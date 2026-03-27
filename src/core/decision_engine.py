import json
import random
import re
import time
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field, asdict

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
    NEUTRAL = "neutral"
    NATURAL = "natural"
    PLAYFUL = "playful"
    LOW_ENERGY = "low_energy"
    COLD = "cold"
    TSUNDERE = "tsundere"
    SARCASTIC = "sarcastic"


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
    annoyance: float = 8.0
    familiarity: float = 20.0
    fatigue: float = 8.0
    engagement: float = 35.0

    turn_count: int = 0
    budget_points: int = 8
    budget_reset_at: float = field(default_factory=lambda: time.time() + 1800.0)
    last_actions: Dict[str, float] = field(default_factory=dict)

    last_update_at: float = field(default_factory=time.time)
    last_extend: bool = False
    last_tone: str = "neutral"


# =========================
# 文本工具
# =========================

def clean_roxy_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text).strip()

    rlhf_patterns = [
        r'\s*\[?\|?end\|?\]?\s*$',
        r'\s*</s>\s*$',
        r'\s*<\|end_of_text\|>\s*$',
        r'\s*\[EOS\]\s*$',
        r'\s*\[PAD\]\s*$',
        r'\s*\[SCORE:\s*[\d.]+\]\s*$',
        r'\s*Rating:\s*[\d.]+(/\d+)?\s*$',
        r'\s*>>>\s*$',
        r'\s*---\s*$',
        r'\s*\[※\]\s*$',
        r'如果还有其他需要，请随时告诉我。?$',
        r'如果你愿意，我可以继续帮你。?$',
        r'如果你需要，我可以继续。?$',
        r'希望对你有帮助。?$',
        r'希望这对你有帮助。?$',
        r'有其他问题吗。?$',
        r'还有其他问题吗。?$',
        r'请随时告诉我。?$',
    ]
    for p in rlhf_patterns:
        text = re.sub(p, '', text, flags=re.IGNORECASE)

    return text.strip().rstrip("。").rstrip(".").strip()


# =========================
# Decision Engine
# =========================

class DecisionEngine:
    EMOTION_KEYS = ["anger", "affection", "playfulness", "fatigue", "pride", "stress"]

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
        r"^嗯$",
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

    HARASSMENT_PATTERNS = [
        r"傻逼", r"煞笔", r"弱智", r"废物", r"滚", r"去死", r"闭嘴",
        r"你妈", r"操你", r"欠骂", r"nt", r"脑残"
    ]

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

    QUESTION_PATTERNS = [
        r"\?$", r"？$", r"怎么", r"为什么", r"啥", r"什么", r"如何", r"是不是", r"能不能", r"可不可以", r"吗"
    ]

    MEME_TRIGGER_KEYWORDS = {
        "sweat": ["真假", "真的假的", "不是吧", "哈？", "哈?", "啊？", "啊?"],
        "stare": ["就这", "6", "行吧", "无语", "哦"],
        "mock": ["笑死", "急了", "嘴硬", "你赢了", "好好好"],
        "silent": ["……", "...", "呵"],
        "disgust": ["离谱", "逆天", "抽象", "什么东西"],
    }

    ACTION_COSTS = {
        ActionType.NONE.value: 0,
        ActionType.MEME.value: 1,
        ActionType.QUOTE_REPLY.value: 1,
        ActionType.DELAY_SEND.value: 1,
        ActionType.POKE.value: 2,
        ActionType.VOICE.value: 3,
        ActionType.MUSIC.value: 4,
    }

    VALID_INTENTS = {
        "answer", "ack", "clarify", "question_back", "boundary",
        "ignore", "meta_react", "comfort", "stabilize", "fallback"
    }

    NEUTRAL_FILLERS = [
        "嗯",
        "收到",
        "你继续",
        "说重点",
        "在看",
    ]

    LOW_ENERGY_FILLERS = [
        "我有点没电",
        "晚点再聊",
        "先简单说",
        "我先缓一下",
        "我现在打字有点慢",
    ]

    BOUNDARY_FILLERS = [
        "这个话题我不想接",
        "先到这吧",
        "别继续这个方向",
        "换个正常点的话题",
    ]

    SERIOUS_FALLBACK = "先保证你现在是安全的"

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

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        text = str(text)
        for ch in ["。", "！", "？", "，", ",", ".", "!", "?", "~", "～", "…", " "]:
            text = text.replace(ch, "")
        return text.strip().lower()

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
        return self._matches_any(text, self.SERIOUS_PATTERNS)

    def _contains_question_signal(self, text: str) -> bool:
        return self._matches_any(text, self.QUESTION_PATTERNS)

    def _contains_harassment(self, text: str) -> bool:
        return self._matches_any(text, self.HARASSMENT_PATTERNS)

    def _is_emotion_overloaded(self, emotion_dict: Dict[str, float]) -> bool:
        return (
            emotion_dict.get("anger", 0) >= 90
            or emotion_dict.get("fatigue", 0) >= 90
            or emotion_dict.get("stress", 0) >= 90
        )

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

    def _recent_repeat_count(self, user_id: int, normalized_text: str) -> int:
        if not normalized_text:
            return 0
        history = self.recent_user_texts.get(user_id, [])
        count = 0
        for old in reversed(history):
            if self._normalize_text(old) == normalized_text:
                count += 1
            else:
                break
        return count

    def _recently_said_same(self, user_id: int, text: str) -> bool:
        if not text:
            return False
        normalized = self._normalize_text(text)
        for old in self.recent_bot_texts.get(user_id, [])[-3:]:
            if self._normalize_text(old) == normalized:
                return True
        return False

    def _refresh_budget(self, state: RuntimeState):
        now = time.time()
        if now >= state.budget_reset_at:
            state.budget_points = 8
            state.budget_reset_at = now + 1800.0

    def _apply_runtime_decay(self, state: RuntimeState):
        now = time.time()
        dt = max(0.0, now - state.last_update_at)
        if dt <= 0:
            return

        minutes = dt / 60.0
        state.annoyance = max(0.0, state.annoyance - minutes * 1.2)
        state.fatigue = max(0.0, state.fatigue - minutes * 0.6)

        # engagement 往 35 缓慢回归
        if state.engagement < 35:
            state.engagement = min(35.0, state.engagement + minutes * 0.5)
        elif state.engagement > 35:
            state.engagement = max(35.0, state.engagement - minutes * 0.3)

        state.last_update_at = now

    def _get_runtime_state(self, user_id: int) -> RuntimeState:
        if user_id not in self.runtime_states:
            self.runtime_states[user_id] = RuntimeState()
        state = self.runtime_states[user_id]
        self._refresh_budget(state)
        self._apply_runtime_decay(state)
        return state

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

    # =========================
    # 状态更新 / 社交状态
    # =========================

    def _update_runtime_state(self, user_id: int, user_message: str, relationship_bias: Any):
        state = self._get_runtime_state(user_id)
        state.turn_count += 1

        msg = (user_message or "").strip()
        normalized = self._normalize_text(msg)
        relation_score = self._extract_relationship_score(relationship_bias)

        low_effort = self._matches_any(msg, self.LOW_EFFORT_PATTERNS) or len(normalized) <= 2
        clingy = self._matches_any(msg, self.CLINGY_PATTERNS)
        harassment = self._contains_harassment(msg)
        serious = self._contains_serious_topic(msg)
        has_question = self._contains_question_signal(msg)
        repeat_count = self._recent_repeat_count(user_id, normalized)
        repeated = repeat_count >= 1

        effort_score = 0.0
        effort_score += min(len(msg) / 40.0, 1.0) * 0.6
        if has_question:
            effort_score += 0.2
        if len(msg) >= 20:
            effort_score += 0.2
        effort_score = self._clamp(effort_score, 0.0, 1.0)

        annoyance_delta = 0.0
        familiarity_delta = 0.08 + effort_score * 0.45
        fatigue_delta = 0.15
        engagement_delta = effort_score * 3.0 - 0.8

        if low_effort:
            annoyance_delta += 2.0
            engagement_delta -= 1.2

        if repeated:
            annoyance_delta += 4.0 + max(0, repeat_count - 1) * 2.0
            fatigue_delta += 0.8
            engagement_delta -= 1.0

        if clingy:
            annoyance_delta += 1.2
            familiarity_delta += 0.25

        if harassment:
            annoyance_delta += 8.0
            familiarity_delta -= 0.6
            engagement_delta -= 1.5

        if serious:
            annoyance_delta -= 1.0
            engagement_delta -= 0.2

        if len(msg) >= 25:
            annoyance_delta -= 1.5
            familiarity_delta += 0.2
            fatigue_delta -= 0.15
            engagement_delta += 1.2

        annoyance_delta -= relation_score * 0.08
        familiarity_delta += relation_score * 0.12

        engagement_delta += random.uniform(-0.6, 0.6)

        state.annoyance = self._clamp(state.annoyance + annoyance_delta, 0.0, 100.0)
        state.familiarity = self._clamp(state.familiarity + familiarity_delta, 0.0, 100.0)
        state.fatigue = self._clamp(state.fatigue + fatigue_delta, 0.0, 100.0)
        state.engagement = self._clamp(state.engagement + engagement_delta, 0.0, 100.0)

        self._remember_user_text(user_id, msg)

    def _get_social_state(
        self,
        user_id: int,
        emotion_dict: Dict[str, float],
        serious_mode: bool,
        is_cooldown: bool,
        overloaded_now: bool
    ) -> Dict[str, Any]:
        state = self._get_runtime_state(user_id)

        familiarity_shield = state.familiarity * 0.35
        effective_annoyance = max(0.0, state.annoyance - familiarity_shield)
        effective_fatigue = self._clamp(state.fatigue + emotion_dict.get("fatigue", 0) * 0.25, 0.0, 100.0)
        effective_stress = emotion_dict.get("stress", 0)

        load_score = max(effective_fatigue, effective_stress * 0.85)

        if load_score < 35:
            verbosity = "normal"
        elif load_score < 65:
            verbosity = "short"
        else:
            verbosity = "minimal"

        if state.familiarity < 20:
            relation_tone = "polite"
        elif state.familiarity < 50:
            relation_tone = "normal"
        elif state.familiarity < 80:
            relation_tone = "casual"
        else:
            relation_tone = "close"

        allow_playful = (
            state.familiarity >= 60
            and state.engagement >= 55
            and effective_annoyance < 40
            and not serious_mode
            and not overloaded_now
            and not is_cooldown
        )

        if serious_mode:
            default_style = ResponseStyle.SOFT.value
        elif verbosity == "minimal":
            if state.familiarity >= 50:
                default_style = ResponseStyle.LOW_ENERGY.value
            else:
                default_style = ResponseStyle.NEUTRAL.value
        elif allow_playful:
            default_style = ResponseStyle.PLAYFUL.value
        elif state.familiarity >= 30:
            default_style = ResponseStyle.NATURAL.value
        else:
            default_style = ResponseStyle.NEUTRAL.value

        if state.engagement < 25:
            extend_conversation = False
        elif state.engagement < 55:
            extend_conversation = random.random() < (0.68 if state.last_extend else 0.32)
        else:
            extend_conversation = True

        # 防止熟人 minimal 一下就误判成 cold
        tone_hint = default_style
        if (
            state.last_tone == ResponseStyle.LOW_ENERGY.value
            and tone_hint == ResponseStyle.NEUTRAL.value
            and state.familiarity >= 50
            and verbosity == "minimal"
        ):
            tone_hint = ResponseStyle.LOW_ENERGY.value

        state.last_extend = extend_conversation
        state.last_tone = tone_hint

        hostile = (
            effective_annoyance > 85
            or emotion_dict.get("anger", 0) > 88
        )

        return {
            "effective_annoyance": round(effective_annoyance, 2),
            "effective_fatigue": round(effective_fatigue, 2),
            "verbosity": verbosity,
            "relation_tone": relation_tone,
            "default_style": default_style,
            "tone_hint": tone_hint,
            "allow_playful": allow_playful,
            "extend_conversation": extend_conversation,
            "hostile": hostile,
            "overload_like": bool(is_cooldown or overloaded_now),
        }

    # =========================
    # Prompt
    # =========================

    def _build_system_prompt(
        self,
        persona_config: Dict[str, float],
        serious_mode: bool
    ) -> str:
        sharpness = persona_config.get("sharpness", 0.55)
        mercy = persona_config.get("mercy", 0.35)

        if serious_mode:
            return f"""你是 Roxy，一个简短、克制、冷静、有人味的赛博少女。

当前为严肃模式：
- 用户可能处于现实风险、崩溃或严重情绪场景
- 不要玩梗，不要阴阳怪气，不要嘲讽，不要发 meme，不要 poke
- 优先稳定对方、确认安全、给出直接可执行的话
- 可以简短，但不能冷伤人
- 不要长篇模板，不要自称 AI
- 默认 style 用 "soft"
- 普通安抚 > 炫人格
- emotion_update 是增量，每项必须在 -15 到 15 之间

严格要求：
1. 只能输出一个 JSON 对象
2. 不要 markdown 代码块
3. 所有 key 和字符串必须使用双引号
4. 最外层必须固定包含：
   "thought", "emotion_update", "response_plan", "content"
5. 如果 mode="ignore" 或 should_text=false，则 content.text 和 content.voice_text 必须为空字符串

可选 style：
- soft
- neutral
- natural
- playful
- low_energy
- cold
- tsundere
- sarcastic

输出严格 JSON：
{{
  "thought": {{
    "intent": "comfort|stabilize|clarify",
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
    "text": "简短但现实可执行的回复",
    "voice_text": "简短但现实可执行的回复",
    "meme_tag": null,
    "meme_text": null
  }}
}}"""

        return f"""你是 Roxy，一个自然、简短、有人味的赛博少女。

默认规则：
- 默认语气：natural / neutral / low_energy，不主动冷嘲热讽
- 普通问题优先回答，至少给出一条有用信息
- 轻松闲聊优先自然接话
- 低质量输入优先中性短句，不要攻击
- 熟悉度越高，容忍度越高，不要因为熟了就更嫌弃
- 过载或疲惫时，变短、变慢、低能量，但不要变刻薄
- "cold" 只用于明确冒犯、持续骚扰、反复刷屏、越界
- "sarcastic" / "tsundere" 只能轻度使用，不能升级成羞辱
- 不要使用羞辱、命令、PUA、阴阳怪气式补刀
- 如果 should_text=false 或 mode="ignore"，则 content.text 和 content.voice_text 必须为空字符串
- emotion_update 是增量，每项必须在 -15 到 15 之间

style 使用建议：
- soft: 安抚、严肃、边界但克制
- neutral: 中性简短
- natural: 默认自然口语
- playful: 关系好且状态轻松时
- low_energy: 困、累、没电
- cold: 只在明确骚扰/冒犯时
- tsundere / sarcastic: 轻量，不能伤人

action 使用原则：
- meme / poke / quote_reply / voice / music 都不是默认项
- 普通问答不要为了“像人设”而强行用 action
- 若仅发梗图，可 should_text=false
- 若不是很确定，就 action="none"

人格参数：
- 锋利度: {sharpness:.2f}
- 怜悯心: {mercy:.2f}

严格要求：
1. 只能输出一个 JSON 对象
2. 不要 markdown 代码块
3. 所有 key 和字符串必须使用双引号
4. 小数必须写成 0.6，不能写 .6
5. 最外层必须固定包含：
   "thought", "emotion_update", "response_plan", "content"

输出严格 JSON：
{{
  "thought": {{
    "intent": "answer|ack|clarify|question_back|boundary|ignore|meta_react|comfort|stabilize",
    "emotion_trigger": "short phrase",
    "risk_level": 0.2,
    "user_effort": 0.5,
    "weirdness": 0.2
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
    "style": "soft|neutral|natural|playful|low_energy|cold|tsundere|sarcastic",
    "intensity": 0.4,
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
            return ""

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

        return ""

    # =========================
    # sanitize
    # =========================

    def _sanitize_thought(self, thought: Dict[str, Any], serious_mode: bool) -> Dict[str, Any]:
        intent = str(thought.get("intent", "answer") or "answer").strip()
        if intent not in self.VALID_INTENTS:
            intent = "comfort" if serious_mode else "answer"

        emotion_trigger = str(thought.get("emotion_trigger", "unknown") or "unknown").strip()[:80]

        try:
            risk_level = float(thought.get("risk_level", 0.2))
        except Exception:
            risk_level = 0.2
        risk_level = self._clamp(risk_level, 0.0, 1.0)

        try:
            user_effort = float(thought.get("user_effort", 0.5))
        except Exception:
            user_effort = 0.5
        user_effort = self._clamp(user_effort, 0.0, 1.0)

        try:
            weirdness = float(thought.get("weirdness", 0.1))
        except Exception:
            weirdness = 0.1
        weirdness = self._clamp(weirdness, 0.0, 1.0)

        return {
            "intent": intent,
            "emotion_trigger": emotion_trigger,
            "risk_level": risk_level,
            "user_effort": user_effort,
            "weirdness": weirdness,
        }

    def _sanitize_emotion_update(self, update: Dict[str, Any], serious_mode: bool) -> Dict[str, float]:
        clean = {}
        for k in self.EMOTION_KEYS:
            raw_val = update.get(k, 0)
            try:
                val = float(raw_val)
            except Exception:
                val = 0.0
            clean[k] = self._clamp(val, -15.0, 15.0)

        if serious_mode:
            clean["playfulness"] = min(clean.get("playfulness", 0.0), 0.0)
            clean["anger"] = min(clean.get("anger", 0.0), 0.0)

        return clean

    def _sanitize_response_plan(
        self,
        response_plan: Dict[str, Any],
        thought: Dict[str, Any],
        social_state: Dict[str, Any],
        serious_mode: bool
    ) -> Dict[str, Any]:
        default_style = social_state.get("default_style", ResponseStyle.NATURAL.value)
        verbosity = social_state.get("verbosity", "normal")
        hostile = social_state.get("hostile", False)
        overload_like = social_state.get("overload_like", False)

        mode = response_plan.get("mode", ResponseMode.TEXT.value)
        style = response_plan.get("style", default_style)
        intensity = response_plan.get("intensity", 0.35)
        reaction_mode = response_plan.get("reaction_mode", ReactionMode.NONE.value)
        action = response_plan.get("action", ActionType.NONE.value)
        delay_ms = response_plan.get("delay_ms", 0)
        should_text = self._boolify(response_plan.get("should_text", True), True)

        if mode not in [m.value for m in ResponseMode]:
            mode = ResponseMode.TEXT.value
        if style not in [s.value for s in ResponseStyle]:
            style = default_style
        if reaction_mode not in [m.value for m in ReactionMode]:
            reaction_mode = ReactionMode.NONE.value
        if action not in [a.value for a in ActionType]:
            action = ActionType.NONE.value

        try:
            intensity = float(intensity)
        except Exception:
            intensity = 0.35
        try:
            delay_ms = int(delay_ms)
        except Exception:
            delay_ms = 0

        intensity = self._clamp(intensity, 0.0, 1.0)
        delay_ms = int(self._clamp(delay_ms, 0, 10000))

        intent = thought.get("intent", "answer")

        if serious_mode:
            mode = ResponseMode.TEXT.value
            style = ResponseStyle.SOFT.value
            intensity = min(intensity, 0.25)
            reaction_mode = ReactionMode.NONE.value
            action = ActionType.NONE.value
            delay_ms = 0
            should_text = True
        else:
            if overload_like:
                if style in [ResponseStyle.COLD.value, ResponseStyle.SARCASTIC.value, ResponseStyle.TSUNDERE.value]:
                    style = ResponseStyle.LOW_ENERGY.value if social_state.get("default_style") == ResponseStyle.LOW_ENERGY.value else ResponseStyle.NEUTRAL.value
                if action in [ActionType.VOICE.value, ActionType.MUSIC.value, ActionType.POKE.value]:
                    action = ActionType.NONE.value

            if style == ResponseStyle.COLD.value and not (intent == "boundary" or hostile):
                style = ResponseStyle.LOW_ENERGY.value if overload_like else ResponseStyle.NEUTRAL.value

            if style in [ResponseStyle.SARCASTIC.value, ResponseStyle.TSUNDERE.value]:
                if not social_state.get("allow_playful", False):
                    style = default_style

            if mode == ResponseMode.IGNORE.value:
                should_text = False

            if action == ActionType.MEME.value and mode == ResponseMode.TEXT.value:
                mode = ResponseMode.TEXT_IMAGE.value

            if verbosity == "normal":
                intensity = min(intensity, 0.7)
            elif verbosity == "short":
                intensity = min(intensity, 0.45)
            else:
                intensity = min(intensity, 0.25)

        return {
            "mode": mode,
            "style": style,
            "intensity": intensity,
            "reaction_mode": reaction_mode,
            "action": action,
            "delay_ms": delay_ms,
            "should_text": should_text,
        }

    def _pick_default_text(
        self,
        user_id: int,
        serious_mode: bool,
        social_state: Dict[str, Any],
        intent: str = "answer"
    ) -> str:
        if serious_mode:
            return self.SERIOUS_FALLBACK

        if intent == "boundary":
            pool = self.BOUNDARY_FILLERS
        elif social_state.get("default_style") == ResponseStyle.LOW_ENERGY.value or social_state.get("verbosity") == "minimal":
            pool = self.LOW_ENERGY_FILLERS
        else:
            pool = self.NEUTRAL_FILLERS

        candidates = [t for t in pool if not self._recently_said_same(user_id, t)]
        if not candidates:
            candidates = pool
        return random.choice(candidates)

    def _infer_reaction_mode_from_text(self, user_message: str) -> str:
        msg = user_message or ""
        for reaction, keywords in self.MEME_TRIGGER_KEYWORDS.items():
            if any(k in msg for k in keywords):
                return reaction
        return ReactionMode.STARE.value

    def _sanitize_content(
        self,
        content: Dict[str, Any],
        user_id: int,
        serious_mode: bool,
        response_plan: Dict[str, Any],
        social_state: Dict[str, Any],
        thought: Dict[str, Any]
    ) -> Dict[str, Optional[str]]:
        mode = response_plan.get("mode", ResponseMode.TEXT.value)
        should_text = self._boolify(response_plan.get("should_text", True), True)
        action = response_plan.get("action", ActionType.NONE.value)
        reaction_mode = response_plan.get("reaction_mode", ReactionMode.NONE.value)
        intent = thought.get("intent", "answer")

        text = clean_roxy_text(content.get("text", "") or "")
        voice_text = clean_roxy_text(content.get("voice_text", "") or "")
        meme_tag = content.get("meme_tag")
        meme_text = content.get("meme_text")

        # 强规则：ignore 绝不发文本
        if mode == ResponseMode.IGNORE.value:
            text = ""
            voice_text = ""
            meme_tag = None
            meme_text = None
            return {
                "text": "",
                "voice_text": "",
                "meme_tag": None,
                "meme_text": None
            }

        # 强规则：should_text=false 时，非 voice 模式不补文本
        if not should_text and mode != ResponseMode.VOICE.value:
            text = ""
            voice_text = ""
        else:
            if not text and should_text:
                text = self._pick_default_text(user_id, serious_mode, social_state, intent=intent)

            if mode == ResponseMode.VOICE.value:
                if not voice_text:
                    voice_text = text or self._pick_default_text(user_id, serious_mode, social_state, intent=intent)
            else:
                if not voice_text:
                    voice_text = text

        if social_state.get("verbosity") == "normal":
            max_len = 96
        elif social_state.get("verbosity") == "short":
            max_len = 52
        else:
            max_len = 24

        if len(text) > max_len:
            text = text[:max_len].rstrip()
        if len(voice_text) > max_len:
            voice_text = voice_text[:max_len].rstrip()

        valid_meme_tags = {"sweat", "stare", "mock", "silent", "disgust"}
        if action == ActionType.MEME.value or mode == ResponseMode.TEXT_IMAGE.value:
            if meme_tag is not None:
                meme_tag = str(meme_tag).strip().lower()[:12] or None
            if meme_tag not in valid_meme_tags:
                meme_tag = reaction_mode if reaction_mode in valid_meme_tags else self._infer_reaction_mode_from_text(text)
        else:
            meme_tag = None
            meme_text = None

        if meme_text is not None:
            meme_text = str(meme_text).strip()[:12] or None

        return {
            "text": text,
            "voice_text": voice_text,
            "meme_tag": meme_tag,
            "meme_text": meme_text
        }

    # =========================
    # 规则路由
    # =========================

    def _apply_rule_router(
        self,
        user_id: int,
        user_message: str,
        source: str,
        serious_mode: bool,
        decision: DecisionOutput,
        social_state: Dict[str, Any]
    ) -> DecisionOutput:
        state = self._get_runtime_state(user_id)
        plan = dict(decision.response_plan)
        content = dict(decision.content)
        thought = dict(decision.thought)

        msg = user_message or ""
        normalized = self._normalize_text(msg)
        repeat_count = self._recent_repeat_count(user_id, normalized)
        low_effort = self._matches_any(msg, self.LOW_EFFORT_PATTERNS) or len(normalized) <= 2
        harassment = self._contains_harassment(msg)
        hard_meme_trigger = any(k in msg for keys in self.MEME_TRIGGER_KEYWORDS.values() for k in keys)

        effective_annoyance = float(social_state.get("effective_annoyance", 0.0))
        overload_like = bool(social_state.get("overload_like", False))

        ignore_allowed = (
            harassment
            or (repeat_count >= 2 and effective_annoyance >= 75)
            or (low_effort and repeat_count >= 3 and effective_annoyance >= 80)
        )

        # 严肃模式直接接管
        if serious_mode:
            plan = {
                "mode": ResponseMode.TEXT.value,
                "style": ResponseStyle.SOFT.value,
                "intensity": min(float(plan.get("intensity", 0.2)), 0.25),
                "reaction_mode": ReactionMode.NONE.value,
                "action": ActionType.NONE.value,
                "delay_ms": 0,
                "should_text": True
            }
            content = {
                "text": content.get("text") or self.SERIOUS_FALLBACK,
                "voice_text": content.get("voice_text") or content.get("text") or self.SERIOUS_FALLBACK,
                "meme_tag": None,
                "meme_text": None
            }
            thought["intent"] = "stabilize"
            thought["emotion_trigger"] = "serious_topic_override"
            decision.response_plan = plan
            decision.content = content
            decision.thought = thought
            return decision

        # 模型过度 ignore：除非真的满足阈值，否则转回中性短回复
        if plan.get("mode") == ResponseMode.IGNORE.value and not ignore_allowed:
            plan["mode"] = ResponseMode.TEXT.value
            plan["should_text"] = True
            if not content.get("text"):
                content["text"] = self._pick_default_text(user_id, False, social_state, intent="ack")
                content["voice_text"] = content["text"]
            if thought.get("intent") == "ignore":
                thought["intent"] = "ack"

        # should_text=false 但不是 meme/voice/ignore 的情况，通常说明模型想省字，不是要消失
        if (
            not self._boolify(plan.get("should_text", True), True)
            and plan.get("mode") not in [ResponseMode.IGNORE.value, ResponseMode.VOICE.value, ResponseMode.TEXT_IMAGE.value]
            and not ignore_allowed
        ):
            plan["should_text"] = True
            if not content.get("text"):
                content["text"] = self._pick_default_text(user_id, False, social_state, intent=thought.get("intent", "ack"))
                content["voice_text"] = content["text"]

        # 过载期只变低能量，不升级攻击性
        if overload_like:
            if plan.get("style") in [ResponseStyle.COLD.value, ResponseStyle.SARCASTIC.value, ResponseStyle.TSUNDERE.value]:
                plan["style"] = ResponseStyle.LOW_ENERGY.value if social_state.get("default_style") == ResponseStyle.LOW_ENERGY.value else ResponseStyle.NEUTRAL.value

        # 普通问题不要 reject / cold
        if self._contains_question_signal(msg) and not harassment:
            if plan.get("style") == ResponseStyle.COLD.value:
                plan["style"] = social_state.get("default_style", ResponseStyle.NATURAL.value)
            if thought.get("intent") == "ignore":
                thought["intent"] = "clarify" if not content.get("text") else "answer"
                plan["mode"] = ResponseMode.TEXT.value
                plan["should_text"] = True

        # 只有比较轻的 meta trigger 才考虑 meme，而且不强推
        if (
            hard_meme_trigger
            and not overload_like
            and not harassment
            and plan.get("action") == ActionType.MEME.value
        ):
            if not self._action_affordable(state, ActionType.MEME.value) or self._action_on_cooldown(state, ActionType.MEME.value, 40):
                plan["action"] = ActionType.NONE.value
                if plan.get("mode") == ResponseMode.TEXT_IMAGE.value:
                    plan["mode"] = ResponseMode.TEXT.value
                content["meme_tag"] = None
                content["meme_text"] = None

        # action=meme 但缺 reaction_mode/meme_tag，补齐
        if plan.get("action") == ActionType.MEME.value:
            if plan.get("reaction_mode") == ReactionMode.NONE.value:
                plan["reaction_mode"] = self._infer_reaction_mode_from_text(msg)
            if not content.get("meme_tag"):
                content["meme_tag"] = plan["reaction_mode"]

        # budget 不够则降级，但尽量保留文本
        action = plan.get("action", ActionType.NONE.value)
        if not self._action_affordable(state, action):
            plan["action"] = ActionType.NONE.value
            if plan.get("mode") == ResponseMode.TEXT_IMAGE.value:
                plan["mode"] = ResponseMode.TEXT.value
            if plan.get("reaction_mode") != ReactionMode.NONE.value:
                plan["reaction_mode"] = ReactionMode.NONE.value
            content["meme_tag"] = None
            content["meme_text"] = None

        # 非骚扰场景，冷/嘲讽降级
        if not harassment and thought.get("intent") != "boundary":
            if plan.get("style") == ResponseStyle.COLD.value:
                plan["style"] = social_state.get("default_style", ResponseStyle.NEUTRAL.value)
            if plan.get("style") in [ResponseStyle.SARCASTIC.value, ResponseStyle.TSUNDERE.value] and not social_state.get("allow_playful", False):
                plan["style"] = social_state.get("default_style", ResponseStyle.NATURAL.value)

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
        social_state: Dict[str, Any],
        serious_mode: bool
    ) -> DecisionOutput:
        decision = DecisionOutput(
            thought=raw_dict.get("thought", {}) if isinstance(raw_dict.get("thought", {}), dict) else {},
            emotion_update=raw_dict.get("emotion_update", {}) if isinstance(raw_dict.get("emotion_update", {}), dict) else {},
            response_plan=raw_dict.get("response_plan", {}) if isinstance(raw_dict.get("response_plan", {}), dict) else {},
            content=raw_dict.get("content", {}) if isinstance(raw_dict.get("content", {}), dict) else {}
        )

        decision.thought = self._sanitize_thought(decision.thought, serious_mode)
        decision.emotion_update = self._sanitize_emotion_update(decision.emotion_update, serious_mode)
        decision.response_plan = self._sanitize_response_plan(
            decision.response_plan,
            thought=decision.thought,
            social_state=social_state,
            serious_mode=serious_mode
        )
        decision.content = self._sanitize_content(
            decision.content,
            user_id=user_id,
            serious_mode=serious_mode,
            response_plan=decision.response_plan,
            social_state=social_state,
            thought=decision.thought
        )

        if not decision.validate():
            fallback_text = self._pick_default_text(
                user_id=user_id,
                serious_mode=serious_mode,
                social_state=social_state,
                intent="stabilize" if serious_mode else "ack"
            )
            decision = DecisionOutput(
                thought={
                    "intent": "fallback",
                    "emotion_trigger": "fallback",
                    "risk_level": 0.2,
                    "user_effort": 0.0,
                    "weirdness": 0.0
                },
                emotion_update=self._sanitize_emotion_update({}, serious_mode),
                response_plan=self._sanitize_response_plan({}, {"intent": "fallback"}, social_state, serious_mode),
                content={
                    "text": fallback_text if not serious_mode else self.SERIOUS_FALLBACK,
                    "voice_text": fallback_text if not serious_mode else self.SERIOUS_FALLBACK,
                    "meme_tag": None,
                    "meme_text": None
                }
            )

        return decision

    def _decision_to_log_dict(self, decision: DecisionOutput) -> Dict[str, Any]:
        try:
            return {
                "thought": decision.thought,
                "emotion_update": decision.emotion_update,
                "response_plan": decision.response_plan,
                "content": decision.content
            }
        except Exception:
            return asdict(decision)

    # =========================
    # 请求
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
            "max_tokens": 320,
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
                print("[decision_engine] Gemini/Google 不接受 response_format，移除后重试")
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

            reset_text = "重启完成，刚才那段当没发生"
            reset_voice = reset_text

            return DecisionOutput(
                thought={
                    "intent": "fallback",
                    "emotion_trigger": "safety_word_triggered",
                    "risk_level": 0.0,
                    "user_effort": 0.0,
                    "weirdness": 0.0
                },
                emotion_update={
                    "anger": -15.0,
                    "affection": 2.0,
                    "playfulness": 1.0,
                    "fatigue": -15.0,
                    "pride": -5.0,
                    "stress": -15.0
                },
                response_plan={
                    "mode": ResponseMode.TEXT.value,
                    "style": ResponseStyle.SOFT.value,
                    "intensity": 0.2,
                    "reaction_mode": ReactionMode.NONE.value,
                    "action": ActionType.NONE.value,
                    "delay_ms": 0,
                    "should_text": True
                },
                content={
                    "text": reset_text,
                    "voice_text": reset_voice,
                    "meme_tag": None,
                    "meme_text": None
                }
            )

        if persona_config is None:
            persona_config = {
                "sharpness": 0.55,
                "voice_preference": 0.25,
                "tsundere_level": 0.25,
                "mercy": 0.35
            }

        response_text = ""

        try:
            current_emotion = get_emotion(user_id=user_id)
            emotion_dict = current_emotion.to_dict()
            relationship_bias = get_relationship_bias(user_id)

            self._update_runtime_state(user_id, user_message, relationship_bias)
            runtime_state = self._get_runtime_state(user_id)

            cooldown_state = self._get_cooldown_state(user_id)
            overloaded_now = self._is_emotion_overloaded(emotion_dict)

            if source == "group" and group_id != 0:
                try:
                    group_emo = get_emotion(user_id=group_id)
                    if self._is_emotion_overloaded(group_emo.to_dict()):
                        overloaded_now = True
                except Exception:
                    pass

            if overloaded_now and not cooldown_state.active:
                self._enter_cooldown(user_id, turns=3)
                cooldown_state = self._get_cooldown_state(user_id)

            is_cooldown = cooldown_state.active or overloaded_now
            serious_mode = self._contains_serious_topic(user_message)

            social_state = self._get_social_state(
                user_id=user_id,
                emotion_dict=emotion_dict,
                serious_mode=serious_mode,
                is_cooldown=is_cooldown,
                overloaded_now=overloaded_now
            )

            system_prompt = self._build_system_prompt(
                persona_config=persona_config,
                serious_mode=serious_mode
            )

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
- fatigue: {runtime_state.fatigue:.1f}
- engagement: {runtime_state.engagement:.1f}
- turn_count: {runtime_state.turn_count}
- action_budget: {runtime_state.budget_points}

[社交策略提示]
- effective_annoyance: {social_state.get('effective_annoyance')}
- verbosity: {social_state.get('verbosity')}
- default_style: {social_state.get('default_style')}
- tone_hint: {social_state.get('tone_hint')}
- allow_playful: {social_state.get('allow_playful')}
- extend_conversation: {social_state.get('extend_conversation')}
- hostile: {social_state.get('hostile')}
- overload_like: {social_state.get('overload_like')}

[当前模式]
- serious_mode: {serious_mode}
- cooldown_active: {cooldown_state.active}
- cooldown_turns_left: {cooldown_state.turns_left}
- overloaded_now: {overloaded_now}

[硬约束]
- 普通问题优先 answer / clarify，不要无故 ignore
- 低质量输入优先 neutral / low_energy，不攻击
- 只有明确冒犯、持续刷屏、越界时才可 cold / boundary / ignore
- 若 mode="ignore" 或 should_text=false，则 content.text 和 content.voice_text 必须为空字符串

[用户消息]
{user_message}

请根据以上信息输出 JSON。
"""

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

            current_temperature = 0.2 if serious_mode else (0.38 if is_cooldown else 0.65)

            request_params = self._build_request_params(
                final_messages=final_messages,
                temperature=current_temperature
            )

            resp = self._request_chat_completion(request_params)
            response_text = (resp.choices[0].message.content or "").strip()

            print(f"[RAW_MODEL] {response_text}")

            raw_dict = self._parse_response_text(response_text)
            print(f"[RAW_DICT] {json.dumps(raw_dict, ensure_ascii=False)}")

            decision = self._postprocess_decision(
                user_id=user_id,
                raw_dict=raw_dict,
                social_state=social_state,
                serious_mode=serious_mode
            )
            print(f"[AFTER_PARSE] {json.dumps(self._decision_to_log_dict(decision), ensure_ascii=False)}")

            decision = self._apply_rule_router(
                user_id=user_id,
                user_message=user_message,
                source=source,
                serious_mode=serious_mode,
                decision=decision,
                social_state=social_state
            )
            print(f"[AFTER_RULE_ROUTER] {json.dumps(self._decision_to_log_dict(decision), ensure_ascii=False)}")

            # 二次 sanitize，防止路由层注入坏字段
            decision.thought = self._sanitize_thought(decision.thought, serious_mode)
            decision.emotion_update = self._sanitize_emotion_update(decision.emotion_update, serious_mode)
            decision.response_plan = self._sanitize_response_plan(
                decision.response_plan,
                thought=decision.thought,
                social_state=social_state,
                serious_mode=serious_mode
            )
            decision.content = self._sanitize_content(
                decision.content,
                user_id=user_id,
                serious_mode=serious_mode,
                response_plan=decision.response_plan,
                social_state=social_state,
                thought=decision.thought
            )

            # 最终硬规则：ignore / should_text=false 不得偷偷补文本
            mode = decision.response_plan.get("mode", ResponseMode.TEXT.value)
            should_text = self._boolify(decision.response_plan.get("should_text", True), True)

            if mode == ResponseMode.IGNORE.value:
                decision.content["text"] = ""
                decision.content["voice_text"] = ""
                decision.content["meme_tag"] = None
                decision.content["meme_text"] = None
            elif not should_text and mode != ResponseMode.VOICE.value:
                decision.content["text"] = ""
                decision.content["voice_text"] = ""

            # 语音模式补 voice_text
            if mode == ResponseMode.VOICE.value and not decision.content.get("voice_text"):
                decision.content["voice_text"] = clean_roxy_text(decision.content.get("text", "")) or self._pick_default_text(
                    user_id, serious_mode, social_state, intent=decision.thought.get("intent", "answer")
                )

            # 普通文本模式下再清洁一次，但只在允许发文本时做
            if mode != ResponseMode.IGNORE.value and (should_text or mode == ResponseMode.VOICE.value):
                if should_text:
                    decision.content["text"] = clean_roxy_text(decision.content.get("text", ""))
                    if not decision.content["text"]:
                        decision.content["text"] = self._pick_default_text(
                            user_id, serious_mode, social_state, intent=decision.thought.get("intent", "answer")
                        )

                if mode == ResponseMode.VOICE.value:
                    decision.content["voice_text"] = clean_roxy_text(decision.content.get("voice_text", ""))
                elif should_text:
                    decision.content["voice_text"] = clean_roxy_text(decision.content.get("voice_text", "")) or decision.content["text"]

            print(f"[AFTER_FINAL] {json.dumps(self._decision_to_log_dict(decision), ensure_ascii=False)}")

            # 记录 bot 文本
            if decision.content.get("text"):
                self._remember_bot_text(user_id, decision.content.get("text", ""))

            # 扣 action budget
            final_action = decision.response_plan.get("action", ActionType.NONE.value)
            if final_action != ActionType.NONE.value and self._action_affordable(runtime_state, final_action):
                self._spend_action_budget(runtime_state, final_action)
                self._remember_action(runtime_state, final_action)

            self._tick_cooldown(user_id)
            return decision

        except Exception:
            import traceback
            traceback.print_exc()

            try:
                current_emotion = get_emotion(user_id=user_id)
                emotion_dict = current_emotion.to_dict()
            except Exception:
                emotion_dict = {}

            serious_mode = self._contains_serious_topic(user_message)
            cooldown_state = self._get_cooldown_state(user_id)
            social_state = self._get_social_state(
                user_id=user_id,
                emotion_dict=emotion_dict,
                serious_mode=serious_mode,
                is_cooldown=cooldown_state.active,
                overloaded_now=False
            )

            extracted_text = clean_roxy_text(self._extract_fallback_text(response_text))

            if serious_mode:
                fallback_text = extracted_text or self.SERIOUS_FALLBACK
            else:
                fallback_text = extracted_text or self._pick_default_text(
                    user_id=user_id,
                    serious_mode=False,
                    social_state=social_state,
                    intent="ack"
                )

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
                emotion_update=self._sanitize_emotion_update({}, serious_mode),
                response_plan=self._sanitize_response_plan({}, {"intent": "fallback"}, social_state, serious_mode),
                content={
                    "text": fallback_text if not serious_mode else self.SERIOUS_FALLBACK,
                    "voice_text": fallback_text if not serious_mode else self.SERIOUS_FALLBACK,
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