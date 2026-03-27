"""
动作执行器 - 执行 LLM 做出的决策
严格遵循 5 条执行层硬规则，不允许自作主张补文本
"""
import asyncio
import os
import time
from typing import Optional, Dict, Tuple, List
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont
from .decision_engine import DecisionOutput, ResponseMode, clean_roxy_text
from ..utils.tts import synthesize_tts, is_tts_alive
from config.config import TTS_GPU_IP
from ..interfaces.onebot_client import (
    send_private_text, send_group_text,
    send_private_record, send_group_record,
    send_private_image, send_group_image,
    send_group_poke, send_private_poke
)
from typing import Any, Dict, Optional
from .user_profiles import update_user_interaction
from .emotion_engine import apply_emotion_event

@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    action_type: str  # 实际执行的动作
    message_id: Optional[int] = None
    error: Optional[str] = None
    message: Optional[str] = None
    fallback_chain: List[str] = None  # 应用的降级链
    execution_time_ms: float = 0.0
    
    def __post_init__(self):
        if self.fallback_chain is None:
            self.fallback_chain = []


# =========================
# 执行层归一化函数 - 防止补文本
# =========================

def normalize_decision_for_execution(decision: DecisionOutput) -> DecisionOutput:
    """
    归一化决策对象，确保执行层不会自作主张补文本
    
    硬规则：
    1. mode == ignore → 绝不发任何文本
    2. should_text == false 且 mode != voice → 绝不补文本
    3. meme 发失败 → 只有 should_text == true 才能回退文本
    4. delay_send 前 → 必须检查是不是最新请求
    5. 执行层不能自己造句
    
    Args:
        decision: 待归一化的 DecisionOutput
    
    Returns:
        归一化后的 DecisionOutput
    """
    if not decision:
        return decision
    
    plan = decision.response_plan or {}
    content = decision.content or {}
    
    mode = plan.get("mode", "text")
    should_text = bool(plan.get("should_text", True))
    
    text = clean_roxy_text(content.get("text", "") or "")
    voice_text = clean_roxy_text(content.get("voice_text", "") or "")
    meme_tag = content.get("meme_tag")
    meme_text = content.get("meme_text")
    
    # 规则 1：ignore 绝不发文本
    if mode == "ignore":
        content["text"] = ""
        content["voice_text"] = ""
        content["meme_tag"] = None
        content["meme_text"] = None
        plan["should_text"] = False
        return decision
    
    # 规则 2：should_text=false 时，不准补文本
    if not should_text and mode != "voice":
        content["text"] = ""
        content["voice_text"] = ""
    
    # 规则 3：voice 模式可以只保留 voice_text
    if mode == "voice":
        if not voice_text and text:
            content["voice_text"] = text
    
    # 规则 4：text_image 如果 should_text=false，只允许发图，不允许补字
    if mode == "text_image" and not should_text:
        content["text"] = ""
        content["voice_text"] = ""
    
    return decision


class MemeLibrary:
    """梗图库"""
    
    MEME_DIR = "./memes"
    
    # 梗图映射
    MEME_MAP = {
        "sneer": "sneer.jpg",           # 嘲笑
        "slap_table": "slap_table.jpg", # 拍桌子
        "speechless": "speechless.jpg", # 无言
        "smug": "smug.jpg",             # 自满
        "cold_stare": "cold_stare.jpg", # 冷眼
    }
    
    @classmethod
    def get_meme_path(cls, tag: Optional[str]) -> Optional[str]:
        """获取梗图路径"""
        if not tag or tag not in cls.MEME_MAP:
            return None
        
        path = os.path.join(cls.MEME_DIR, cls.MEME_MAP[tag])
        if os.path.exists(path):
            return os.path.abspath(path)
        
        return None
    
    @classmethod
    def create_dynamic_meme(
        cls,
        base_image_path: str,
        text: str,
        output_path: str
    ) -> bool:
        """
        动态生成梗图 - 在底图上叠字
        
        Args:
            base_image_path: 底图路径
            text: 要叠的文字
            output_path: 输出路径
        
        Returns:
            成功与否
        """
        try:
            if not os.path.exists(base_image_path):
                return False
            
            img = Image.open(base_image_path)
            draw = ImageDraw.Draw(img)
            
            # 尝试加载字体（Windows 字体）
            try:
                font = ImageFont.truetype(
                    "C:\\Windows\\Fonts\\msyhbd.ttc", 30
                )
            except:
                # 如果找不到，用默认字体
                font = ImageFont.load_default()
            
            # 计算文字位置（居中）
            img_width, img_height = img.size
            
            # 画文字背景（黑色半透明）
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            x = (img_width - text_width) // 2
            y = img_height - text_height - 20
            
            # 画黑色背景
            bg_box = [x - 10, y - 10, x + text_width + 10, y + text_height + 10]
            draw.rectangle(bg_box, fill=(0, 0, 0, 128))
            
            # 画白色文字
            draw.text((x, y), text, fill=(255, 255, 255), font=font)
            
            Path(os.path.dirname(output_path)).mkdir(exist_ok=True, parents=True)
            img.save(output_path, quality=90)
            
            return True
            
        except Exception as e:
            print(f"动态梗图生成失败: {e}")
            return False


class ActionExecutor:
    """动作执行器 - 严格遵循 5 条硬规则，支持用户级串行锁"""
    
    def __init__(self):
        """初始化执行器"""
        self.user_locks = defaultdict(asyncio.Lock)
        self.latest_req_id = defaultdict(int)
    
    def next_req_id(self, user_id: int) -> int:
        """获取该用户的下一个请求 ID"""
        self.latest_req_id[user_id] += 1
        return self.latest_req_id[user_id]
    
    # 执行优先级和降级链定义（仅供参考，实际不再使用）
    FALLBACK_CHAINS = {
        ResponseMode.VOICE: ["voice", "text"],           # 语音失败 → 文字
        ResponseMode.TEXT: ["text"],                     # 纯文字
        ResponseMode.TEXT_IMAGE: ["text_image", "text"], # 梗图失败 → 文字
        ResponseMode.IGNORE: ["ignore"],
        ResponseMode.DELAY: ["delay"],
    }
    
    async def execute_decision(
        self,
        decision: DecisionOutput,
        user_id: int,
        username: str,
        group_id: Optional[int] = None,
        req_id: Optional[int] = None,
        enable_grok_refine: bool = False,
        persona_config: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        执行 LLM 的决策，严格遵循 5 条执行层硬规则
        
        硬规则：
        1. mode == ignore → 绝不发任何文本
        2. should_text == false 且 mode != voice → 绝不补文本
        3. meme 发失败 → 只有 should_text == true 才能回退文本
        4. delay_send 发出前 → 必须检查是不是最新请求
        5. 执行层不能自己造句（不补充 "……" / "收到" / "嗯"）
        
        Args:
            decision: DecisionOutput 对象
            user_id: 用户ID
            username: 用户名
            group_id: 群ID（如果是群聊）
            req_id: 请求ID，用于防止旧请求延迟到达
            enable_grok_refine: 是否启用 Grok 润色（已弃用，保留向后兼容）
            persona_config: 人物档案配置
        
        Returns:
            ExecutionResult 包含执行结果
        """
        print(f"[executor] enter user_id={user_id}, username={username}, group_id={group_id}, req_id={req_id}")
        
        # 用户级串行化执行（防止同一用户并发冲突）
        async with self.user_locks[user_id]:
            print(f"[executor] lock acquired user_id={user_id}, req_id={req_id}")
            
            # 最后一次检查：是不是最新请求
            if req_id is not None and req_id != self.latest_req_id[user_id]:
                print(f"[executor] 旧请求被丢弃 user_id={user_id} req_id={req_id} latest={self.latest_req_id[user_id]}")
                return ExecutionResult(
                    success=True,
                    action_type="skip",
                    message="旧请求已被丢弃"
                )
            
            return await self._execute_decision_sync(
                decision, user_id, username, group_id, req_id
            )
    
    async def _execute_decision_sync(
        self,
        decision: DecisionOutput,
        user_id: int,
        username: str,
        group_id: Optional[int] = None,
        req_id: Optional[int] = None
    ) -> ExecutionResult:
        """
        同步执行决策的逻辑（由 execute_decision 在用户锁内调用）
        """
        start_time = time.time()
        
        try:
            # 第一步：归一化决策（防止补文本）
            decision = normalize_decision_for_execution(decision)
            
            # 第二步：更新用户交互统计
            update_user_interaction(user_id, username)
            
            # 第三步：应用情绪更新
            emotion_update = decision.emotion_update
            if emotion_update:
                emotion_dict = emotion_update if isinstance(emotion_update, dict) else emotion_update.to_dict() if hasattr(emotion_update, 'to_dict') else {}
                apply_emotion_event(
                    "user_interaction",
                    emotion_dict,
                    user_id=user_id,
                    group_id=group_id
                )
            
            # 第四步：读取决策参数
            plan = decision.response_plan or {}
            content = decision.content or {}
            
            mode = plan.get("mode", "text")
            action = plan.get("action", "none")
            should_text = bool(plan.get("should_text", True))
            delay_ms = int(plan.get("delay_ms", 0) or 0)
            
            text = content.get("text", "") or ""
            voice_text = content.get("voice_text", "") or ""
            meme_tag = content.get("meme_tag")
            meme_text = content.get("meme_text")
            
            print(f"[executor:sync] user_id={user_id}, mode={mode}, action={action}, should_text={should_text}, text={text!r}, voice_text={voice_text!r}, group_id={group_id}")
            
            # ==================== 执行矩阵：严格的规则驱动 ====================
            
            # 规则 1：ignore 模式 → 直接跳过，不发任何东西
            if mode == "ignore":
                print(f"[executor:sync] 规则 1 触发：ignore 模式，完全忽略")
                return ExecutionResult(
                    success=True,
                    action_type="ignore",
                    message="决策：忽略"
                )
            
            # 规则 2：delay 模式 → 延迟后重新检查再执行
            if mode == "delay" or action == "delay_send":
                print(f"[executor:sync] 规则 2 触发：delay 模式，转交延迟处理")
                return await self._execute_delay(
                    user_id, group_id, decision, delay_ms, req_id
                )
            
            # 规则 3：voice 模式 → 只发语音，不补文本
            if mode == "voice":
                print(f"[executor:sync] 规则 3 触发：voice 模式")
                if not voice_text:
                    print(f"[executor:sync] voice_text 为空，返回失败")
                    return ExecutionResult(
                        success=False,
                        action_type="skip",
                        message="empty_voice_text"
                    )
                return await self._execute_voice(user_id, group_id, voice_text)
            
            # 规则 4：text_image 模式 → 图文分支，失败时只有 should_text==true 才降级
            if mode == "text_image" or action == "meme":
                print(f"[executor:sync] 规则 4 触发：text_image 模式")
                meme_ok = False
                if meme_tag:
                    meme_ok = await self._execute_meme(
                        user_id, group_id, meme_tag, meme_text,
                        text if should_text and text else None
                    )
                
                if meme_ok:
                    return ExecutionResult(
                        success=True,
                        action_type="text_image"
                    )
                
                # 梗图没发出去，检查是否需要回退到文本
                if should_text and text:
                    print(f"[executor:sync] 梗图失败，降级到文本 should_text={should_text}")
                    return await self._execute_text(user_id, group_id, text)
                
                # 既没梗图也不发文本
                print(f"[executor:sync] 梗图不存在且 should_text=false，放弃发送")
                return ExecutionResult(
                    success=False,
                    action_type="skip",
                    message="meme不存在且should_text==false"
                )
            
            # 规则 5：普通文本模式 → 只有 should_text==true 才发
            if mode == "text":
                print(f"[executor:sync] 规则 5 触发：text 模式")
                if not should_text:
                    print(f"[executor:sync] should_text=false，放弃发送")
                    return ExecutionResult(
                        success=True,
                        action_type="skip",
                        message="should_text==false"
                    )
                if not text:
                    print(f"[executor:sync] 文本为空，返回失败")
                    return ExecutionResult(
                        success=False,
                        action_type="skip",
                        message="empty_text"
                    )
                return await self._execute_text(user_id, group_id, text)
            
            # 如果没有匹配任何规则
            print(f"[executor:sync] 未知mode: {mode}")
            return ExecutionResult(
                success=False,
                action_type="error",
                message=f"未知的mode: {mode}"
            )
        
        except Exception as e:
            print(f"[executor:sync] 异常: {e}")
            return ExecutionResult(
                success=False,
                action_type="error",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    async def _execute_delay(
        self,
        user_id: int,
        group_id: Optional[int],
        decision: DecisionOutput,
        delay_ms: int,
        req_id: Optional[int]
    ) -> ExecutionResult:
        """处理延迟执行（释放锁后再睡眠，避免阻塞其他请求）"""
        try:
            delay_ms = max(0, min(delay_ms or 0, 10000))  # 限制最长延迟 10 秒
            
            # 记录延迟请求标识
            print(f"[executor:delay] user_id={user_id}, req_id={req_id}, delay_ms={delay_ms}")
            
            # 延迟后检查是否已经过期（在锁外检查，避免阻塞）
            if req_id is not None and req_id != self.latest_req_id[user_id]:
                return ExecutionResult(
                    success=True,
                    action_type="skip",
                    message="延迟请求已过期（立即丢弃）"
                )
            
            # 只预留延迟，不做实际 sleep（返回给调用方处理）
            # 这样可以立即释放锁，让后续请求能被接收
            async def do_delayed_execution():
                try:
                    # 现在在后台任务中睡眠
                    await asyncio.sleep(delay_ms / 1000)
                    
                    # 再次检查是否过期
                    if req_id is not None and req_id != self.latest_req_id[user_id]:
                        print(f"[executor:delay] 延迟请求已过期，放弃执行 user_id={user_id} req_id={req_id}")
                        return
                    
                    # 变更为目标 mode（防止无限递归 delay）
                    target_mode = decision.response_plan.get("mode", "text")
                    if target_mode == "delay":
                        decision.response_plan["mode"] = "text"
                    if decision.response_plan.get("action") == "delay_send":
                        decision.response_plan["action"] = "none"
                    
                    print(f"[executor:delay] 执行延迟请求 user_id={user_id} req_id={req_id}")
                    
                    # 重新获取锁后执行（不能用 self.user_locks，会死锁）
                    # 应该创建一个后台任务，由事务循环处理
                    async with self.user_locks[user_id]:
                        # 再次检查是否过期（获得锁后最后检查）
                        if req_id is not None and req_id != self.latest_req_id[user_id]:
                            print(f"[executor:delay] 在锁内检查：请求已过期，放弃 user_id={user_id} req_id={req_id}")
                            return
                        
                        # 执行决策
                        result = await self._execute_decision_sync(decision, user_id, "delayed", group_id, req_id)
                        print(f"[executor:delay] 后台执行完成 user_id={user_id} action_type={result.action_type}")
                
                except Exception as e:
                    print(f"[executor:delay] 后台执行异常: {e}")
            
            # 把后台任务提交给事件循环
            asyncio.create_task(do_delayed_execution())
            
            # 立即返回，释放锁
            return ExecutionResult(
                success=True,
                action_type="delay",
                message=f"延迟 {delay_ms}ms 后执行（在后台任务中）"
            )
        
        except Exception as e:
            print(f"[executor:delay] 异常: {e}")
            return ExecutionResult(
                success=False,
                action_type="error",
                error=f"延迟执行异常: {e}"
            )
    
    async def _execute_voice(
        self,
        user_id: int,
        group_id: Optional[int],
        voice_text: str
    ) -> ExecutionResult:
        """执行语音发送（带日志和超时）"""
        try:
            if not voice_text or not voice_text.strip():
                print(f"[executor:voice] voice_text为空")
                return ExecutionResult(
                    success=False,
                    action_type="skip",
                    message="voice_text为空"
                )
            
            print(f"[executor:voice] starting user_id={user_id}, group_id={group_id}, voice_text={voice_text!r}")
            
            # 检查 TTS 是否可用
            if not is_tts_alive(TTS_GPU_IP, 8000):
                print(f"[executor:voice] TTS离线，无法发语音")
                return ExecutionResult(
                    success=False,
                    action_type="skip",
                    message="TTS离线"
                )
            
            # 合成语音（带 30 秒超时）
            try:
                print(f"[executor:voice] 正在合成语音...")
                wav_path = await asyncio.wait_for(
                    synthesize_tts(voice_text),
                    timeout=30
                )
                print(f"[executor:voice] 合成成功: {wav_path}")
            except asyncio.TimeoutError:
                print(f"[executor:voice] TTS合成超时（30秒）")
                return ExecutionResult(
                    success=False,
                    action_type="skip",
                    message="TTS合成超时"
                )
            except Exception as e:
                print(f"[executor:voice] TTS合成异常: {e}")
                return ExecutionResult(
                    success=False,
                    action_type="skip",
                    message=f"TTS合成失败: {e}"
                )
            
            # 发送语音（带 15 秒超时）
            try:
                if group_id:
                    print(f"[executor:voice] 发送到群 {group_id}")
                    result_dict = await asyncio.wait_for(
                        send_group_record(group_id, wav_path),
                        timeout=15
                    )
                else:
                    print(f"[executor:voice] 发送到私聊 {user_id}")
                    result_dict = await asyncio.wait_for(
                        send_private_record(user_id, wav_path),
                        timeout=15
                    )
                
                print(f"[executor:voice] OneBot返回 result={result_dict}")
            except asyncio.TimeoutError:
                print(f"[executor:voice] 发送超时（15秒） group_id={group_id} user_id={user_id}")
                return ExecutionResult(
                    success=False,
                    action_type="error",
                    error="语音发送超时（15s）"
                )
            
            if result_dict.get("status") == "ok" and result_dict.get("retcode") == 0:
                print(f"[executor:voice] 发送成功")
                return ExecutionResult(
                    success=True,
                    action_type="voice",
                    message_id=result_dict.get("data", {}).get("message_id")
                )
            else:
                print(f"[executor:voice] OneBot返回错误 status={result_dict.get('status')} retcode={result_dict.get('retcode')}")
                return ExecutionResult(
                    success=False,
                    action_type="error",
                    error=f"OneBot错误: {result_dict}"
                )
        
        except Exception as e:
            print(f"[executor:voice] 异常: {e}")
            return ExecutionResult(
                success=False,
                action_type="error",
                error=f"语音异常: {e}"
            )
    
    async def _execute_text(
        self,
        user_id: int,
        group_id: Optional[int],
        text: str
    ) -> ExecutionResult:
        """执行文本发送（带日志和超时）"""
        try:
            text = clean_roxy_text(text) or ""
            
            print(f"[executor:text] starting user_id={user_id}, group_id={group_id}, text={text!r}")
            
            if not text:
                print(f"[executor:text] 文本为空，返回失败")
                return ExecutionResult(
                    success=False,
                    action_type="skip",
                    message="文本为空"
                )
            
            # 发送文本（带 15 秒超时）
            try:
                if group_id:
                    result_dict = await asyncio.wait_for(
                        send_group_text(group_id, text),
                        timeout=15
                    )
                else:
                    result_dict = await asyncio.wait_for(
                        send_private_text(user_id, text),
                        timeout=15
                    )
                
                print(f"[executor:text] OneBot返回 result={result_dict}")
            except asyncio.TimeoutError:
                print(f"[executor:text] OneBot超时（15秒） group_id={group_id} user_id={user_id}")
                return ExecutionResult(
                    success=False,
                    action_type="error",
                    error="文本发送超时（15s）"
                )
            
            if result_dict.get("status") == "ok" and result_dict.get("retcode") == 0:
                print(f"[executor:text] 发送成功")
                return ExecutionResult(
                    success=True,
                    action_type="text",
                    message_id=result_dict.get("data", {}).get("message_id")
                )
            else:
                print(f"[executor:text] OneBot返回错误 status={result_dict.get('status')} retcode={result_dict.get('retcode')}")
                return ExecutionResult(
                    success=False,
                    action_type="error",
                    error=f"发送失败: {result_dict}"
                )
        
        except Exception as e:
            print(f"[executor:text] 异常: {e}")
            return ExecutionResult(
                success=False,
                action_type="error",
                error=f"文本异常: {e}"
            )
    
    async def _execute_meme(
        self,
        user_id: int,
        group_id: Optional[int],
        meme_tag: str,
        meme_text: Optional[str],
        accompanying_text: Optional[str] = None
    ) -> bool:
        """
        执行梗图发送
        
        返回 True 表示梗图本身发送成功
        返回 False 表示梗图发送失败（调用方需要决定是否降级到文本）
        """
        try:
            # 获取梗图路径
            meme_path = MemeLibrary.get_meme_path(meme_tag)
            if not meme_path:
                print(f"[梗图] 梗图不存在: {meme_tag}")
                return False
            
            # 如果有梗图文字，则生成动态梗图
            if meme_text:
                try:
                    output_path = f"./cache/dynamic_memes/{user_id}_{int(time.time())}.jpg"
                    if MemeLibrary.create_dynamic_meme(meme_path, meme_text, output_path):
                        meme_path = output_path
                        print(f"[梗图] 动态梗图生成成功")
                    else:
                        print(f"[梗图] 动态梗图生成失败，使用原图")
                except Exception as e:
                    print(f"[梗图] 动态生成异常: {e}")
            
            # 发送梗图（可能带文字）
            if accompanying_text:
                if group_id:
                    await send_group_text(group_id, accompanying_text)
                else:
                    await send_private_text(user_id, accompanying_text)
            
            # 发送梗图
            if meme_path and os.path.exists(meme_path):
                if group_id:
                    result_dict = await send_group_image(group_id, meme_path)
                else:
                    result_dict = await send_private_image(user_id, meme_path)
                
                if result_dict.get("status") == "ok" and result_dict.get("retcode") == 0:
                    print(f"[梗图] 发送成功")
                    return True
            
            return False
        
        except Exception as e:
            print(f"[梗图] 异常: {e}")
            return False
    



# ==================== 梗图映射表 ====================

MEME_MAP = {
    "sweat": [
        "memes/sweat_01.jpg",
        "memes/sweat_02.jpg",
    ],
    "stare": [
        "memes/stare_01.jpg",
    ],
    "mock": [
        "memes/mock_01.jpg",
        "memes/mock_02.jpg",
    ],
    "silent": [
        "memes/silent_01.jpg",
    ],
    "disgust": [
        "memes/disgust_01.jpg",
    ],
}


import random


def pick_meme_file(tag: str) -> Optional[str]:
    """
    随机选择一个梗图
    
    Args:
        tag: 梗图标签
    
    Returns:
        梗图路径或 None
    """
    files = MEME_MAP.get(tag, [])
    if not files:
        return None
    return random.choice(files)



# 全局单例和便利函数
action_executor = ActionExecutor()


async def execute_decision(
    decision: DecisionOutput,
    user_id: int,
    username: str,
    group_id: Optional[int] = None,
    req_id: Optional[int] = None,
    enable_grok_refine: bool = False,
    persona_config: Optional[Dict[str, Any]] = None
) -> ExecutionResult:
    """
    执行决策的全局便利函数 - 返回 ExecutionResult 包含详细的执行信息
    
    Args:
        decision: DecisionOutput 对象
        user_id: 用户ID
        username: 用户名
        group_id: 群ID（如果是群聊）
        req_id: 请求ID，用于防止旧请求延迟到达
        enable_grok_refine: 是否启用 Grok 润色（已弃用）
        persona_config: 人物档案配置
    
    Returns:
        ExecutionResult 包含执行结果
    """
    return await action_executor.execute_decision(
        decision, 
        user_id, 
        username, 
        group_id,
        req_id,
        enable_grok_refine,
        persona_config
    )
