"""
用户档案管理 - 用户关系模型 + 滑动记忆窗口
"""
import json
import time
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict, field
from pathlib import Path


@dataclass
class UserProfile:
    """用户档案"""
    user_id: int
    nickname: str = "用户"
    favorability: float = 50.0      # 好感度 [0-100]
    familiarity: float = 30.0       # 熟悉度 [0-100]
    boundary_risk: float = 20.0     # 越高越容易触发防御 [0-100]
    last_interaction: float = 0     # 最后交互时间戳
    interaction_count: int = 0      # 总交互次数
    created_at: float = 0           # 创建时间
    history: List[Dict[str, str]] = field(default_factory=list)  # 对话历史 - 滑动窗口
    
    def to_dict(self):
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> "UserProfile":
        # 处理向后兼容 - 旧数据可能没有 history 字段
        if "history" not in data:
            data["history"] = []
        return UserProfile(**data)


class UserProfileManager:
    """用户档案管理器"""
    
    PROFILE_FILE = "./cache/user_profiles.json"
    
    def __init__(self):
        self.profiles: Dict[int, UserProfile] = {}
        self.load_profiles()
    
    def load_profiles(self) -> None:
        """从文件加载用户档案"""
        Path("./cache").mkdir(exist_ok=True)
        
        if not Path(self.PROFILE_FILE).exists():
            return
        
        try:
            with open(self.PROFILE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for uid_str, profile_dict in data.items():
                    uid = int(uid_str)
                    self.profiles[uid] = UserProfile.from_dict(profile_dict)
        except Exception as e:
            print(f"加载用户档案失败: {e}")
    
    def save_profiles(self) -> None:
        """
        保存用户档案到文件（原子写入）
        先写临时文件，再替换原文件，避免文件损坏
        """
        try:
            Path("./cache").mkdir(exist_ok=True)
            data = {
                str(uid): profile.to_dict()
                for uid, profile in self.profiles.items()
            }
            
            # 原子写入：先写临时文件
            tmp_file = Path(self.PROFILE_FILE + ".tmp")
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 原子替换
            tmp_file.replace(self.PROFILE_FILE)
            print(f"[档案] 用户档案已保存")
        except Exception as e:
            print(f"[错误] 保存用户档案失败: {e}")
    
    def get_or_create(self, user_id: int, nickname: str = "用户") -> UserProfile:
        """获取或创建用户档案"""
        if user_id not in self.profiles:
            self.profiles[user_id] = UserProfile(
                user_id=user_id,
                nickname=nickname,
                created_at=time.time()
            )
            self.save_profiles()
        else:
            # 更新昵称
            if nickname and nickname != "用户":
                self.profiles[user_id].nickname = nickname
        
        return self.profiles[user_id]
    
    def update_interaction(self, user_id: int, nickname: str = None) -> UserProfile:
        """更新用户交互统计"""
        profile = self.get_or_create(user_id, nickname or "用户")
        profile.last_interaction = time.time()
        profile.interaction_count += 1
        
        # 根据交互次数自动提升熟悉度（缓慢）
        profile.familiarity = min(100, profile.familiarity + 0.5)
        
        self.save_profiles()
        return profile
    
    def update_favorability(self, user_id: int, delta: float) -> UserProfile:
        """更新好感度"""
        profile = self.get_or_create(user_id)
        profile.favorability = max(0, min(100, profile.favorability + delta))
        self.save_profiles()
        return profile
    
    def update_boundary_risk(self, user_id: int, delta: float) -> UserProfile:
        """更新边界风险"""
        profile = self.get_or_create(user_id)
        profile.boundary_risk = max(0, min(100, profile.boundary_risk + delta))
        self.save_profiles()
        return profile
    
    def get_relationship_bias(self, user_id: int) -> Dict[str, float]:
        """
        获取关系偏差
        
        基于用户档案，返回应该如何对待这个用户的建议
        - affection_bonus: 亲近感增强
        - anger_bias: 愤怒敏感性
        - tolerance: 容错度
        """
        profile = self.get_or_create(user_id)
        
        # 熟人 + 高好感 = 更容易发语音、更软语气
        affection_bonus = (profile.familiarity * 0.3 + profile.favorability * 0.2) - 40
        
        # 边界风险高 = 更容易生气
        anger_bias = profile.boundary_risk * 0.5
        
        # 好感高 = 更容忍
        tolerance = max(-20, profile.favorability - 50)
        
        return {
            "affection_bonus": affection_bonus,
            "anger_bias": anger_bias,
            "tolerance": tolerance,
            "familiarity": profile.familiarity,
            "favorability": profile.favorability,
            "boundary_risk": profile.boundary_risk
        }
    
    def add_message_to_history(self, user_id: int, role: str, content: str) -> None:
        """
        向用户的对话历史中添加一条消息
        
        Args:
            user_id: 用户ID
            role: "user" 或 "assistant"
            content: 消息内容
        """
        profile = self.get_or_create(user_id)
        
        # 确保 history 存在
        if not hasattr(profile, "history") or profile.history is None:
            profile.history = []
        
        # 添加新消息
        profile.history.append({
            "role": role,
            "content": content
        })
        
        # 滑动窗口：只保留最近的 8 条对话（4个回合），防止 Token 爆炸
        max_history = 8
        if len(profile.history) > max_history:
            profile.history = profile.history[-max_history:]
            print(f"[历史] 用户 {user_id} 的对话历史超限，仅保留最近 {max_history} 条")
        
        # 保存
        self.save_profiles()
    
    def get_message_history(self, user_id: int) -> List[Dict[str, str]]:
        """
        获取用户的对话历史
        
        返回 OpenAI/Grok 兼容格式的消息列表
        """
        profile = self.get_or_create(user_id)
        
        if not hasattr(profile, "history") or profile.history is None:
            return []
        
        return profile.history


# 全局单例
user_profile_manager = UserProfileManager()


# 便利函数
def get_user_profile(user_id: int, nickname: str = "用户") -> UserProfile:
    """获取用户档案"""
    return user_profile_manager.get_or_create(user_id, nickname)


def update_user_interaction(user_id: int, nickname: str = None) -> UserProfile:
    """更新用户交互"""
    return user_profile_manager.update_interaction(user_id, nickname)


def get_relationship_bias(user_id: int) -> Dict[str, float]:
    """获取关系偏差"""
    return user_profile_manager.get_relationship_bias(user_id)


def add_message_to_history(user_id: int, role: str, content: str) -> None:
    """向用户对话历史中添加消息"""
    user_profile_manager.add_message_to_history(user_id, role, content)


def get_message_history(user_id: int) -> List[Dict[str, str]]:
    """获取用户对话历史"""
    return user_profile_manager.get_message_history(user_id)
