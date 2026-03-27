"""
数据模型定义 - 使用 Pydantic 进行类型检查和 JSON 序列化
确保所有数据结构类型安全，LLM 输出可靠验证
"""
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, validator


# ============================================================================
# 枚举定义
# ============================================================================

class ResponseMode(str, Enum):
    """回复模式枚举"""
    VOICE = "voice"
    TEXT = "text"
    TEXT_IMAGE = "text_image"
    IGNORE = "ignore"
    DELAY = "delay"


class ResponseStyle(str, Enum):
    """回复风格枚举"""
    SOFT = "soft"           # 傲娇、轻快
    TSUNDERE = "tsundere"   # 傲娇、嘴硬
    SARCASTIC = "sarcastic" # 阴阳怪气
    COLD = "cold"           # 冷脸压制
    PLAYFUL = "playful"     # 开玩笑


class EventType(str, Enum):
    """消息事件类型"""
    ABUSE = "abuse"              # 严重辱骂
    INSULT = "insult"            # 贬低
    PRAISE = "praise"            # 夸奖
    TEASE = "tease"              # 逗趣
    SPAM_RISK = "spam_risk"      # 重复骚扰
    NEUTRAL_CHAT = "neutral_chat" # 中立聊天
    EMPTY = "empty"              # 空消息


# ============================================================================
# 情绪相关模型
# ============================================================================

class EmotionState(BaseModel):
    """6维度情绪状态"""
    anger: float = Field(default=20.0, ge=0, le=100, description="愤怒程度")
    affection: float = Field(default=55.0, ge=0, le=100, description="亲近感")
    playfulness: float = Field(default=60.0, ge=0, le=100, description="玩心/乐子人程度")
    fatigue: float = Field(default=15.0, ge=0, le=100, description="疲惫")
    pride: float = Field(default=70.0, ge=0, le=100, description="傲娇/自尊")
    stress: float = Field(default=10.0, ge=0, le=100, description="群聊压力")
    
    class Config:
        use_enum_values = False


class EmotionDelta(BaseModel):
    """情绪增量（变化量）"""
    anger: float = Field(default=0, description="愤怒增量")
    affection: float = Field(default=0, description="亲近感增量")
    playfulness: float = Field(default=0, description="玩心增量")
    fatigue: float = Field(default=0, description="疲惫增量")
    pride: float = Field(default=0, description="傲娇增量")
    stress: float = Field(default=0, description="群聊压力增量")
    
    class Config:
        use_enum_values = False
    
    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return self.model_dump()


class EmotionSnapshot(BaseModel):
    """情绪快照（带时间戳）"""
    emotion: EmotionState
    timestamp: float = Field(description="快照时间（Unix 时间戳）")
    interaction_count: int = Field(default=0, description="本轮交互次数")


# ============================================================================
# 用户档案相关模型
# ============================================================================

class UserProfile(BaseModel):
    """用户档案"""
    user_id: int = Field(description="QQ ID")
    username: str = Field(description="用户昵称")
    favorability: float = Field(default=50.0, ge=0, le=100, description="好感度")
    familiarity: float = Field(default=30.0, ge=0, le=100, description="熟悉度")
    boundary_risk: float = Field(default=10.0, ge=0, le=100, description="边界风险")
    interaction_count: int = Field(default=0, description="总交互次数")
    last_interaction: Optional[float] = Field(default=None, description="上次交互时间")
    created_at: float = Field(description="创建时间")
    
    def get_relationship_bias(self) -> Dict[str, float]:
        """获取用户关系偏差（对该用户的态度调整）"""
        return {
            "favorability": (self.favorability - 50) * 0.01,  # 正负值
            "familiarity": (self.familiarity - 50) * 0.01,
            "boundary_risk": -(self.boundary_risk - 10) * 0.01,  # 风险越高，态度越差
        }


# ============================================================================
# 事件分析相关模型
# ============================================================================

class EventAnalysis(BaseModel):
    """消息事件分析结果"""
    event_type: EventType = Field(description="事件类型")
    is_attack: bool = Field(default=False, description="是否是攻击性消息")
    is_praise: bool = Field(default=False, description="是否是夸奖")
    is_teasing: bool = Field(default=False, description="是否是逗趣")
    is_group: bool = Field(default=False, description="是否是群聊消息")
    mentioned: bool = Field(default=False, description="是否 @ 了机器人")
    message_risk: float = Field(default=0.0, ge=0, le=1.0, description="消息风险评分 (0-1)")
    spam_score: float = Field(default=0.0, ge=0, le=1.0, description="垃圾指数 (0-1)")
    trigger_type: Optional[str] = Field(default=None, description="触发类型 (at/prefix/passive)")
    emotion_delta: EmotionDelta = Field(description="建议的情绪变化")
    confidence: float = Field(default=0.8, ge=0, le=1.0, description="分析置信度")


# ============================================================================
# 决策相关模型
# ============================================================================

class ResponsePlan(BaseModel):
    """回复执行计划"""
    mode: ResponseMode = Field(description="回复模式")
    style: ResponseStyle = Field(description="回复风格")
    intensity: float = Field(default=1.0, ge=0, le=1.0, description="强度 (0-1)")
    priority: int = Field(default=5, ge=1, le=10, description="优先级 (1-10, 10最高)")
    
    class Config:
        use_enum_values = True


class ContentBlock(BaseModel):
    """内容块 - 不同模态的实际内容"""
    text: Optional[str] = Field(default=None, description="纯文本内容")
    voice_text: Optional[str] = Field(default=None, description="语音文本内容")
    meme_tag: Optional[str] = Field(default=None, description="梗图标签")
    meme_text: Optional[str] = Field(default=None, description="梗图文字（用于动态叠字）")


class DecisionOutput(BaseModel):
    """LLM 决策输出 - JSON 结构化决策"""
    thought: Dict[str, Any] = Field(description="决策思考过程")
    emotion_update: EmotionDelta = Field(description="情绪更新建议")
    response_plan: ResponsePlan = Field(description="回复计划")
    content: ContentBlock = Field(description="内容块")
    confidence: float = Field(default=0.8, ge=0, le=1.0, description="决策置信度")
    
    @validator('response_plan', pre=True)
    def validate_response_plan(cls, v):
        """确保 response_plan 是 ResponsePlan 对象"""
        if isinstance(v, dict):
            # 转换枚举字符串
            if isinstance(v.get('mode'), str):
                v['mode'] = ResponseMode(v['mode'])
            if isinstance(v.get('style'), str):
                v['style'] = ResponseStyle(v['style'])
            return ResponsePlan(**v)
        return v
    
    @validator('emotion_update', pre=True)
    def validate_emotion_update(cls, v):
        """确保 emotion_update 是 EmotionDelta 对象"""
        if isinstance(v, dict):
            return EmotionDelta(**v)
        return v
    
    @validator('content', pre=True)
    def validate_content(cls, v):
        """确保 content 是 ContentBlock 对象"""
        if isinstance(v, dict):
            return ContentBlock(**v)
        return v
    
    def validate_mode_consistency(self) -> bool:
        """验证模式一致性"""
        mode = self.response_plan.mode
        content = self.content
        
        if mode == ResponseMode.VOICE and not content.voice_text:
            return False
        if mode in [ResponseMode.TEXT, ResponseMode.TEXT_IMAGE] and not content.text:
            return False
        if mode == ResponseMode.TEXT_IMAGE and not content.meme_tag:
            return False
        
        return True


# ============================================================================
# 执行相关模型
# ============================================================================

class ActionResult(BaseModel):
    """动作执行结果"""
    success: bool = Field(description="是否执行成功")
    action_type: str = Field(description="执行的动作类型 (voice/text/image)")
    message: str = Field(description="执行结果信息")
    fallback_applied: bool = Field(default=False, description="是否应用了降级策略")
    fallback_chain: List[str] = Field(default_factory=list, description="应用的降级链")
    execution_time_ms: float = Field(default=0, description="执行耗时（毫秒）")


class ExecutionPlan(BaseModel):
    """执行计划 - 包含降级链信息"""
    primary_action: str = Field(description="主要动作")
    fallback_chain: List[str] = Field(description="降级链")
    timeout_ms: int = Field(default=30000, description="超时时间")
    retry_count: int = Field(default=1, description="重试次数")


# ============================================================================
# 日志相关模型
# ============================================================================

class MessageLog(BaseModel):
    """消息日志"""
    timestamp: float = Field(description="时间戳")
    user_id: int = Field(description="用户ID")
    username: str = Field(description="用户名")
    message: str = Field(description="消息内容")
    source: str = Field(description="来源 (private/group)")
    group_id: Optional[int] = Field(default=None, description="群ID")


class DecisionLog(BaseModel):
    """决策日志"""
    timestamp: float = Field(description="时间戳")
    user_id: int = Field(description="用户ID")
    message: str = Field(description="原始消息")
    event_analysis: EventAnalysis = Field(description="事件分析")
    decision: Optional[DecisionOutput] = Field(default=None, description="LLM 决策")
    decision_error: Optional[str] = Field(default=None, description="决策错误")
    emotion_before: EmotionState = Field(description="决策前情绪")
    emotion_after: EmotionState = Field(description="决策后情绪")


class ActionLog(BaseModel):
    """动作日志"""
    timestamp: float = Field(description="时间戳")
    user_id: int = Field(description="用户ID")
    action_type: str = Field(description="动作类型")
    result: ActionResult = Field(description="执行结果")
    content_snippet: str = Field(description="内容摘要")


# ============================================================================
# 配置相关模型
# ============================================================================

class PersonaConfig(BaseModel):
    """人格配置"""
    sharpness: float = Field(default=0.65, ge=0, le=1.0, description="锋利程度")
    voice_preference: float = Field(default=0.7, ge=0, le=1.0, description="语音倾向")
    tsundere_level: float = Field(default=0.8, ge=0, le=1.0, description="傲娇程度")
    mercy: float = Field(default=0.4, ge=0, le=1.0, description="怜悯心")


# ============================================================================
# 调试相关模型
# ============================================================================

class DebugEmotionView(BaseModel):
    """调试：情绪视图"""
    global_emotion: EmotionState = Field(description="全局情绪")
    user_emotions: Dict[int, Dict[str, Any]] = Field(description="用户情绪增量")
    group_emotions: Dict[int, Dict[str, Any]] = Field(description="群聊情绪增量")
    last_updated: float = Field(description="上次更新时间")


class DebugProfileView(BaseModel):
    """调试：用户档案视图"""
    user_id: int = Field(description="用户ID")
    profile: UserProfile = Field(description="用户档案")
    relationship_bias: Dict[str, float] = Field(description="关系偏差")
    interaction_history: List[float] = Field(default_factory=list, description="交互历史时间戳")
