from fastapi import FastAPI, Request, BackgroundTasks
from contextlib import asynccontextmanager
from config.config import (
    BOT_QQ, TRIGGER_PREFIX, TARGET_GROUP_ID, 
    LLM_PROVIDER, MODEL_NAME, ACTIVE_API_KEY, ACTIVE_PROVIDER_NAME,
    REFINE_WITH_GROK, PERSONA_CONFIG
)
from .utils.guard import (
    group_in_cooldown, user_in_cooldown,
    mark_group_reply, mark_user_reply
)
from .brain import ask_brain
from .core.action_executor import execute_decision, action_executor
from .core.emotion_engine import apply_emotion_event, get_emotion
from .core.user_profiles import update_user_interaction
from .core.event_mapper import analyze_message
from .utils.logger import (
    log_app, log_message, log_emotion_change, log_decision,
    log_action, log_event_analysis
)
from .utils.cron_scheduler import RoxyBiorhythm

# ============= 初始化生物钟 =============
biorhythm = RoxyBiorhythm(target_group_id=TARGET_GROUP_ID)


# ============= 助手函数 =============
def is_self_message(event: dict) -> bool:
    """检查是否为机器人自己发出的消息"""
    # 1. NapCat 回传的 message_sent 事件
    if event.get("post_type") == "message_sent":
        return True
    
    # 2. 发送者 user_id 就是机器人自己
    user_id_str = str(event.get("user_id", ""))
    bot_qq_str = str(BOT_QQ)
    if user_id_str == bot_qq_str and user_id_str != "0":
        return True
    
    # 3. 发送者的 self_id 等于 user_id（备选检查）
    if str(event.get("user_id", "")) == str(event.get("self_id", "")):
        return True
    
    return False

def extract_text(event: dict) -> str:
    return (event.get("raw_message") or "").strip()

def is_at_me(event: dict) -> bool:
    msgs = event.get("message", [])
    self_id = str(event.get("self_id", ""))
    bot_qq = str(BOT_QQ) if 'BOT_QQ' in globals() else ""
    
    # 建立一个合法的 ID 集合
    my_ids = {self_id, bot_qq}
    # 建立一个可能的昵称集合（如果你的机器人叫 Roxy）
    my_names = {"@Roxy", f"@{self_id}"} 

    for seg in msgs:
        seg_type = seg.get("type")
        seg_data = seg.get("data", {})

        # 1. 检查标准的 AT 类型（CQ码模式）
        if seg_type == "at":
            qq = str(seg_data.get("qq", "")).strip()
            if qq in my_ids:
                return True
        
        # 2. 检查文本类型（由于某些端会将@识别为纯文本）
        elif seg_type == "text":
            content = seg_data.get("text", "").strip()
            # 只要开头带有 @Roxy 或者任何配置的 ID
            if any(name in content for name in my_names):
                return True
                
    return False

def clean_group_text(event: dict) -> str:
    msgs = event.get("message", [])
    parts = []
    for seg in msgs:
        if seg.get("type") == "text":
            parts.append(seg.get("data", {}).get("text", ""))
    return "".join(parts).strip()

def too_long(text: str, limit: int = 200) -> bool:
    return len((text or "").strip()) > limit

def should_handle_group(event: dict) -> bool:
    group_id = event.get("group_id")
    user_id = event.get("user_id")
    text = extract_text(event)

    triggered = is_at_me(event) or any(text.startswith(p) for p in TRIGGER_PREFIX)
    if not triggered:
        return False

    if group_in_cooldown(group_id):
        print("群聊被群冷却拦截:", group_id)
        return False

    if user_in_cooldown(user_id):
        print("群聊被用户冷却拦截:", user_id)
        return False

    return True


# ============= 伪造事件处理函数 (前置定义，供 lifespan 使用) =============
async def handle_synthetic_event(event: dict):
    """
    处理由 cron_scheduler 生成的伪造事件
    这些事件会被当作真实消息一样处理，走完整的分析-决策-执行链路
    
    伪造事件的特殊字段:
    - _synthetic: bool = True
    - _event_type: str (SYSTEM_BORED, SYSTEM_NEWS, 等)
    """
    try:
        # 识别伪造事件类型（用于日志）
        event_type = event.get("_event_type", "UNKNOWN")
        print(f"[伪造事件] 处理系统事件: {event_type}")
        log_app(f"[伪造事件] 开始处理系统事件: {event_type}", level="info")
        
        # 如果是群聊事件，处理方式与真实群聊完全一致
        message_type = event.get("message_type")
        
        if message_type == "group":
            await handle_group_message(event)
        elif message_type == "private":
            await handle_private_message(event)
        else:
            print(f"[伪造事件] 未知的消息类型: {message_type}")
    
    except Exception as e:
        import traceback
        print(f"[伪造事件] 处理失败: {repr(e)}")
        traceback.print_exc()
        log_app(f"伪造事件处理失败: {repr(e)}", level="error")


# ============= FastAPI 生命周期 =============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期管理
    startup: 启动生物钟 + 显示LLM模型配置
    shutdown: 关闭生物钟
    """
    # 启动时：注册事件处理函数并启动定时任务
    biorhythm.set_event_processor(handle_synthetic_event)
    biorhythm.start()
    
    # 显示LLM模型信息
    llm_info = (
        f"\n{'='*60}\n"
        f"🤖 LLM 厂商信息\n"
        f"{'='*60}\n"
        f"当前选择厂商: {ACTIVE_PROVIDER_NAME.upper()}\n"
        f"服务商标识 (LLM_PROVIDER): {LLM_PROVIDER}\n"
        f"模型前缀 (MODEL_NAME): {MODEL_NAME}\n"
        f"API Key 已配置: {'✓' if ACTIVE_API_KEY else '✗'}\n"
        f"{'='*60}\n"
    )
    log_app(llm_info, level="info")
    log_app(f"[主程序] FastAPI 应用启动，生物钟已初始化", level="info")
    
    yield
    
    # 关闭时：清理生物钟资源
    biorhythm.shutdown()
    log_app("[主程序] FastAPI 应用关闭，生物钟已清理", level="info")


app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/onebot/event")
async def onebot_event(request: Request, background_tasks: BackgroundTasks):
    event = await request.json()
    print("收到事件：", event)

    post_type = event.get("post_type")
    user_id = str(event.get("user_id", ""))

    # 1. 忽略机器人自己发出的消息（NapCat 回传）
    if post_type == "message_sent":
        print(f"已忽略: message_sent 事件")
        return {"status": "ok"}

    # 2. 忽略发送者就是 bot 自己的消息
    bot_qq_str = str(BOT_QQ)
    if user_id == bot_qq_str and user_id != "0":
        print(f"已忽略: 机器人自己的消息 (user_id={user_id})")
        return {"status": "ok"}
    
    # 3. 忽略 user_id == self_id 的情况（备选检查）
    if user_id == str(event.get("self_id", "")):
        print(f"已忽略: user_id == self_id")
        return {"status": "ok"}

    # 4. 只处理 message 事件
    if post_type != "message":
        print(f"已忽略: 非 message 事件 (post_type={post_type})")
        return {"status": "ok"}

    msg_type = event.get("message_type")

    if msg_type == "private":
        if not user_in_cooldown(event.get("user_id")):
            mark_user_reply(event.get("user_id"))
            background_tasks.add_task(handle_private_message, event)

    elif msg_type == "group":
        # 更新群聊活动时间戳（重置冷场计时器）
        biorhythm.update_activity()
        
        print("进入群聊判断")
        print("group_id =", event.get("group_id"))
        print("raw_message =", event.get("raw_message"))
        print("is_at_me =", is_at_me(event))

        handle_group = should_handle_group(event)
        print("should_handle_group =", handle_group)

        if handle_group:
            mark_group_reply(event.get("group_id"))
            mark_user_reply(event.get("user_id"))
            background_tasks.add_task(handle_group_message, event)

    return {"status": "ok"}

async def handle_private_message(event: dict):
    user_id = event.get("user_id")
    raw_message = extract_text(event)
    
    if too_long(raw_message, 500):
        return
    
    sender = event.get("sender", {}) or {}
    username = sender.get("nickname", str(user_id))

    print("[1] 开始处理私聊")
    try:
        # 记录收到的消息
        print("[2] 记录消息前")
        log_message(user_id, username, raw_message, source="private")
        print("[3] 记录消息后")
        
        # 获取情绪变化前的状态
        print("[4] 获取情绪前")
        emotion_before = get_emotion(user_id=user_id).to_dict()
        print("[5] 获取情绪后")
        
        # 更新用户交互
        print("[6] 更新档案前")
        update_user_interaction(user_id, username)
        print("[7] 更新档案后")
        
        # 分析消息，应用基础情绪增量
        print("[8] 分析消息前")
        event_analysis = analyze_message(raw_message, source="private", mentioned=True)
        event_type = event_analysis.event_type.value
        emotion_delta = event_analysis.emotion_delta.to_dict()
        print(f"[9] 分析消息后: event_type={event_type}")
        
        print("[10] 记录事件分析前")
        log_event_analysis(
            user_id, event_type,
            event_analysis.is_attack,
            event_analysis.is_praise,
            event_analysis.is_teasing,
            event_analysis.message_risk
        )
        print("[11] 记录事件分析后")
        
        print("[12] apply_emotion_event前")
        apply_emotion_event(event_type, emotion_delta, user_id=user_id)
        print("[13] apply_emotion_event后")
        
        # 获取情绪变化后的状态
        print("[14] 获取最终情绪前")
        emotion_after = get_emotion(user_id=user_id).to_dict()
        print("[15] 获取最终情绪后")
        
        print("[16] log_emotion_change前")
        log_emotion_change(user_id, emotion_before, emotion_after, emotion_delta)
        print("[17] log_emotion_change后")
        
        # 让 Roxy 的大脑做出决策
        print("[18] ask_brain前")
        decision = await ask_brain(
            user_text=raw_message,
            user_id=user_id,
            username=username,
            source="private"
        )
        print(f"[19] ask_brain后: decision={decision}")
        
        if not decision:
            print("[20] 决策为空")
            log_decision(user_id, raw_message, event_type, error="决策失败")
            from onebot_client import send_private_text
            await send_private_text(user_id, "……信号在飘，没听清。")
            return
        
        print("[21] log_decision前")
        log_decision(
            user_id, raw_message, event_type,
            decision_mode=decision.response_plan.get("mode"),
            decision_style=decision.response_plan.get("style")
        )
        print("[22] log_decision后")
        
        # 执行决策
        print("[23] execute_decision前")
        req_id = action_executor.next_req_id(user_id)
        exec_result = await execute_decision(
            decision=decision,
            user_id=user_id,
            username=username,
            group_id=None,
            req_id=req_id,
            enable_grok_refine=REFINE_WITH_GROK,
            persona_config=PERSONA_CONFIG
        )
        print(f"[24] execute_decision后: success={exec_result.success}")
        
        print("[25] log_action前")
        log_action(
            user_id,
            exec_result.action_type,
            exec_result.success,
            exec_result.error,
            exec_result.fallback_chain,
            exec_result.execution_time_ms
        )
        print("[26] log_action后")
        
        if not exec_result.success:
            print("[27] 执行失败，发送fallback文本")
            try:
                from onebot_client import send_private_text
                await send_private_text(user_id, "……刚才信号有点飘。")
            except Exception as err:
                print(f"[27-err] fallback发送失败: {repr(err)}")
        
        print("[28] 私聊处理完成")

        print("[28] 私聊处理完成")

    except Exception as e:
        import traceback
        print(f"[private] 处理异常: {repr(e)}")
        traceback.print_exc()
        log_app(f"私聊处理失败: {repr(e)}", level="error")
        try:
            from onebot_client import send_private_text
            await send_private_text(user_id, "……刚才信号有点飘。")
        except Exception as send_err:
            print(f"[private] fallback发送失败: {repr(send_err)}")

async def handle_group_message(event: dict):
    group_id = event.get("group_id")
    user_id = event.get("user_id")
    text = clean_group_text(event) if is_at_me(event) else extract_text(event)
    
    if too_long(text, 200):
        return
    
    sender = event.get("sender", {}) or {}
    username = sender.get("card") or sender.get("nickname") or str(user_id)

    try:
        # 记录收到的消息
        log_message(user_id, username, text, source="group")
        
        # 获取情绪变化前的状态
        emotion_before = get_emotion(user_id=user_id, group_id=group_id).to_dict()
        
        # 更新用户交互
        update_user_interaction(user_id, username)
        
        # 分析消息，应用基础情绪增量
        mentioned = is_at_me(event)
        event_analysis = analyze_message(text, source="group", mentioned=mentioned)
        event_type = event_analysis.event_type.value
        emotion_delta = event_analysis.emotion_delta.to_dict()
        
        log_event_analysis(
            user_id, event_type,
            event_analysis.is_attack,
            event_analysis.is_praise,
            event_analysis.is_teasing,
            event_analysis.message_risk
        )
        
        apply_emotion_event(event_type, emotion_delta, user_id=user_id, group_id=group_id)
        
        # 获取情绪变化后的状态
        emotion_after = get_emotion(user_id=user_id, group_id=group_id).to_dict()
        log_emotion_change(user_id, emotion_before, emotion_after, emotion_delta, group_id)
        
        # 让 Roxy 的大脑做出决策
        decision = await ask_brain(
            user_text=text,
            user_id=user_id,
            username=username,
            source="group",
            group_id=group_id
        )
        
        if not decision:
            log_decision(user_id, text, event_type, error="决策失败")
            from onebot_client import send_group_text
            await send_group_text(group_id, "……信号在飘，没听清。")
            return
        
        log_decision(
            user_id, text, event_type,
            decision_mode=decision.response_plan.get("mode"),
            decision_style=decision.response_plan.get("style")
        )
        
        # 执行决策
        req_id = action_executor.next_req_id(user_id)
        exec_result = await execute_decision(
            decision=decision,
            user_id=user_id,
            username=username,
            group_id=group_id,
            req_id=req_id,
            enable_grok_refine=REFINE_WITH_GROK,
            persona_config=PERSONA_CONFIG
        )
        
        log_action(
            user_id,
            exec_result.action_type,
            exec_result.success,
            exec_result.error,
            exec_result.fallback_chain,
            exec_result.execution_time_ms
        )
        
        if not exec_result.success:
            try:
                from onebot_client import send_group_text
                await send_group_text(group_id, "……刚才信号有点飘。")
            except Exception:
                pass

    except Exception as e:
        log_app(f"群聊处理失败: {e}", level="error")
        try:
            from onebot_client import send_group_text
            await send_group_text(group_id, "……刚才信号有点飘。")
        except Exception:
            pass