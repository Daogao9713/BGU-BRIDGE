"""
日志系统配置 - 统一的日志处理
支持多个日志通道和持久化
"""
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
import json


# 创建 logs 目录
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)


def setup_logger(
    name: str,
    log_file: str,
    level: int = logging.INFO,
    format_string: str = None
) -> logging.Logger:
    """
    设置一个日志记录器
    
    Args:
        name: 日志记录器名称
        log_file: 日志文件名
        level: 日志级别
        format_string: 自定义格式字符串
    
    Returns:
        配置好的 Logger 对象
    """
    if format_string is None:
        format_string = '[%(asctime)s] [%(levelname)s] %(message)s'
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加处理程序
    if logger.handlers:
        return logger
    
    # 文件处理程序（每天轮转）
    log_path = LOG_DIR / log_file
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    
    # 格式化器
    formatter = logging.Formatter(format_string)
    file_handler.setFormatter(formatter)
    
    # 添加处理程序
    logger.addHandler(file_handler)
    
    return logger


# ============================================================================
# 各个日志通道
# ============================================================================

# 应用日志 - 记录程序运行状态、启动、错误等
app_logger = setup_logger(
    "app",
    "app.log",
    logging.INFO,
    '[%(asctime)s] [%(levelname)s] %(message)s'
)

# 消息日志 - 记录收到的消息
message_logger = setup_logger(
    "message",
    "message.log",
    logging.INFO,
    '[%(asctime)s] [MSG] %(message)s'
)

# 决策日志 - 记录LLM决策过程和结果
decision_logger = setup_logger(
    "decision",
    "decision.log",
    logging.INFO,
    '[%(asctime)s] [DECISION] %(message)s'
)

# 动作日志 - 记录执行的动作（发语音、文字、梗图）
action_logger = setup_logger(
    "action",
    "action.log",
    logging.INFO,
    '[%(asctime)s] [ACTION] %(message)s'
)

# 情绪日志 - 记录情绪变化
emotion_logger = setup_logger(
    "emotion",
    "emotion.log",
    logging.INFO,
    '[%(asctime)s] [EMOTION] %(message)s'
)

# 用户档案日志 - 记录用户档案更新
profile_logger = setup_logger(
    "profile",
    "profile.log",
    logging.INFO,
    '[%(asctime)s] [PROFILE] %(message)s'
)


# ============================================================================
# 便利函数
# ============================================================================

def log_app(msg: str, level: str = "info"):
    """记录应用日志"""
    getattr(app_logger, level)(msg)


def log_message(user_id: int, username: str, text: str, source: str = "group"):
    """记录收到的消息"""
    text_short = text[:100] if len(text) > 100 else text
    message = f"[{source}] user_id={user_id} name={username} text={text_short}"
    message_logger.info(message)


def log_emotion_change(
    user_id: int,
    emotion_before: dict,
    emotion_after: dict,
    delta: dict = None,
    group_id: int = None
):
    """记录情绪变化"""
    msg = f"user_id={user_id}"
    if group_id:
        msg += f" group_id={group_id}"
    
    msg += f" before={json.dumps(emotion_before, ensure_ascii=False)}"
    msg += f" after={json.dumps(emotion_after, ensure_ascii=False)}"
    
    if delta:
        msg += f" delta={json.dumps(delta, ensure_ascii=False)}"
    
    emotion_logger.info(msg)


def log_decision(
    user_id: int,
    message: str,
    event_type: str,
    decision_mode: str = None,
    decision_style: str = None,
    error: str = None
):
    """记录决策信息"""
    message_short = message[:100] if len(message) > 100 else message
    
    msg = f"user_id={user_id} message={message_short} event={event_type}"
    
    if decision_mode:
        msg += f" mode={decision_mode}"
    
    if decision_style:
        msg += f" style={decision_style}"
    
    if error:
        msg += f" ERROR: {error}"
    
    if error:
        decision_logger.error(msg)
    else:
        decision_logger.info(msg)


def log_action(
    user_id: int,
    action_type: str,
    success: bool,
    message: str = None,
    fallback_chain: list = None,
    execution_time_ms: float = 0
):
    """记录动作执行"""
    status = "SUCCESS" if success else "FAILED"
    msg = f"[{status}] user_id={user_id} action={action_type} time_ms={execution_time_ms:.1f}"
    
    if message:
        msg += f" msg={message}"
    
    if fallback_chain and len(fallback_chain) > 0:
        msg += f" fallbacks={','.join(fallback_chain)}"
    
    if success:
        action_logger.info(msg)
    else:
        action_logger.error(msg)


def log_profile_update(
    user_id: int,
    username: str,
    changes: dict
):
    """记录用户档案更新"""
    msg = f"user_id={user_id} name={username} changes={json.dumps(changes, ensure_ascii=False)}"
    profile_logger.info(msg)


def log_event_analysis(
    user_id: int,
    event_type: str,
    is_attack: bool,
    is_praise: bool,
    is_teasing: bool,
    risk_score: float
):
    """记录事件分析"""
    msg = f"user_id={user_id} type={event_type}"
    flags = []
    
    if is_attack:
        flags.append("attack")
    if is_praise:
        flags.append("praise")
    if is_teasing:
        flags.append("tease")
    
    if flags:
        msg += f" flags={','.join(flags)}"
    
    msg += f" risk={risk_score:.2f}"
    
    message_logger.info(msg)


# ============================================================================
# 日志查询和统计函数
# ============================================================================

def get_recent_logs(log_type: str, lines: int = 50) -> list:
    """获取最近的日志行"""
    log_file = LOG_DIR / f"{log_type}.log"
    
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return all_lines[-lines:] if len(all_lines) > lines else all_lines
    except Exception as e:
        app_logger.error(f"读取日志失败: {e}")
        return []


def get_user_activity(user_id: int) -> dict:
    """获取用户的活动统计"""
    result = {
        "user_id": user_id,
        "message_count": 0,
        "action_count": 0,
        "emotion_changes": 0,
        "recent_messages": []
    }
    
    try:
        # 统计消息
        message_file = LOG_DIR / "message.log"
        if message_file.exists():
            with open(message_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if f"user_id={user_id}" in line:
                        result["message_count"] += 1
                        result["recent_messages"].append(line.strip())
        
        # 统计动作
        action_file = LOG_DIR / "action.log"
        if action_file.exists():
            with open(action_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if f"user_id={user_id}" in line:
                        result["action_count"] += 1
        
        # 统计情绪变化
        emotion_file = LOG_DIR / "emotion.log"
        if emotion_file.exists():
            with open(emotion_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if f"user_id={user_id}" in line:
                        result["emotion_changes"] += 1
        
        result["recent_messages"] = result["recent_messages"][-20:]  # 最近20条
        
    except Exception as e:
        app_logger.error(f"获取用户活动统计失败: {e}")
    
    return result
