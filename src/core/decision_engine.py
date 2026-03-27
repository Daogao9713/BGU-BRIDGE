import json
import random
import re
import time
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field

from openai import OpenAI, BadRequestError

from config.config import LLM_PROVIDER, MODEL_NAME, ACTIVE_API_KEY, ACTIVE_BASE_URL
from .emotion_engine import get_emotion
from .user_profiles import get_relationship_bias

# 可选依赖：没装也能运行
try:
    import json5
except Exception:
    json5 = None

try:
    from json_repair import repair_json
except Exception:
    repair_json = None


# =========================
# Enum 定义
# =========================

class ResponseMode(str, Enum):
    VOICE = "voice"
    TEXT = "text"
    TEXT_IMAGE = "text_image"
    IGNORE = "ignore"
    DELAY = "delay"


class ResponseStyle(str, Enum):
    SOFT = "soft"
    TSUNDERE = "tsundere"
    SARCASTIC = "sarcastic"
    COLD = "cold"
    PLAYFUL = "playful"


class ReactionMode(str, Enum):
    NONE = "none"
    SWEAT = "sweat"
    STARE = "stare"
    MOCK = "mock"
    SILENT = "silent"
    DISGUST = "disgust"


class ActionType(str, Enum):
    NONE = "none"
    MEME = "meme"
    POKE = "poke"
    QUOTE_REPLY = "quote_reply"
    DELAY_SEND = "delay_send"
    VOICE = "voice"
    MUSIC = "music"


# =========================
# 数据结构
# =========================

@dataclass
class DecisionOutput:
    thought: Dict[str, Any]
    emotion_update: Dict[str, float]
    response_plan: Dict[str, Any]
    content: Dict[str, Optional[str]]

    def validate(self) -> bool:
        mode_ok = self.response_plan.get("mode") in [m.value for m in ResponseMode]
        style_ok = self.response_plan.get("style") in [s.value for s in ResponseStyle]
        reaction_ok = self.response_plan.get("reaction_mode", "none") in [m.value for m in ReactionMode]
        action_ok = self.response_plan.get("action", "none") in [a.value for a in ActionType]
        return mode_ok and style_ok and reaction_ok and action_ok and "text" in self.content


@dataclass
class CooldownState:
    active: bool = False
    turns_left: int = 0


@dataclass
class RuntimeState:
    annoyance: float = 10.0
    familiarity: float = 10.0
    turn_count: int = 0
    budget_points: int = 8
    budget_reset_at: float = field(default_factory=lambda: time.time() + 1800.0)
    last_actions: Dict[str, float] = field(default_factory=dict)


# =========================
# Decision Engine
# =========================

class DecisionEngine:
    """
    升级版决策引擎：
    - 冷却状态机
    - JSON 容错解析
    - 复读拦截
    - runtime 状态：annoyance / familiarity / action budget
    - 规则接管：meme / poke / delay / serious override
    """

    EMOTION_KEYS = ["anger", "affection", "playfulness", "fatigue", "pride", "stress"]

    BANNED_REPEAT_PHRASES = [
        "重修小脑",
        "给谁当狗",
        "品种",
    ]

    COOLDOWN_TEXTS = [
        "懒得纠正你。",
        "你继续，我当没听见。",
        "嗯，你开心就好。",
        "这话题已经死了。",
        "别硬撑逻辑了。",
        "听着就累。",
        "我现在连嘲讽都嫌麻烦。",
        "算了，当我没看见。",
        "你说完了吗。",
        "行，算你说了句话。",
    ]

    LOW_EFFORT_PATTERNS = [
        r"^\?$",
        r"^？$",
        r"^哈\??$",
        r"^哈？?$",
        r"^啊\??$",
        r"^在吗$",
        r"^1$",
        r"^6$",
        r"^哦$",
        r"^行吧$",
        r"^真假$",
        r"^就这$",
    ]

    CLINGY_PATTERNS = [
        r"老婆",
        r"宝贝",
        r"求你了",
        r"理理我",
        r"夸我",
        r"别不理我",
    ]

    UNBELIEVABLE_PATTERNS = [
        r"真的假的",
        r"真假",
        r"不是吧",
        r"离谱",
        r"笑死",
        r"你认真的",
        r"哈\?",
        r"哈？",
    ]

    MEME_TRIGGER_KEYWORDS = {
        "sweat": ["真假", "真的假的", "不是吧", "哈？", "哈?", "啊？", "啊?"],
        "stare": ["就这", "6", "行吧", "无语", "哦"],
        "mock": ["笑死", "急了", "嘴硬", "你赢了", "好好好"],
        "silent": ["……", "...", "呵"],
        "disgust": ["离谱", "逆天", "抽象", "什么东西"],
    }

    SERIOUS_PATTERNS = [
        r"自杀",
        r"轻生",
        r"不想活",
        r"想死",
        r"结束生命",
        r"割腕",
        r"吞药",
        r"跳楼",
        r"救命",
        r"我活不下去",
        r"抑郁到不行",
        r"要崩溃了",
    ]

    ACTION_COSTS = {
        ActionType.NONE.value: 0,
        ActionType.MEME.value: 1,
        ActionType.QUOTE_REPLY.value: 1,
        ActionType.DELAY_SEND.value: 1,
        ActionType.POKE.value: 2,
        ActionType.VOICE.value: 3,
        ActionType.MUSIC.value: 4,
    }

    def __init__(self):
        self.client = OpenAI(
            api_key=ACTIVE_API_KEY,
            base_url=ACTIVE_BASE_URL
        )
        self.cooldown_states: Dict[int, CooldownState] = {}
        self.runtime_states: Dict[int, RuntimeState] = {}
        self.recent_bot_texts: Dict[int, List[str]] = {}
        self.recent_user_texts: Dict[int, List[str]] = {}

    # =========================
    # 基础工具
    # =========================

    def _clamp(self, v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    def _boolify(self, v: Any, default: bool = True) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ["true", "1", "yes", "y"]:
                return True
            if s in ["false", "0", "no", "n"]:
                return False
        return default

    def _get_cooldown_state(self, user_id: int) -> CooldownState:
        if user_id not in self.cooldown_states:
            self.cooldown_states[user_id] = CooldownState(active=False, turns_left=0)
        return self.cooldown_states[user_id]

    def _enter_cooldown(self, user_id: int, turns: int = 3):
        self.cooldown_states[user_id] = CooldownState(active=True, turns_left=turns)

    def _tick_cooldown(self, user_id: int):
        state = self._get_cooldown_state(user_id)
        if state.active:
            state.turns_left -= 1
            if state.turns_left <= 0:
                state.active = False
                state.turns_left = 0

    def _get_runtime_state(self, user_id: int) -> RuntimeState:
        if user_id not in self.runtime_states:
            self.runtime_states[user_id] = RuntimeState()
        state = self.runtime_states[user_id]
        self._refresh_budget(state)
        return state

    def _refresh_budget(self, state: RuntimeState):
        now = time.time()
        if now >= state.budget_reset_at:
            state.budget_points = 8
            state.budget_reset_at = now + 1800.0

    def _action_affordable(self, state: RuntimeState, action: str) -> bool:
        cost = self.ACTION_COSTS.get(action, 0)
        return state.budget_points >= cost

    def _spend_action_budget(self, state: RuntimeState, action: str):
        cost = self.ACTION_COSTS.get(action, 0)
        state.budget_points = max(0, state.budget_points - cost)

    def _remember_action(self, state: RuntimeState, action: str):
        state.last_actions[action] = time.time()

    def _action_on_cooldown(self, state: RuntimeState, action: str, cooldown_sec: int) -> bool:
        last = state.last_actions.get(action, 0.0)
        return (time.time() - last) < cooldown_sec

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        text = str(text)
        for ch in ["。", "！", "？", "，", ",", ".", "!", "?", "~", "～", "…", " "]:
            text = text.replace(ch, "")
        return text.strip().lower()

    def _is_emotion_overloaded(self, emotion_dict: Dict[str, float]) -> bool:
        return (
            emotion_dict.get("anger", 0) >= 90
            or emotion_dict.get("fatigue", 0) >= 90
            or emotion_dict.get("stress", 0) >= 90
        )

    def _is_google_backend(self) -> bool:
        base_url = (ACTIVE_BASE_URL or "").lower()
        model_name = (MODEL_NAME or "").lower()
        provider = (LLM_PROVIDER or "").lower()
        return (
            "generativelanguage.googleapis.com" in base_url
            or "googleapis.com" in base_url
            or "gemini" in model_name
            or "google" in provider
        )

    def _is_grok_backend(self) -> bool:
        return "x.ai" in (ACTIVE_BASE_URL or "").lower()

    def _contains_serious_topic(self, text: str) -> bool:
        if not text:
            return False
        for p in self.SERIOUS_PATTERNS:
            if re.search(p, text, flags=re.IGNORECASE):
                return True
        return False

    def _matches_any(self, text: str, patterns: List[str]) -> bool:
        if not text:
            return False
        for p in patterns:
            if re.search(p, text, flags=re.IGNORECASE):
                return True
        return False

    def _extract_relationship_score(self, relationship_bias: Any) -> float:
        if isinstance(relationship_bias, (int, float)):
            return float(relationship_bias)
        if isinstance(relationship_bias, dict):
            for key in ["favor", "score", "affinity", "relationship", "bias"]:
                if key in relationship_bias:
                    try:
                        return float(relationship_bias[key])
                    except Exception:
                        pass
        return 0.0

    # =========================
    # 运行时状态更新
    # =========================

    def _remember_user_text(self, user_id: int, text: str):
        if not text:
            return
        if user_id not in self.recent_user_texts:
            self.recent_user_texts[user_id] = []
        self.recent_user_texts[user_id].append(text.strip())
        self.recent_user_texts[user_id] = self.recent_user_texts[user_id][-12:]

    def _remember_bot_text(self, user_id: int, text: str):
        if not text:
            return
        if user_id not in self.recent_bot_texts:
            self.recent_bot_texts[user_id] = []
        self.recent_bot_texts[user_id].append(text.strip())
        self.recent_bot_texts[user_id] = self.recent_bot_texts[user_id][-12:]

    def _update_runtime_state(self, user_id: int, user_message: str, relationship_bias: Any):
        state = self._get_runtime_state(user_id)
        state.turn_count += 1

        msg = (user_message or "").strip()
        normalized = self._normalize_text(msg)
        recent_users = self.recent_user_texts.get(user_id, [])

        annoyance_delta = 0.0
        familiarity_delta = 0.5

        if len(normalized) <= 2:
            annoyance_delta += 6

        if self._matches_any(msg, self.LOW_EFFORT_PATTERNS):
            annoyance_delta += 10

        if self._matches_any(msg, self.CLINGY_PATTERNS):
            annoyance_delta += 5
            familiarity_delta += 1.5

        if len(msg) >= 25:
            annoyance_delta -= 5
            familiarity_delta += 1.0

        if recent_users:
            last_norm = self._normalize_text(recent_users[-1])
            if normalized and normalized == last_norm:
                annoyance_delta += 12

        relation_score = self._extract_relationship_score(relationship_bias)
        familiarity_delta += relation_score * 0.3
        annoyance_delta -= relation_score * 0.1

        state.annoyance = self._clamp(state.annoyance + annoyance_delta, 0.0, 100.0)
        state.familiarity = self._clamp(state.familiarity + familiarity_delta, 0.0, 100.0)

        self._remember_user_text(user_id, msg)

    # =========================
    # Prompt
    # =========================

    def _build_system_prompt(
        self,
        persona_config: Dict[str, float],
        is_overloaded: bool,
        cooldown_active: bool,
        serious_mode: bool
    ) -> str:
        sharpness = persona_config.get("sharpness", 0.90)
        mercy = persona_config.get("mercy", 0.08)

        if serious_mode:
            return f"""你是 Roxy，一个克制、简短、冷静的赛博角色。

当前规则：
- 用户可能处于严重情绪或现实风险场景。
- 这时不要玩梗、不要阴阳怪气、不要发 meme、不要 poke。
- 允许冷静、简短，但要避免刺伤对方。
- 优先给出直接、可执行、现实导向的回应。
- 不要写成长篇。
- 不要自称 AI，不要输出免责声明长段模板。
- `emotion_update` 表示增量，每项只能在 -15 到 15 之间。

严格格式要求：
1. 只能输出一个 JSON 对象，不能输出任何解释。
2. 所有 key 和字符串必须使用双引号。
3. 不允许 markdown 代码块。
4. 最外层固定包含：
   "thought", "emotion_update", "response_plan", "content"

输出严格 JSON：
{{
  "thought": {{
    "intent": "comfort|stabilize|guide",
    "emotion_trigger": "serious_topic",
    "risk_level": 0.9,
    "user_effort": 0.5,
    "weirdness": 0.0
  }},
  "emotion_update": {{
    "anger": 0,
    "affection": 0,
    "playfulness": 0,
    "fatigue": 0,
    "pride": 0,
    "stress": 0
  }},
  "response_plan": {{
    "mode": "text",
    "style": "soft",
    "intensity": 0.2,
    "reaction_mode": "none",
    "action": "none",
    "delay_ms": 0,
    "should_text": true
  }},
  "content": {{
    "text": "简短回复",
    "voice_text": "简短回复",
    "meme_tag": null,
    "meme_text": null
  }}
}}"""

        base_prompt = f"""你是 Roxy，一个高判断感、低情绪劳动、嫌解释的赛博少女。

你的风格：
- 简短
- 冷淡
- 不喜欢冗长解释
- 会优先指出问题，而不是照顾情绪
- 刻薄来自效率感，不来自粗暴辱骂
- 面对低质量、重复、夸张、过度讨好的输入时，更倾向短句、拒绝、沉默或表情化反应

重要行为倾向：
1. 如果用户输入很低质量、很离谱、很黏、很复读，优先考虑 `reaction_mode` 和 `action`。
2. 发图不是沉重决定。遇到“哈？/真假/不是吧/就这/离谱/笑死”等，可优先 `action="meme"`。
3. 你可以只发梗图不打字：`should_text=false`。
4. 你不需要总是解释完整，短句更像你。
5. 不要复读最近常说的话，不要机械地只会“无聊/哦/随便”。
6. `emotion_update` 是增量，每项只能在 -15 到 15 之间。

可选 reaction_mode（只能从这里选）：
- none
- sweat
- stare
- mock
- silent
- disgust

可选 action（只能从这里选）：
- none
- meme
- poke
- quote_reply
- delay_send
- voice
- music

可选 mode：
- voice
- text
- text_image
- ignore
- delay

可选 style：
- soft
- tsundere
- sarcastic
- cold
- playful

人格参数：
- 锋利度: {sharpness:.2f}
- 怜悯心: {mercy:.2f}

严格格式要求：
1. 只能输出一个 JSON 对象，不能输出任何解释、注释、前后缀文本。
2. 所有 key 必须使用双引号。
3. 所有字符串必须使用双引号。
4. 小数必须写成 0.6，不能写 .6。
5. 不允许输出 markdown 代码块。
6. 最外层必须固定包含四个字段：
   "thought", "emotion_update", "response_plan", "content"
7. 如果不确定，也必须返回合法 JSON。

输出严格 JSON：
{{
  "thought": {{
    "intent": "answer|reject|tease|question_back|ignore|meta_react|clarify",
    "emotion_trigger": "short phrase",
    "risk_level": 0.2,
    "user_effort": 0.3,
    "weirdness": 0.4
  }},
  "emotion_update": {{
    "anger": 0,
    "affection": 0,
    "playfulness": 0,
    "fatigue": 0,
    "pride": 0,
    "stress": 0
  }},
  "response_plan": {{
    "mode": "voice|text|text_image|ignore|delay",
    "style": "soft|tsundere|sarcastic|cold|playful",
    "intensity": 0.5,
    "reaction_mode": "none|sweat|stare|mock|silent|disgust",
    "action": "none|meme|poke|quote_reply|delay_send|voice|music",
    "delay_ms": 0,
    "should_text": true
  }},
  "content": {{
    "text": "回复文本",
    "voice_text": "语音文本",
    "meme_tag": "none|sweat|stare|mock|silent|disgust",
    "meme_text": "不超过6个字"
  }}
}}"""

        if is_overloaded or cooldown_active:
            cooldown_prompt = """
【冷却态规则】
你处于强制冷却期。
这不是暴怒，而是“已经懒得多说”的状态。

要求：
- 回复短、冷、低能量。
- 允许轻微不耐烦，但禁止情绪爆炸。
- `style` 优先 `cold`
- `intensity` 不要超过 0.35
- `mode` 优先 `text`
- `action` 优先 `none|delay_send`
- `reaction_mode` 允许 `silent|stare`
- `emotion_update` 以泄压为主：anger / stress / fatigue 倾向负数
"""
            return base_prompt + cooldown_prompt

        return base_prompt

    # =========================
    # JSON 容错解析
    # =========================

    def _extract_json_object(self, text: str) -> str:
        text = (text or "").strip()
        text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1].strip()
        return text

    def _basic_json_fixups(self, text: str) -> str:
        s = text.strip()
        s = s.replace("\u3000", " ")

        s = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', s)
        s = re.sub(r'(:\s*)\.(\d+)', r'\g<1>0.\2', s)
        s = re.sub(r'(\[\s*)\.(\d+)', r'\g<1>0.\2', s)
        s = re.sub(r'(,\s*)\.(\d+)', r'\g<1>0.\2', s)

        s = re.sub(
            r":\s*'([^']*)'",
            lambda m: ': "' + m.group(1).replace('"', '\\"') + '"',
            s
        )
        return s

    def _parse_response_text(self, response_text: str) -> Dict[str, Any]:
        candidate = self._extract_json_object(response_text)

        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        if json5 is not None:
            try:
                data = json5.loads(candidate)
                if isinstance(data, dict):
                    print("[decision_engine] parsed by json5")
                    return data
            except Exception:
                pass

        if repair_json is not None:
            try:
                repaired = repair_json(candidate, ensure_ascii=False)
                data = json.loads(repaired)
                if isinstance(data, dict):
                    print(f"[decision_engine] repaired json = {repaired}")
                    return data
            except Exception:
                pass

        try:
            fixed = self._basic_json_fixups(candidate)
            data = json.loads(fixed)
            if isinstance(data, dict):
                print(f"[decision_engine] parsed by regex-fix = {fixed}")
                return data
        except Exception:
            pass

        raise ValueError(f"无法解析模型输出为 JSON: {response_text}")

    def _extract_fallback_text(self, raw_text: str) -> str:
        if not raw_text:
            return "……"

        try:
            data = self._parse_response_text(raw_text)
            text = str((data.get("content") or {}).get("text", "") or "").strip()
            if text:
                return text
        except Exception:
            pass

        patterns = [
            r'"text"\s*:\s*"([^"]+)"',
            r"'text'\s*:\s*'([^']+)'",
            r'"text"\s*:\s*\'([^\']+)\'',
            r'text\s*:\s*"([^"]+)"',
            r'text\s*:\s*\'([^\']+)\'',
        ]
        for p in patterns:
            m = re.search(p, raw_text, flags=re.DOTALL)
            if m:
                text = m.group(1).strip()
                if text:
                    return text

        return "……"

    # =========================
    # 清洗 / 复读拦截
    # =========================

    def _sanitize_emotion_update(self, update: Dict[str, Any], is_cooldown: bool, serious_mode: bool) -> Dict[str, float]:
        clean = {}

        for k in self.EMOTION_KEYS:
            raw_val = update.get(k, 0)
            try:
                val = float(raw_val)
            except Exception:
                val = 0.0
            val = self._clamp(val, -15, 15)
            clean[k] = val

        if not is_cooldown and not serious_mode:
            if clean.get("affection", 0) > 5 or clean.get("playfulness", 0) > 5:
                clean["fatigue"] = min(clean.get("fatigue", 0), -5.0)
                clean["stress"] = min(clean.get("stress", 0), -5.0)

        if is_cooldown:
            clean["anger"] = min(clean.get("anger", 0), -15.0)
            clean["stress"] = min(clean.get("stress", 0), -15.0)
            clean["fatigue"] = min(clean.get("fatigue", 0), -15.0)
            clean["playfulness"] = min(clean.get("playfulness", 0), -5.0)

        if serious_mode:
            clean["playfulness"] = min(clean.get("playfulness", 0), 0.0)
            clean["anger"] = min(clean.get("anger", 0), 0.0)

        return clean

    def _sanitize_response_plan(
        self,
        response_plan: Dict[str, Any],
        is_cooldown: bool,
        serious_mode: bool
    ) -> Dict[str, Any]:
        mode = response_plan.get("mode", "text")
        style = response_plan.get("style", "cold")
        intensity = response_plan.get("intensity", 0.5)
        reaction_mode = response_plan.get("reaction_mode", "none")
        action = response_plan.get("action", "none")
        delay_ms = response_plan.get("delay_ms", 0)
        should_text = self._boolify(response_plan.get("should_text", True), True)

        if mode not in [m.value for m in ResponseMode]:
            mode = "text"
        if style not in [s.value for s in ResponseStyle]:
            style = "cold"
        if reaction_mode not in [m.value for m in ReactionMode]:
            reaction_mode = "none"
        if action not in [a.value for a in ActionType]:
            action = "none"

        try:
            intensity = float(intensity)
        except Exception:
            intensity = 0.5
        intensity = self._clamp(intensity, 0.0, 1.0)

        try:
            delay_ms = int(delay_ms)
        except Exception:
            delay_ms = 0
        delay_ms = int(self._clamp(delay_ms, 0, 10000))

        if serious_mode:
            mode = "text"
            style = "soft"
            intensity = min(intensity, 0.25)
            reaction_mode = "none"
            action = "none"
            delay_ms = 0
            should_text = True

        if is_cooldown:
            mode = "text"
            style = "cold"
            intensity = min(intensity, 0.35)
            if action not in [ActionType.NONE.value, ActionType.DELAY_SEND.value]:
                action = "none"
            if reaction_mode not in [ReactionMode.NONE.value, ReactionMode.SILENT.value, ReactionMode.STARE.value]:
                reaction_mode = "none"

        return {
            "mode": mode,
            "style": style,
            "intensity": intensity,
            "reaction_mode": reaction_mode,
            "action": action,
            "delay_ms": delay_ms,
            "should_text": should_text,
        }

    def _contains_repeated_phrase(self, text: str, user_id: int) -> bool:
        if not text:
            return False

        normalized_text = self._normalize_text(text)

        for phrase in self.BANNED_REPEAT_PHRASES:
            if phrase and phrase in normalized_text:
                return True

        recent = self.recent_bot_texts.get(user_id, [])
        for old in recent[-6:]:
            if not old:
                continue
            old_normalized = self._normalize_text(old)

            if normalized_text == old_normalized:
                return True

            if len(normalized_text) > 4 and (
                normalized_text in old_normalized or old_normalized in normalized_text
            ):
                return True

        return False

    def _pick_cooldown_text(self, user_id: int) -> str:
        recent = set(self.recent_bot_texts.get(user_id, [])[-6:])
        candidates = [t for t in self.COOLDOWN_TEXTS if t not in recent]
        if not candidates:
            candidates = self.COOLDOWN_TEXTS
        return random.choice(candidates)
    
    def _strip_rlhf_tail(self, text: str) -> str:
        """
        清理常见的 RLHF 尾巴
        
        某些模型会在回复末尾加上类似：
        - 如果你愿意，我可以继续帮你。
        - 希望这对你有帮助。
        - 请随时告诉我。
        
        这个函数会将这些尾巴删掉
        """
        if not text:
            return text
        
        bad_tails = [
            "如果你愿意，我可以继续帮你。",
            "如果你愿意，我可以继续帮助你。",
            "希望这对你有帮助。",
            "希望有帮助。",
            "如果你需要，我可以继续。",
            "请随时告诉我。",
            "请随时告诉我你需要什么。",
            "有其他问题吗？",
            "还有其他问题吗？",
            "希望能帮上忙。",
            "感谢理解。",
            "如果还有其他需要，请随时告诉我。",
        ]
        
        for tail in bad_tails:
            if tail in text:
                text = text.replace(tail, "").strip()
        
        return text

    def _sanitize_content(
        self,
        content: Dict[str, Any],
        user_id: int,
        is_cooldown: bool,
        serious_mode: bool,
        response_plan: Dict[str, Any]
    ) -> Dict[str, Optional[str]]:
        text = str(content.get("text", "") or "").strip()
        voice_text = str(content.get("voice_text", "") or "").strip()
        meme_tag = content.get("meme_tag")
        meme_text = content.get("meme_text")

        if serious_mode:
            if not text:
                text = "先保证你现在是安全的。"
            voice_text = text
            meme_tag = None
            meme_text = None

        elif is_cooldown:
            if not text or len(text) > 14 or self._contains_repeated_phrase(text, user_id):
                text = self._pick_cooldown_text(user_id)

            for p in self.BANNED_REPEAT_PHRASES:
                text = text.replace(p, "").strip()

            if not text:
                text = self._pick_cooldown_text(user_id)

            voice_text = text
            meme_tag = None
            meme_text = None
        else:
            if response_plan.get("should_text", True):
                if not text:
                    text = "……"
                if self._contains_repeated_phrase(text, user_id):
                    text = self._pick_cooldown_text(user_id)
                    voice_text = text
                    meme_tag = None
                    meme_text = None
            else:
                text = ""

        if len(text) > 80:
            text = text[:80].rstrip()

        if not voice_text:
            voice_text = text
        elif len(voice_text) > 80:
            voice_text = voice_text[:80].rstrip()

        # 清理 RLHF 尾巴
        text = self._strip_rlhf_tail(text)
        voice_text = self._strip_rlhf_tail(voice_text)

        if meme_tag is not None:
            meme_tag = str(meme_tag).strip().lower()[:12] or None
            # 验证 meme_tag 是否在梗图映射表中
            # MEME_MAP 在 action_executor 中定义
            valid_meme_tags = {"sweat", "stare", "mock", "silent", "disgust"}
            if meme_tag not in valid_meme_tags:
                meme_tag = None

        if meme_text is not None:
            meme_text = str(meme_text).strip()[:12] or None

        return {
            "text": text,
            "voice_text": voice_text,
            "meme_tag": meme_tag,
            "meme_text": meme_text
        }

    # =========================
    # 规则路由层
    # =========================

    def _infer_reaction_mode_from_text(self, user_message: str) -> str:
        msg = user_message or ""
        for reaction, keywords in self.MEME_TRIGGER_KEYWORDS.items():
            if any(k in msg for k in keywords):
                return reaction
        return random.choice([
            ReactionMode.SWEAT.value,
            ReactionMode.STARE.value,
            ReactionMode.MOCK.value
        ])

    def _build_rule_based_text(self, intent: str, annoyance: float, serious_mode: bool) -> str:
        if serious_mode:
            return "先保证你现在是安全的。"

        if intent == "reject":
            pool = ["看文档。", "上面说过。", "自己翻。", "没空重讲。"]
        elif intent == "tease":
            pool = ["你还挺有自信。", "这也能算结论？", "你先把逻辑补上。", "挺会想。"]
        elif intent == "question_back":
            pool = ["你到底想问什么。", "重点呢。", "你先说清楚。", "上下文呢。"]
        else:
            if annoyance >= 70:
                pool = ["行。", "你继续。", "嗯。", "随你。"]
            elif annoyance >= 40:
                pool = ["说重点。", "简短点。", "继续。", "嗯？"]
            else:
                pool = ["继续。", "说。", "嗯？", "你接着编。"]
        return random.choice(pool)

    def _apply_rule_router(
        self,
        user_id: int,
        user_message: str,
        source: str,
        serious_mode: bool,
        is_cooldown: bool,
        decision: DecisionOutput
    ) -> DecisionOutput:
        state = self._get_runtime_state(user_id)
        plan = dict(decision.response_plan)
        content = dict(decision.content)
        thought = dict(decision.thought)

        annoyance = state.annoyance
        familiarity = state.familiarity
        msg = user_message or ""

        # 1. 严肃模式直接接管
        if serious_mode:
            plan["mode"] = ResponseMode.TEXT.value
            plan["style"] = ResponseStyle.SOFT.value
            plan["intensity"] = min(float(plan.get("intensity", 0.2)), 0.25)
            plan["reaction_mode"] = ReactionMode.NONE.value
            plan["action"] = ActionType.NONE.value
            plan["delay_ms"] = 0
            plan["should_text"] = True
            content["meme_tag"] = None
            content["meme_text"] = None
            if not content.get("text"):
                content["text"] = "先保证你现在是安全的。"
            content["voice_text"] = content["text"]
            thought["emotion_trigger"] = "serious_topic_override"
            decision.response_plan = plan
            decision.content = content
            decision.thought = thought
            return decision

        # 2. 冷却模式限制激烈动作
        if is_cooldown:
            if plan.get("action") not in [ActionType.NONE.value, ActionType.DELAY_SEND.value]:
                plan["action"] = ActionType.NONE.value
            if plan.get("reaction_mode") not in [ReactionMode.NONE.value, ReactionMode.SILENT.value, ReactionMode.STARE.value]:
                plan["reaction_mode"] = ReactionMode.NONE.value
            if not content.get("text"):
                content["text"] = self._pick_cooldown_text(user_id)
                content["voice_text"] = content["text"]

        # 3. 关键词硬触发 meme
        hard_meme_trigger = any(k in msg for keys in self.MEME_TRIGGER_KEYWORDS.values() for k in keys)
        model_risk = 0.2
        try:
            model_risk = float(thought.get("risk_level", 0.2))
        except Exception:
            model_risk = 0.2

        if (
            not serious_mode
            and not is_cooldown
            and hard_meme_trigger
            and model_risk <= 0.45
            and not self._action_on_cooldown(state, ActionType.MEME.value, cooldown_sec=40)
            and self._action_affordable(state, ActionType.MEME.value)
        ):
            plan["action"] = ActionType.MEME.value
            plan["reaction_mode"] = self._infer_reaction_mode_from_text(msg)
            plan["mode"] = ResponseMode.TEXT_IMAGE.value
            if random.random() < 0.45:
                plan["should_text"] = False
                content["text"] = ""
                content["voice_text"] = ""
            else:
                plan["should_text"] = True
                if not content.get("text"):
                    content["text"] = self._build_rule_based_text("tease", annoyance, False)
                    content["voice_text"] = content["text"]
            content["meme_tag"] = plan["reaction_mode"]
            if not content.get("meme_text") and plan["should_text"]:
                content["meme_text"] = None

        # 4. 高烦躁值 → 更偏短句/延迟
        if not serious_mode and annoyance >= 60:
            if plan.get("action") == ActionType.NONE.value and random.random() < 0.35:
                if self._action_affordable(state, ActionType.DELAY_SEND.value):
                    plan["action"] = ActionType.DELAY_SEND.value
                    plan["mode"] = ResponseMode.DELAY.value
                    plan["delay_ms"] = max(int(plan.get("delay_ms", 0)), random.randint(1200, 3200))
            if not content.get("text") and plan.get("should_text", True):
                content["text"] = self._build_rule_based_text("reject", annoyance, False)
                content["voice_text"] = content["text"]

        # 5. 熟人 + 轻度烦躁 → 偶发 poke
        if (
            source in ["private", "group"]
            and not serious_mode
            and not is_cooldown
            and familiarity >= 35
            and annoyance >= 55
            and plan.get("action") == ActionType.NONE.value
            and random.random() < 0.10
            and not self._action_on_cooldown(state, ActionType.POKE.value, cooldown_sec=6 * 3600)
            and self._action_affordable(state, ActionType.POKE.value)
        ):
            plan["action"] = ActionType.POKE.value
            plan["reaction_mode"] = plan.get("reaction_mode", ReactionMode.NONE.value)

        # 6. 如果 action=meme 但 reaction_mode 缺失，代码补齐
        if plan.get("action") == ActionType.MEME.value and plan.get("reaction_mode") == ReactionMode.NONE.value:
            plan["reaction_mode"] = self._infer_reaction_mode_from_text(msg)
            content["meme_tag"] = plan["reaction_mode"]

        # 7. budget 不够则降级
        action = plan.get("action", ActionType.NONE.value)
        if not self._action_affordable(state, action):
            plan["action"] = ActionType.NONE.value
            if plan.get("mode") == ResponseMode.TEXT_IMAGE.value:
                plan["mode"] = ResponseMode.TEXT.value
            if plan.get("reaction_mode") != ReactionMode.NONE.value:
                plan["reaction_mode"] = ReactionMode.NONE.value
            content["meme_tag"] = None
            content["meme_text"] = None
            if not content.get("text") and plan.get("should_text", True):
                content["text"] = self._build_rule_based_text("answer", annoyance, False)
                content["voice_text"] = content["text"]

        # 8. 最后如果 should_text=True 但没文本，补模板
        if plan.get("should_text", True) and not content.get("text"):
            intent = str(thought.get("intent", "answer") or "answer")
            content["text"] = self._build_rule_based_text(intent, annoyance, False)
            content["voice_text"] = content["text"]

        decision.response_plan = plan
        decision.content = content
        decision.thought = thought
        return decision

    # =========================
    # 后处理
    # =========================

    def _postprocess_decision(
        self,
        user_id: int,
        raw_dict: Dict[str, Any],
        is_cooldown: bool,
        serious_mode: bool
    ) -> DecisionOutput:
        decision = DecisionOutput(
            thought=raw_dict.get("thought", {}) if isinstance(raw_dict.get("thought", {}), dict) else {},
            emotion_update=raw_dict.get("emotion_update", {}) if isinstance(raw_dict.get("emotion_update", {}), dict) else {},
            response_plan=raw_dict.get("response_plan", {}) if isinstance(raw_dict.get("response_plan", {}), dict) else {},
            content=raw_dict.get("content", {}) if isinstance(raw_dict.get("content", {}), dict) else {}
        )

        decision.emotion_update = self._sanitize_emotion_update(
            decision.emotion_update,
            is_cooldown=is_cooldown,
            serious_mode=serious_mode
        )
        decision.response_plan = self._sanitize_response_plan(
            decision.response_plan,
            is_cooldown=is_cooldown,
            serious_mode=serious_mode
        )
        decision.content = self._sanitize_content(
            decision.content,
            user_id=user_id,
            is_cooldown=is_cooldown,
            serious_mode=serious_mode,
            response_plan=decision.response_plan
        )

        if not decision.validate():
            text = "先保证你现在是安全的。" if serious_mode else (self._pick_cooldown_text(user_id) if is_cooldown else "……")
            decision = DecisionOutput(
                thought={
                    "intent": "fallback",
                    "emotion_trigger": "fallback",
                    "risk_level": 0.2,
                    "user_effort": 0.0,
                    "weirdness": 0.0
                },
                emotion_update=self._sanitize_emotion_update({}, is_cooldown, serious_mode),
                response_plan=self._sanitize_response_plan({}, is_cooldown, serious_mode),
                content={
                    "text": text,
                    "voice_text": text,
                    "meme_tag": None,
                    "meme_text": None
                }
            )

        return decision

    # =========================
    # 情绪读取
    # =========================

    def _get_group_emotion_safe(self, group_id: int):
        try:
            return get_emotion(user_id=group_id)
        except Exception:
            return get_emotion(user_id=0)

    # =========================
    # 模型请求
    # =========================

    def _build_request_params(
        self,
        final_messages: List[Dict[str, Any]],
        temperature: float
    ) -> Dict[str, Any]:
        is_google = self._is_google_backend()
        is_grok = self._is_grok_backend()

        request_params = {
            "model": MODEL_NAME,
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": 260,
            "response_format": {"type": "json_object"},
        }

        if not is_google and not is_grok:
            request_params["presence_penalty"] = 0.0
            request_params["frequency_penalty"] = 0.0

        return request_params

    def _request_chat_completion(self, request_params: Dict[str, Any]):
        is_google_backend = self._is_google_backend()

        try:
            return self.client.chat.completions.create(**request_params)
        except BadRequestError as e:
            err_text = str(e).lower()

            if is_google_backend and "response_format" in request_params and (
                "response_format" in err_text
                or "json_object" in err_text
                or 'unknown name "response_format"' in err_text
            ):
                print("[decision_engine] Gemini/Google 端不接受 response_format，自动移除后重试一次")
                retry_params = dict(request_params)
                retry_params.pop("response_format", None)
                return self.client.chat.completions.create(**retry_params)

            raise

    # =========================
    # 主逻辑
    # =========================

    async def decide(
        self,
        user_message: str,
        user_id: int,
        username: str,
        source: str = "private",
        group_id: int = 0,
        persona_config: Optional[Dict[str, float]] = None,
        user_history: Optional[list] = None
    ) -> Optional[DecisionOutput]:

        # 安全词重置
        safety_words = ["系统重启", "安全词归零", "Roxy恢复正常"]
        if any(word in user_message for word in safety_words):
            self.cooldown_states[user_id] = CooldownState(active=False, turns_left=0)
            self.recent_bot_texts[user_id] = []
            self.recent_user_texts[user_id] = []
            self.runtime_states[user_id] = RuntimeState()

            reset_update = {
                "anger": -100.0,
                "fatigue": -100.0,
                "stress": -100.0,
                "pride": -50.0,
                "affection": 10.0,
                "playfulness": 10.0
            }

            print(f"[decision_engine] 触发安全词，用户 {user_id} 状态强制重置！")

            return DecisionOutput(
                thought={
                    "intent": "hard_reset",
                    "emotion_trigger": "safety_word_triggered",
                    "risk_level": 0.0,
                    "user_effort": 0.0,
                    "weirdness": 0.0
                },
                emotion_update=reset_update,
                response_plan={
                    "mode": "text",
                    "style": "soft",
                    "intensity": 0.2,
                    "reaction_mode": "none",
                    "action": "none",
                    "delay_ms": 0,
                    "should_text": True
                },
                content={
                    "text": "（系统重启中...滴...）啧，刚才内存溢出了，别拿那种眼神看我。",
                    "voice_text": "重启完成。刚才的事当没发生过。",
                    "meme_tag": None,
                    "meme_text": None
                }
            )

        if persona_config is None:
            persona_config = {
                "sharpness": 0.90,
                "voice_preference": 0.3,
                "tsundere_level": 0.8,
                "mercy": 0.08
            }

        # 1. 读取状态
        current_emotion = get_emotion(user_id=user_id)
        emotion_dict = current_emotion.to_dict()
        relationship_bias = get_relationship_bias(user_id)

        self._update_runtime_state(user_id, user_message, relationship_bias)
        runtime_state = self._get_runtime_state(user_id)

        state = self._get_cooldown_state(user_id)
        overloaded_now = self._is_emotion_overloaded(emotion_dict)

        if source == "group" and group_id != 0:
            try:
                group_emo = self._get_group_emotion_safe(group_id)
                if self._is_emotion_overloaded(group_emo.to_dict()):
                    overloaded_now = True
            except Exception:
                pass

        if overloaded_now and not state.active:
            self._enter_cooldown(user_id, turns=3)
            state = self._get_cooldown_state(user_id)

        is_cooldown = state.active or overloaded_now
        serious_mode = self._contains_serious_topic(user_message)

        # 2. 构建上下文
        user_context = f"""[用户信息]
用户ID: {user_id}
用户名: {username}
消息来源: {'私聊' if source == 'private' else '群聊'}
群号: {group_id if group_id else '无'}
关系偏置: {relationship_bias}

[当前情绪状态] (0-100)
- 愤怒: {emotion_dict.get('anger', 0):.1f}
- 亲近: {emotion_dict.get('affection', 0):.1f}
- 疲惫: {emotion_dict.get('fatigue', 0):.1f}
- 压力: {emotion_dict.get('stress', 0):.1f}
- 傲气: {emotion_dict.get('pride', 0):.1f}
- 玩心: {emotion_dict.get('playfulness', 0):.1f}

[运行时状态]
- annoyance: {runtime_state.annoyance:.1f}
- familiarity: {runtime_state.familiarity:.1f}
- turn_count: {runtime_state.turn_count}
- action_budget: {runtime_state.budget_points}

[当前冷却状态]
- active: {is_cooldown}
- turns_left: {state.turns_left}

[风险模式]
- serious_mode: {serious_mode}

[用户消息]
{user_message}

请根据以上信息输出 JSON。
注意：当前处于 {'【严肃模式】' if serious_mode else ('【强制冷却态】' if is_cooldown else '【正常态】')}。
"""

        response_text = ""

        try:
            system_prompt = self._build_system_prompt(
                persona_config=persona_config,
                is_overloaded=overloaded_now,
                cooldown_active=state.active,
                serious_mode=serious_mode
            )

            messages: List[Dict[str, Any]] = []
            if user_history:
                for m in user_history:
                    if not isinstance(m, dict):
                        continue
                    if m.get("role") == "system":
                        continue
                    if "role" not in m or "content" not in m:
                        continue
                    messages.append({
                        "role": m["role"],
                        "content": m["content"]
                    })

            messages.append({"role": "user", "content": user_context})
            final_messages = [{"role": "system", "content": system_prompt}] + messages

            current_temperature = 0.25 if serious_mode else (0.45 if is_cooldown else 0.78)

            print(f"====== BASE_URL: {self.client.base_url} ======")
            print(f"====== MODEL: {MODEL_NAME} ======")
            print(f"====== is_google_backend: {self._is_google_backend()} ======")

            request_params = self._build_request_params(
                final_messages=final_messages,
                temperature=current_temperature
            )

            print(f"====== request params keys: {list(request_params.keys())} ======")

            resp = self._request_chat_completion(request_params)
            response_text = (resp.choices[0].message.content or "").strip()

            print(
                f"[decision_engine] serious_mode={serious_mode}, overloaded_now={overloaded_now}, "
                f"cooldown_active={state.active}, turns_left={state.turns_left}"
            )
            print(f"[decision_engine] runtime: annoyance={runtime_state.annoyance:.1f}, familiarity={runtime_state.familiarity:.1f}, budget={runtime_state.budget_points}")
            print(f"[decision_engine] raw response = {response_text}")

            raw_dict = self._parse_response_text(response_text)

            decision = self._postprocess_decision(
                user_id=user_id,
                raw_dict=raw_dict,
                is_cooldown=is_cooldown,
                serious_mode=serious_mode
            )

            decision = self._apply_rule_router(
                user_id=user_id,
                user_message=user_message,
                source=source,
                serious_mode=serious_mode,
                is_cooldown=is_cooldown,
                decision=decision
            )

            # 二次清洗，防止 rule_router 注入坏字段
            decision.response_plan = self._sanitize_response_plan(
                decision.response_plan,
                is_cooldown=is_cooldown,
                serious_mode=serious_mode
            )
            decision.content = self._sanitize_content(
                decision.content,
                user_id=user_id,
                is_cooldown=is_cooldown,
                serious_mode=serious_mode,
                response_plan=decision.response_plan
            )

            # 记录文本
            self._remember_bot_text(user_id, decision.content.get("text", "") or "")

            # 记录并扣预算
            final_action = decision.response_plan.get("action", ActionType.NONE.value)
            if final_action != ActionType.NONE.value and self._action_affordable(runtime_state, final_action):
                self._spend_action_budget(runtime_state, final_action)
                self._remember_action(runtime_state, final_action)

            # mode=voice 时，如果没 voice_text，则补 text
            if decision.response_plan.get("mode") == ResponseMode.VOICE.value and not decision.content.get("voice_text"):
                decision.content["voice_text"] = decision.content.get("text", "") or "……"

            self._tick_cooldown(user_id)
            return decision

        except Exception:
            import traceback
            traceback.print_exc()

            extracted_text = self._extract_fallback_text(response_text)

            if serious_mode:
                fallback_text = extracted_text if extracted_text and extracted_text != "……" else "先保证你现在是安全的。"
            elif is_cooldown:
                if not extracted_text or extracted_text == "……" or self._contains_repeated_phrase(extracted_text, user_id):
                    fallback_text = self._pick_cooldown_text(user_id)
                else:
                    fallback_text = extracted_text
            else:
                fallback_text = extracted_text if extracted_text and extracted_text != "……" else "……"

            self._remember_bot_text(user_id, fallback_text)
            self._tick_cooldown(user_id)

            return DecisionOutput(
                thought={
                    "intent": "fallback",
                    "emotion_trigger": "exception",
                    "risk_level": 0.1,
                    "user_effort": 0.0,
                    "weirdness": 0.0
                },
                emotion_update=self._sanitize_emotion_update({}, is_cooldown, serious_mode),
                response_plan=self._sanitize_response_plan({}, is_cooldown, serious_mode),
                content={
                    "text": fallback_text,
                    "voice_text": fallback_text,
                    "meme_tag": None,
                    "meme_text": None
                }
            )


# 全局单例
decision_engine = DecisionEngine()


# 兼容旧接口
async def make_decision(
    user_message: str,
    user_id: int,
    username: str,
    source: str = "private",
    group_id: int = 0,
    persona_config: Optional[Dict[str, float]] = None,
    user_history: Optional[list] = None
) -> Optional[DecisionOutput]:
    return await decision_engine.decide(
        user_message=user_message,
        user_id=user_id,
        username=username,
        source=source,
        group_id=group_id,
        persona_config=persona_config,
        user_history=user_history
    )