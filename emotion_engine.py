"""
情绪引擎 - 6维度情绪系统 + 事件驱动 + 时间衰减
"""
import time
import json
from typing import Dict, Optional
from dataclasses import dataclass, asdict, field
from pathlib import Path

@dataclass
class EmotionState:
    """6维度情绪状态"""
    anger: float = 20.0         # 愤怒
    affection: float = 55.0     # 亲近感
    playfulness: float = 60.0   # 玩心 / 乐子人程度
    fatigue: float = 15.0       # 疲惫
    pride: float = 70.0         # 傲娇 / 自尊
    stress: float = 10.0        # 群聊压力
    
    def clamp(self) -> None:
        """确保所有值在[0, 100]范围内"""
        for key in self.__dataclass_fields__:
            val = getattr(self, key)
            setattr(self, key, max(0, min(100, val)))
    
    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class EmotionContext:
    """情绪的完整上下文"""
    emotion: EmotionState
    last_update_time: float = field(default_factory=time.time)
    interaction_count: int = 0  # 本轮交互次数
    
    def age_seconds(self) -> float:
        """距离上次更新已过了多少秒"""
        return time.time() - self.last_update_time


class EmotionEngine:
    """
    全局情绪引擎
    - 管理 Roxy 的全局情绪状态
    - 管理每个用户的相对情绪偏移（相对于全局基线）
    """
    
    # 全局情绪基线（Roxy 的"心情"）
    _global_emotion: EmotionState
    _global_emotion_time: float
    
    # 用户维度的情绪增量
    _user_emotion_delta: Dict[int, EmotionState]
    _user_emotion_time: Dict[int, float]
    
    # 群聊维度的情绪增量
    _group_emotion_delta: Dict[int, EmotionState]
    _group_emotion_time: Dict[int, float]
    
    # 自然衰减系数（每分钟）
    DECAY_RATES = {
        "anger": 4.0,       # 每分钟 -4
        "affection": 1.0,   # 每分钟 -1（缓慢衰减）
        "playfulness": 2.0, # 每分钟 -2
        "fatigue": 1.5,     # 每分钟 -1.5（逐渐恢复）
        "pride": 1.0,       # 每分钟 -1
        "stress": 5.0       # 每分钟 -5（压力快速释放）
    }
    
    # 设置文件路径
    EMOTION_STATE_FILE = "./cache/emotion_state.json"
    
    def __init__(self):
        self._global_emotion = EmotionState()
        self._global_emotion_time = time.time()
        
        self._user_emotion_delta = {}
        self._user_emotion_time = {}
        
        self._group_emotion_delta = {}
        self._group_emotion_time = {}
        
        self.load_state()
    
    def load_state(self) -> None:
        """从文件加载保存的情绪状态"""
        Path("./cache").mkdir(exist_ok=True)
        
        if not Path(self.EMOTION_STATE_FILE).exists():
            return
        
        try:
            with open(self.EMOTION_STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "global_emotion" in data:
                    self._global_emotion = EmotionState(**data["global_emotion"])
                    self._global_emotion_time = data.get("global_emotion_time", time.time())
                
                if "user_emotion_delta" in data:
                    for uid_str, emotion_dict in data["user_emotion_delta"].items():
                        uid = int(uid_str)
                        self._user_emotion_delta[uid] = EmotionState(**emotion_dict)
                        self._user_emotion_time[uid] = data["user_emotion_time"].get(uid_str, time.time())
        except Exception as e:
            print(f"加载情绪状态失败: {e}")
    
    def save_state(self) -> None:
        """
        保存情绪状态到文件（原子写入）
        先写临时文件，再替换原文件，避免文件损坏
        """
        try:
            data = {
                "global_emotion": self._global_emotion.to_dict(),
                "global_emotion_time": self._global_emotion_time,
                "user_emotion_delta": {
                    str(uid): emotion.to_dict()
                    for uid, emotion in self._user_emotion_delta.items()
                },
                "user_emotion_time": {
                    str(uid): t for uid, t in self._user_emotion_time.items()
                },
                "group_emotion_delta": {
                    str(gid): emotion.to_dict()
                    for gid, emotion in self._group_emotion_delta.items()
                },
                "group_emotion_time": {
                    str(gid): t for gid, t in self._group_emotion_time.items()
                },
            }
            
            Path("./cache").mkdir(exist_ok=True)
            
            # 原子写入：先写临时文件
            tmp_file = Path(self.EMOTION_STATE_FILE + ".tmp")
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 原子替换
            tmp_file.replace(self.EMOTION_STATE_FILE)
            print(f"[情绪] 状态已保存")
        except Exception as e:
            print(f"[错误] 保存情绪状态失败: {e}")
    
    def _apply_decay(self, emotion: EmotionState, seconds: float) -> EmotionState:
        """根据时间衰减情绪"""
        decay_minutes = seconds / 60.0
        
        for key, decay_rate in self.DECAY_RATES.items():
            current = getattr(emotion, key)
            decayed = max(0, current - decay_rate * decay_minutes)
            setattr(emotion, key, decayed)
        
        emotion.clamp()
        return emotion
    
    def _update_decay(self) -> None:
        """更新全局和用户的衰减"""
        now = time.time()
        
        # 全局衰减
        age = now - self._global_emotion_time
        if age > 0:
            self._global_emotion = self._apply_decay(self._global_emotion, age)
            self._global_emotion_time = now
        
        # 用户衰减
        for uid in list(self._user_emotion_delta.keys()):
            age = now - self._user_emotion_time.get(uid, now)
            if age > 0:
                self._user_emotion_delta[uid] = self._apply_decay(
                    self._user_emotion_delta[uid], age
                )
                self._user_emotion_time[uid] = now
        
        # 群聊衰减
        for gid in list(self._group_emotion_delta.keys()):
            age = now - self._group_emotion_time.get(gid, now)
            if age > 0:
                self._group_emotion_delta[gid] = self._apply_decay(
                    self._group_emotion_delta[gid], age
                )
                self._group_emotion_time[gid] = now
    
    def apply_event(self, event_type: str, delta: Dict[str, float],
                    user_id: Optional[int] = None,
                    group_id: Optional[int] = None) -> None:
        """
        应用情绪事件
        
        event_type: "praise", "insult", "tease", "spam", "boundary_breach", etc.
        delta: {"anger": +20, "affection": -8, ...}
        user_id: 触发事件的用户ID
        group_id: 触发事件的群ID（如果是群聊）
        """
        self._update_decay()
        
        # 全局情绪更新
        for key, val in delta.items():
            if hasattr(self._global_emotion, key):
                current = getattr(self._global_emotion, key)
                setattr(self._global_emotion, key, current + val)
        
        # 用户维度的相对偏移
        if user_id is not None:
            if user_id not in self._user_emotion_delta:
                self._user_emotion_delta[user_id] = EmotionState(
                    anger=0, affection=0, playfulness=0,
                    fatigue=0, pride=0, stress=0
                )
            
            for key, val in delta.items():
                if hasattr(self._user_emotion_delta[user_id], key):
                    current = getattr(self._user_emotion_delta[user_id], key)
                    setattr(self._user_emotion_delta[user_id], key, current + val)
            
            self._user_emotion_time[user_id] = time.time()
        
        # 群聊维度的相对偏移
        if group_id is not None:
            if group_id not in self._group_emotion_delta:
                self._group_emotion_delta[group_id] = EmotionState(
                    anger=0, affection=0, playfulness=0,
                    fatigue=0, pride=0, stress=0
                )
            
            for key, val in delta.items():
                if hasattr(self._group_emotion_delta[group_id], key):
                    current = getattr(self._group_emotion_delta[group_id], key)
                    setattr(self._group_emotion_delta[group_id], key, current + val)
            
            self._group_emotion_time[group_id] = time.time()
        
        # 全局情绪夹紧
        self._global_emotion.clamp()
        if user_id in self._user_emotion_delta:
            self._user_emotion_delta[user_id].clamp()
        if group_id in self._group_emotion_delta:
            self._group_emotion_delta[group_id].clamp()
        
        self.save_state()
    
    def get_emotion(self, user_id: Optional[int] = None,
                   group_id: Optional[int] = None) -> EmotionState:
        """
        获取当前情绪（综合全局 + 用户/群聊维度）
        """
        self._update_decay()
        
        # 基础是全局情绪
        emotion = EmotionState(**self._global_emotion.to_dict())
        
        # 叠加用户维度
        if user_id is not None and user_id in self._user_emotion_delta:
            user_delta = self._user_emotion_delta[user_id]
            for key in emotion.__dataclass_fields__:
                val = getattr(emotion, key) + getattr(user_delta, key)
                setattr(emotion, key, val)
        
        # 叠加群聊维度（可选，如果group_id提供）
        if group_id is not None and group_id in self._group_emotion_delta:
            group_delta = self._group_emotion_delta[group_id]
            for key in emotion.__dataclass_fields__:
                val = getattr(emotion, key) + getattr(group_delta, key)
                setattr(emotion, key, val)
        
        emotion.clamp()
        return emotion
    
    def get_global_emotion(self) -> EmotionState:
        """获取全局情绪"""
        self._update_decay()
        return EmotionState(**self._global_emotion.to_dict())
    
    def reset_emotion(self) -> None:
        """重置到初始状态"""
        self._global_emotion = EmotionState()
        self._global_emotion_time = time.time()
        self._user_emotion_delta.clear()
        self._user_emotion_time.clear()
        self._group_emotion_delta.clear()
        self._group_emotion_time.clear()
        self.save_state()


# 全局单例
emotion_engine = EmotionEngine()


# 便利函数
def apply_emotion_event(event_type: str, delta: Dict[str, float],
                       user_id: Optional[int] = None,
                       group_id: Optional[int] = None) -> None:
    """应用情绪事件"""
    emotion_engine.apply_event(event_type, delta, user_id, group_id)


def get_emotion(user_id: Optional[int] = None,
               group_id: Optional[int] = None) -> EmotionState:
    """获取情绪"""
    return emotion_engine.get_emotion(user_id, group_id)


def get_global_emotion() -> EmotionState:
    """获取全局情绪"""
    return emotion_engine.get_global_emotion()
