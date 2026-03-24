"""
Brain - Roxy v2 决策层
负责调用 decision_engine 获取 JSON 决策
包含滑动记忆窗口支持
"""
from typing import Optional, Dict
from decision_engine import make_decision, DecisionOutput
from config import PERSONA_CONFIG
from user_profiles import get_message_history, add_message_to_history


async def ask_brain(
    user_text: str,
    user_id: int,
    username: str,
    source: str = "private",
    group_id: Optional[int] = None
) -> Optional[DecisionOutput]:
    """
    让 Roxy 的大脑做出决策
    
    Args:
        user_text: 用户消息
        user_id: 用户ID
        username: 用户名
        source: "private" 或 "group"
        group_id: 群ID（如果是群聊）
    
    Returns:
        DecisionOutput 或 None（如果决策失败）
    """
    try:
        print(f"[brain] user_text={user_text!r}, user_id={user_id}, source={source}")
        
        # 🎯 第一步：获取用户的对话历史（滑动窗口）
        user_history = get_message_history(user_id)
        print(f"[brain] 用户 {user_id} 的历史记录条数: {len(user_history)}")
        
        # 🎯 第二步：将当前用户消息添加到历史
        add_message_to_history(user_id, "user", user_text)
        
        # 调用决策引擎（传递历史上下文）
        decision = await make_decision(
            user_message=user_text,
            user_id=user_id,
            username=username,
            source=source,
            persona_config=PERSONA_CONFIG,
            user_history=user_history  # 把历史记录传给 LLM
        )
        
        print(f"[brain] decision = {decision}")
        
        # 🎯 第三步：如果决策成功，将 Roxy 的回复也添加到历史
        if decision:
            reply_text = decision.content.get("text", "")
            if reply_text:
                add_message_to_history(user_id, "assistant", reply_text)
                print(f"[brain] 已记录 Roxy 的回复到历史")
        
        return decision
    except Exception as e:
        import traceback
        print(f"[brain] 异常: {repr(e)}")
        traceback.print_exc()
        raise
