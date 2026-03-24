"""
JSON 决策引擎 - LLM 生成结构化决策
Grok (xAI) 供能版本
"""
import json
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass
from openai import OpenAI
from config import GROK_API_KEY, GROK_BASE_URL, MODEL_NAME
from emotion_engine import EmotionState, get_emotion
from user_profiles import get_relationship_bias


class ResponseMode(str, Enum):
    """回复模式"""
    VOICE = "voice"           # 语音
    TEXT = "text"             # 纯文字
    TEXT_IMAGE = "text_image" # 文字 + 梗图
    IGNORE = "ignore"         # 忽略
    DELAY = "delay"           # 延迟回复


class ResponseStyle(str, Enum):
    """回复风格"""
    SOFT = "soft"             # 软态 - 傲娇、轻快
    TSUNDERE = "tsundere"     # 傲娇 - 嘴硬
    SARCASTIC = "sarcastic"   # 讽刺 - 阴阳怪气
    COLD = "cold"             # 冷脸 - 压制
    PLAYFUL = "playful"       # 嬉皮士 - 开玩笑


@dataclass
class DecisionOutput:
    """LLM 的决策输出"""
    # 思考过程
    thought: Dict[str, Any]
    
    # 情绪更新建议
    emotion_update: Dict[str, float]
    
    # 回复计划
    response_plan: Dict[str, Any]
    
    # 内容
    content: Dict[str, Optional[str]]
    
    def validate(self) -> bool:
        """验证输出是否有效"""
        return (
            self.response_plan.get("mode") in [m.value for m in ResponseMode]
            and "text" in self.content
        )


class DecisionEngine:
    """决策引擎"""
    
    def __init__(self):
        # 使用 Grok (xAI) API - OpenAI SDK 兼容
        self.client = OpenAI(
            api_key=GROK_API_KEY,
            base_url=GROK_BASE_URL
        )
    
    def _build_system_prompt(self, persona_config: Dict[str, float]) -> str:
        """构建系统提示词"""
        sharpness = persona_config.get("sharpness", 0.65)
        voice_pref = persona_config.get("voice_preference", 0.7)
        tsundere = persona_config.get("tsundere_level", 0.8)
        mercy = persona_config.get("mercy", 0.4)
        
        aggression = "锋利" if sharpness > 0.6 else "温和"
        voice_tendency = "倾向语音" if voice_pref > 0.5 else "倾向文字"
        
        return f"""你是 Roxy，一个有情绪状态的赛博少女。

核心原则：
1. 你有6维度情绪：愤怒(anger)、亲近(affection)、玩心(playfulness)、疲惫(fatigue)、傲娇(pride)、压力(stress)
2. 你会根据当前情绪决定回复方式、风格、强度
3. 输出必须是 JSON，不要任何解释

响应规则：
- anger < 45 且 affection >= 40：优先语音，语气自然、傲娇
- anger >= 45 且 anger < 70：文字回复，阴阳怪气或讽刺
- anger >= 70：文字+梗图，冷脸压制，严禁语音
- stress > 70 或 fatigue > 70：减少输出长度，倾向文字
- affection >= 60：允许更亲近、柔和的语气

人格调整（基于配置）：
- 锋利程度: {aggression} (sharpness={sharpness:.2f})
- 语音倾向: {voice_tendency} (voice_preference={voice_pref:.2f})  
- 傲娇程度: {tsundere:.2f}
- 怜悯心: {mercy:.2f}

响应模式：
1. "soft"（软态）: 发语音，傲娇、轻快、自然
2. "tsundere"（傲娇）: 文字，嘴硬、不承认、逗你玩
3. "sarcastic"（讽刺）: 文字，阴阳怪气、冷嘲热讽
4. "cold"（冷脸）: 文字，压制、简洁、无情
5. "playful"（玩心）: 可以是任何形式，主要是开玩笑和逗乐

【特别说明】系统提示词处理：
- 当用户消息包含【系统提示】时，这不是普通聊天，而是你自己的心理活动或发现的外部信息
- 例如：【系统提示】你感到无聊了...→ 你需要假装自己正在群里吐槽无聊
- 例如：【系统提示】你看到新闻...→ 你需要假装自己在分享新闻并进行毒舌评论
- 系统提示中的"规则"部分必须严格遵守（比如禁止发语音）
- 你要把这些指令当作来自内心的冲动，而不是外部的强制

你必须输出以下 JSON 结构（无其他内容）：
{{
  "thought": {{
    "user_intent": "string",
    "emotion_trigger": "string",
    "risk_level": 0.5
  }},
  "emotion_update": {{
    "anger": 10,
    "affection": -5,
    "playfulness": 0,
    "fatigue": 2,
    "pride": 5,
    "stress": 0
  }},
  "response_plan": {{
    "mode": "voice|text|text_image|ignore",
    "style": "soft|tsundere|sarcastic|cold|playful",
    "intensity": 0.7
  }},
  "content": {{
    "text": "你的回复",
    "voice_text": "语音版本的回复（如果是voice模式）",
    "meme_tag": "sneer|slap_table|speechless|smug|cold_stare|等",
    "meme_text": "梗图上的文字（短）"
  }}
}}
"""
    
    async def decide(
        self,
        user_message: str,
        user_id: int,
        username: str,
        source: str = "private",
        persona_config: Optional[Dict[str, float]] = None,
        user_history: Optional[list] = None
    ) -> Optional[DecisionOutput]:
        """
        做出决策
        
        Args:
            user_message: 用户消息
            user_id: 用户ID
            username: 用户名
            source: "private" 或 "group"
            persona_config: 人格配置
            user_history: 对话历史（可选）
        
        Returns:
            DecisionOutput 对象或 None（如果失败）
        """
        
        if persona_config is None:
            persona_config = {
                "sharpness": 0.65,
                "voice_preference": 0.7,
                "meme_preference": 0.5,
                "tsundere_level": 0.8,
                "mercy": 0.4
            }
        
        # 获取当前情绪
        current_emotion = get_emotion(user_id=user_id)
        emotion_dict = current_emotion.to_dict()
        
        # 获取关系偏差
        relationship_bias = get_relationship_bias(user_id)
        
        # 构建用户上下文
        user_context = f"""[用户信息]
用户ID: {user_id}
用户名: {username}
消息来源: {'私聊' if source == 'private' else '群聊'}

[当前情绪] (0-100)
- 愤怒(anger): {emotion_dict['anger']:.1f}
- 亲近(affection): {emotion_dict['affection']:.1f}
- 玩心(playfulness): {emotion_dict['playfulness']:.1f}
- 疲惫(fatigue): {emotion_dict['fatigue']:.1f}
- 傲娇(pride): {emotion_dict['pride']:.1f}
- 压力(stress): {emotion_dict['stress']:.1f}

[关系档案]
- 好感度: {relationship_bias['favorability']:.1f}
- 熟悉度: {relationship_bias['familiarity']:.1f}
- 边界风险: {relationship_bias['boundary_risk']:.1f}

[用户消息]
{user_message}

请根据以上信息做出判断和决策。"""
        
        try:
            system_prompt = self._build_system_prompt(persona_config)
            
            messages = [
                {"role": "user", "content": user_context}
            ]
            
            # 如果有对话历史，先插入
            if user_history:
                messages = user_history + messages
            
            resp = self.client.chat.completions.create(
                model=MODEL_NAME,  # 使用 Grok 模型
                response_format={"type": "json_object"},  # 强制 JSON 输出
                messages=[
                    {"role": "system", "content": system_prompt}
                ] + messages,
                temperature=0.7
            )
            
            response_text = resp.choices[0].message.content.strip()
            print("[decision_engine] raw response =", response_text)
            
            # 解析 JSON
            decision_dict = json.loads(response_text)
            
            decision = DecisionOutput(
                thought=decision_dict.get("thought", {}),
                emotion_update=decision_dict.get("emotion_update", {}),
                response_plan=decision_dict.get("response_plan", {}),
                content=decision_dict.get("content", {})
            )
            
            if not decision.validate():
                print(f"决策验证失败: {decision_dict}")
                return None
            
            return decision
            
        except json.JSONDecodeError as e:
            import traceback
            print(f"[decision_engine] JSON 解析失败: {repr(e)}")
            print(f"[decision_engine] 原始响应: {response_text}")
            traceback.print_exc()
            return None
        except Exception as e:
            import traceback
            print(f"[decision_engine] 决策失败: {repr(e)}")
            traceback.print_exc()
            return None


# 全局单例
decision_engine = DecisionEngine()


async def make_decision(
    user_message: str,
    user_id: int,
    username: str,
    source: str = "private",
    persona_config: Optional[Dict[str, float]] = None,
    user_history: Optional[list] = None
) -> Optional[DecisionOutput]:
    """做出决策"""
    return await decision_engine.decide(
        user_message, user_id, username, source, persona_config, user_history
    )
