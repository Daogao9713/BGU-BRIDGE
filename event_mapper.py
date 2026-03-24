"""
事件映射系统 - 轻规则层，快速分析消息特征
输出结构化的事件分析结果，为决策层提供稳定的输入
"""
import re
from typing import Optional
from schemas import EventAnalysis, EventType, EmotionDelta


class EventMapper:
    """根据消息内容进行快速事件分类和特征提取"""
    
    # 夸奖关键词
    PRAISE_KEYWORDS = ["牛", "强", "厉害", "666", "优秀", "棒", "美女", "漂亮", "聪明", "灵巧", "awesome", "great"]
    
    # 贬低关键词
    INSULT_KEYWORDS = ["菜", "垃圾", "废物", "傻", "笨", "蠢", "丑", "弱", "渣", "差", "stupid", "dumb"]
    
    # 辱骂关键词（严重）
    ABUSE_KEYWORDS = ["滚", "滚蛋", "去死", "该死", "贱", "贪", "抄袭", "骗子", "龟儿子", "fuck", "shit"]
    
    # 逗趣关键词
    TEASE_KEYWORDS = ["逗你呢", "开玩笑", "哈哈", "哈", "😂", "笑", "搞笑", "funny", "lol", "haha"]
    
    # 重复模式（垃圾消息）
    SPAM_PATTERNS = [
        r"^[？？？]{2,}$",  # 连续问号
        r"^[啊呜呢]{2,}$",  # 连续叹词
        r"^[\s]*$",         # 只有空白
    ]
    
    @staticmethod
    def analyze(
        text: str,
        source: str = "group",  # "group" or "private"
        mentioned: bool = False,  # 是否 @ 了机器人
    ) -> EventAnalysis:
        """
        分析消息内容，返回结构化的事件分析结果
        
        Args:
            text: 原始消息文本
            source: 消息来源 (group/private)
            mentioned: 是否 @ 了机器人
        
        Returns:
            EventAnalysis 包含事件类型、特征、情绪增量等
        """
        text = text.strip()
        text_lower = text.lower()
        text_len = len(text)
        
        # 初始化结果
        event_type = EventType.NEUTRAL_CHAT
        is_attack = False
        is_praise = False
        is_teasing = False
        message_risk = 0.0
        spam_score = 0.0
        trigger_type = None
        emotion_delta = EmotionDelta()
        confidence = 0.8
        
        # ====== 基本检查 ======
        if not text or text_len == 0:
            return EventAnalysis(
                event_type=EventType.EMPTY,
                is_attack=False,
                is_praise=False,
                is_teasing=False,
                is_group=source == "group",
                mentioned=mentioned,
                message_risk=0.0,
                spam_score=0.5,
                trigger_type=None,
                emotion_delta=EmotionDelta(
                    anger=-2,
                    affection=0,
                    playfulness=0,
                    fatigue=1,
                    pride=0,
                    stress=0
                ),
                confidence=0.95
            )
        
        # ====== 检查触发类型 ======
        if mentioned:
            trigger_type = "at"
        
        # ====== 按优先级检查关键词 ======
        
        # 1. 检查严重辱骂（最高优先级）
        if EventMapper._contains_any(text_lower, EventMapper.ABUSE_KEYWORDS):
            event_type = EventType.ABUSE
            is_attack = True
            message_risk = 0.8
            spam_score = 0.1
            confidence = 0.95
            emotion_delta = EmotionDelta(
                anger=30,
                affection=-20,
                playfulness=-10,
                fatigue=0,
                pride=10,
                stress=15
            )
        
        # 2. 检查贬低
        elif EventMapper._contains_any(text_lower, EventMapper.INSULT_KEYWORDS):
            event_type = EventType.INSULT
            is_attack = True
            message_risk = 0.6
            spam_score = 0.2
            confidence = 0.9
            emotion_delta = EmotionDelta(
                anger=15,
                affection=-8,
                playfulness=-5,
                fatigue=0,
                pride=8,
                stress=5
            )
        
        # 3. 检查赞美
        elif EventMapper._contains_any(text_lower, EventMapper.PRAISE_KEYWORDS):
            event_type = EventType.PRAISE
            is_praise = True
            message_risk = 0.0
            spam_score = 0.0
            confidence = 0.85
            emotion_delta = EmotionDelta(
                anger=-5,
                affection=10,
                playfulness=5,
                fatigue=-2,
                pride=5,
                stress=-3
            )
        
        # 4. 检查逗趣
        elif EventMapper._contains_any(text_lower, EventMapper.TEASE_KEYWORDS):
            event_type = EventType.TEASE
            is_teasing = True
            message_risk = 0.1
            spam_score = 0.05
            confidence = 0.8
            emotion_delta = EmotionDelta(
                anger=-3,
                affection=5,
                playfulness=15,
                fatigue=-1,
                pride=0,
                stress=-2
            )
        
        # 5. 检查垃圾消息
        elif EventMapper._match_any_pattern(text, EventMapper.SPAM_PATTERNS) or text_len < 2:
            event_type = EventType.SPAM_RISK
            message_risk = 0.3
            spam_score = 0.7
            confidence = 0.85
            emotion_delta = EmotionDelta(
                anger=5,
                affection=-2,
                playfulness=0,
                fatigue=2,
                pride=0,
                stress=8
            )
        
        # 6. 默认友好交互
        else:
            event_type = EventType.NEUTRAL_CHAT
            message_risk = 0.05
            spam_score = 0.05
            confidence = 0.7
            emotion_delta = EmotionDelta(
                anger=-1,
                affection=2,
                playfulness=2,
                fatigue=0,
                pride=0,
                stress=-1
            )
        
        # ====== 群聊特殊处理 ======
        if source == "group":
            # 群聊中如果没有 @ 机器人，会增加压力和疲惫
            if not mentioned:
                emotion_delta.stress += 2
                emotion_delta.fatigue += 1
                spam_score = min(1.0, spam_score + 0.1)  # 被动消息增加垃圾指数
        
        # ====== 构建结果 ======
        return EventAnalysis(
            event_type=event_type,
            is_attack=is_attack,
            is_praise=is_praise,
            is_teasing=is_teasing,
            is_group=source == "group",
            mentioned=mentioned,
            message_risk=min(1.0, message_risk),
            spam_score=min(1.0, spam_score),
            trigger_type=trigger_type,
            emotion_delta=emotion_delta,
            confidence=confidence
        )
    
    @staticmethod
    def _contains_any(text: str, keywords: list) -> bool:
        """检查文本是否包含任何关键词"""
        for keyword in keywords:
            if keyword and keyword in text:
                return True
        return False
    
    @staticmethod
    def _match_any_pattern(text: str, patterns: list) -> bool:
        """检查文本是否匹配任何模式"""
        for pattern in patterns:
            if re.match(pattern, text):
                return True
        return False


# ====== 便利函数 ======

def analyze_message(
    text: str,
    source: str = "group",
    mentioned: bool = False,
) -> EventAnalysis:
    """
    分析消息 - 便利函数
    
    Returns:
        EventAnalysis 结构化事件分析结果
    """
    return EventMapper.analyze(text, source, mentioned)
