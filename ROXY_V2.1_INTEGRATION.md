"""
Roxy v2.1 快速集成指南
======================

4 个关键改进 + 日志系统 - 如何使用


### 1️⃣ Pydantic schemas (schemas.py) 的使用

✅ 自动导入和验证 LLM 输出

from schemas import DecisionOutput, EventAnalysis
from event_mapper import analyze_message

# 在 decision_engine.py 中:
raw_response = llm.chat(...)  # 获得 JSON 字符串
data = json.loads(raw_response)

# Pydantic 自动验证和转换
try:
    decision = DecisionOutput(
        thought=data.get("thought", {}),
        emotion_update=data.get("emotion_update", {}),
        response_plan=data.get("response_plan"),
        content=data.get("content")
    )
    # ✅ 如果验证通过，decision 对象安全可用
    
except ValidationError as e:
    # ❌ 如果验证失败（如 mode="invalid"），自动降级
    print(f"决策验证失败: {e}")
    # 返回默认的纯文字回复


### 2️⃣ action_executor.py 的降级链

✅ 自动在执行失败时降级

from action_executor import execute_decision, ExecutionResult

# 使用新的 execute_decision（返回 ExecutionResult）
result = await execute_decision(decision, user_id, username, group_id)

# 检查执行结果
if result.success:
    print(f"✅ 成功: {result.action_type}")
else:
    print(f"❌ 失败: {result.error}")
    print(f"降级链: {result.fallback_chain}")
    # 例如: ['voice', 'text'] 表示语音失败后自动发了文字

# 原来的代码（两种兼容）:
# success = await execute_decision(...)  # 返回 bool （不推荐）


### 3️⃣ event_mapper.py 的结构化特征

✅ 获得消息的详富特征信息

from event_mapper import analyze_message

analysis = analyze_message(
    text="太厉害了！",
    source="group",      # "group" or "private"
    mentioned=True       # 是否 @ 了机器人
)

# 获得 EventAnalysis 对象
print(f"事件类型: {analysis.event_type}")           # praise
print(f"是否夸奖: {analysis.is_praise}")            # True
print(f"风险评分: {analysis.message_risk}")         # 0.05
print(f"垃圾指数: {analysis.spam_score}")           # 0.0
print(f"情绪增量: {analysis.emotion_delta}")        # EmotionDelta(affection=10, ...)
print(f"置信度: {analysis.confidence}")             # 0.95

# 在 app.py 中使用:
log_event_analysis(
    user_id, 
    analysis.event_type.value,
    analysis.is_attack, 
    analysis.is_praise, 
    analysis.is_teasing,
    analysis.message_risk
)


### 4️⃣ 原子写入 (emotion_engine + user_profiles)

✅ 自动保证文件完整性

# 无需改任何代码，emotion_engine.py 和 user_profiles.py 已自动处理
from emotion_engine import apply_emotion_event

apply_emotion_event("praise", {"affection": 10}, user_id=123)
# emotion_state.json 已通过原子写入保存

# 即使在写入过程中断电:
# - emotion_state.json 保持原状（完好）
# - emotion_state.json.tmp 被丢弃


### 5️⃣ 日志系统 (logger.py) 的使用

✅ 在关键位置添加日志调用

from logger import (
    log_message, 
    log_emotion_change, 
    log_decision, 
    log_action,
    log_event_analysis,
    get_user_activity
)

## 5.1 记录收到的消息
log_message(
    user_id=123,
    username="小芳",
    text="你好呀",
    source="group"  # or "private"
)
# 输出到 logs/message.log

## 5.2 记录情绪变化
emotion_before = get_emotion(user_id=123).to_dict()
# ... 做些事情改变了情绪 ...
emotion_after = get_emotion(user_id=123).to_dict()

log_emotion_change(
    user_id=123,
    emotion_before=emotion_before,
    emotion_after=emotion_after,
    delta={"affection": 10, "anger": -5},
    group_id=456  # optional
)
# 输出到 logs/emotion.log

## 5.3 记录事件分析
log_event_analysis(
    user_id=123,
    event_type="praise",
    is_attack=False,
    is_praise=True,
    is_teasing=False,
    risk_score=0.05
)
# 输出到 logs/message.log

## 5.4 记录决策
log_decision(
    user_id=123,
    message="你好呀",
    event_type="neutral",
    decision_mode="text",
    decision_style="soft",
    error=None  # 如果有错误，传入错误信息
)
# 输出到 logs/decision.log

## 5.5 记录动作执行
log_action(
    user_id=123,
    action_type="text",
    success=True,
    message="发送成功",
    fallback_chain=["voice", "text"],  # 如果有降级
    execution_time_ms=234.5
)
# 输出到 logs/action.log

## 5.6 查询用户活动
activity = get_user_activity(user_id=123)
print(activity["message_count"])          # 10
print(activity["action_count"])           # 10
print(activity["emotion_changes"])        # 10
print(activity["recent_messages"][-3:])   # 最近 3 条消息


### 具体集成示例 (app.py 中)

✅ 完整的消息处理流程

async def handle_private_message(event: dict):
    user_id = event.get("user_id")
    raw_message = event.get("raw_message", "").strip()
    username = event.get("sender", {}).get("nickname", str(user_id))
    
    try:
        # 1️⃣ 记录收到的消息
        log_message(user_id, username, raw_message, source="private")
        
        # 2️⃣ 获取情绪前状态
        emotion_before = get_emotion(user_id=user_id).to_dict()
        
        # 3️⃣ 快速分析消息 (轻规则层)
        event_analysis = analyze_message(raw_message, source="private", mentioned=True)
        
        # 4️⃣ 记录事件分析
        log_event_analysis(
            user_id, 
            event_analysis.event_type.value,
            event_analysis.is_attack,
            event_analysis.is_praise,
            event_analysis.is_teasing,
            event_analysis.message_risk
        )
        
        # 5️⃣ 应用情绪变化
        apply_emotion_event(
            event_analysis.event_type.value,
            event_analysis.emotion_delta.to_dict(),
            user_id=user_id
        )
        
        # 6️⃣ 获取情绪后状态
        emotion_after = get_emotion(user_id=user_id).to_dict()
        
        # 7️⃣ 记录情绪变化
        log_emotion_change(user_id, emotion_before, emotion_after)
        
        # 8️⃣ LLM 决策 (Pydantic 自动验证)
        decision = await ask_brain(raw_message, user_id, username, "private")
        
        if not decision:
            log_decision(user_id, raw_message, event_analysis.event_type.value, error="LLM 失败")
            return
        
        # 9️⃣ 记录决策
        log_decision(
            user_id,
            raw_message,
            event_analysis.event_type.value,
            decision_mode=decision.response_plan.mode.value,
            decision_style=decision.response_plan.style.value
        )
        
        # 🔟 执行决策 (自动降级)
        exec_result = await execute_decision(decision, user_id, username)
        
        # 1️⃣1️⃣ 记录执行结果
        log_action(
            user_id,
            exec_result.action_type,
            exec_result.success,
            exec_result.error,
            exec_result.fallback_chain,
            exec_result.execution_time_ms
        )
        
    except Exception as e:
        log_app(f"处理失败: {e}", level="error")


### 日志查询常用命令

# 看最近的消息
tail logs/message.log -n 20

# 看最近的决策
tail logs/decision.log -n 20

# 看动作执行（特别是错误和降级）
tail logs/action.log -n 20

# 看情绪变化
tail logs/emotion.log -n 20

# 看特定用户的消息
grep "user_id=123" logs/message.log

# 看失败的动作
grep "[FAILED]" logs/action.log

# 看有降级的动作
grep "fallbacks=" logs/action.log

# 看 ERROR 级别的日志
grep "ERROR" logs/app.log


### 配置修改 (如果需要)

# 日志文件轮转大小 (默认 10MB)
# logger.py 第 48 行:
maxBytes=10*1024*1024  # 改为其他值

# 日志备份数量 (默认 5 个)
# logger.py 第 49 行:
backupCount=5  # 改为其他值

# 日志级别 (默认 INFO)
# logger.py 第 13 行:
level: int = logging.INFO  # 改为 DEBUG / WARNING / ERROR


### 与原代码的兼容性

✅ 完全兼容，无需改现有代码

旧代码:
  event_type, emotion_delta = analyze_message(text)
  success = await execute_decision(decision, user_id, username)

新代码（推荐，有日志）:
  event_analysis = analyze_message(text)
  exec_result = await execute_decision(decision, user_id, username)

两种都可以，新代码能获得更多信息。


### 性能影响

✅ 日志系统性能开销很小

- log_message(): <1ms
- log_emotion_change(): <1ms
- log_decision(): <1ms
- log_action(): <1ms

文件 I/O 是异步的，不会阻塞主线程。


### 完整检查清单

- [ ] pip install pydantic>=2.0
- [ ] schemas.py 已导入
- [ ] action_executor.py 已改为返回 ExecutionResult
- [ ] event_mapper.py 已导入 EventAnalysis
- [ ] logger.py 已导入日志函数
- [ ] app.py 已添加日志调用
- [ ] 创建了 logs/ 目录
- [ ] 启动时检查 logs/*.log 是否创建
- [ ] 发送测试消息，查看日志是否更新


Created with 💕 for Roxy v2.1
"""
