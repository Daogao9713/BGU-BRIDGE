"""
动作执行器 - 执行 LLM 做出的决策
支持明确的降级链和执行失败恢复
"""
import asyncio
import os
import time
from typing import Optional, Dict, Tuple, List
from pathlib import Path
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
from .decision_engine import DecisionOutput, ResponseMode
from ..utils.tts import synthesize_tts, is_tts_alive
from config.config import TTS_GPU_IP
from ..interfaces.onebot_client import (
    send_private_text, send_group_text,
    send_private_record, send_group_record,
    send_private_image, send_group_image,
    send_group_poke, send_private_poke
)
from ..utils.content_refiner import refine_content_with_grok
from typing import Any, Dict, Optional
from .user_profiles import update_user_interaction
from .emotion_engine import apply_emotion_event  # 请根据你实际的文件名修改

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
    """动作执行器 - 支持降级链"""
    
    # 执行优先级和降级链定义
    FALLBACK_CHAINS = {
        ResponseMode.VOICE: ["voice", "text"],           # 语音失败 → 文字
        ResponseMode.TEXT: ["text"],                     # 纯文字
        ResponseMode.TEXT_IMAGE: ["text_image", "text"], # 梗图失败 → 文字
        ResponseMode.IGNORE: ["ignore"],
        ResponseMode.DELAY: ["delay"],
    }
    
    @staticmethod
    async def execute_decision(
        decision: DecisionOutput,
        user_id: int,
        username: str,
        group_id: Optional[int] = None,
        enable_grok_refine: bool = False,
        persona_config: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        执行 LLM 的决策，支持新的字段分流 + 可选的 Grok 润色
        
        Args:
            decision: DecisionOutput 对象
            user_id: 用户ID
            username: 用户名
            group_id: 群ID（如果是群聊）
            enable_grok_refine: 是否启用 Grok 润色
            persona_config: 人物档案配置
        
        Returns:
            ExecutionResult 包含执行结果和降级信息
        """
        start_time = time.time()
        result = None
        
        try:
            # 更新用户交互统计
            update_user_interaction(user_id, username)
            
            # 应用情绪更新
            emotion_update = decision.emotion_update
            if emotion_update:
                emotion_dict = emotion_update.to_dict() if hasattr(emotion_update, 'to_dict') else emotion_update
                apply_emotion_event(
                    "user_interaction",
                    emotion_dict,
                    user_id=user_id,
                    group_id=group_id
                )
            
            # 可选：用 Grok 润色文案（方案 B）
            decision_content = decision.content
            if enable_grok_refine and decision_content:
                print(f"[Grok 润色] 开始润色文案")
                decision_content = await refine_content_with_grok(
                    decision_content,
                    decision.response_plan,
                    persona_config
                )
                print(f"[Grok 润色] 完成 → {decision_content}")
            
            # ==================== 读取新字段，分流处理 ====================
            response_plan = decision.response_plan or {}
            content = decision_content or {}
            
            action = response_plan.get("action")  # "send", "delay_send", "poke", "meme"
            reaction_mode = response_plan.get("reaction_mode")  # "voice", "text", etc
            delay_ms = response_plan.get("delay_ms", 0)
            should_text = response_plan.get("should_text", True)
            
            meme_tag = content.get("meme_tag")
            meme_text = content.get("meme_text")
            text = content.get("text") or ""
            voice_text = content.get("voice_text") or text
            
            # 处理延迟
            if action == "delay_send" and delay_ms > 0:
                print(f"[延迟] 等待 {delay_ms}ms")
                await asyncio.sleep(delay_ms / 1000)
            
            # 处理 poke 动作
            if action == "poke":
                result = await ActionExecutor._execute_poke(user_id, group_id)
                if result:
                    result.execution_time_ms = (time.time() - start_time) * 1000
                    return result
            
            # 处理梗图动作（可能只有梗图，没有文本）
            if action == "meme" or reaction_mode == "text_image" or (action == "send" and meme_tag):
                result = await ActionExecutor._execute_text_image_new(
                    text, meme_tag, meme_text, should_text, user_id, group_id
                )
                if result:
                    result.execution_time_ms = (time.time() - start_time) * 1000
                    if result.success:
                        return result
            
            # 处理语音
            if reaction_mode == "voice":
                if not is_tts_alive(TTS_GPU_IP, 8000):
                    print("[探针] TTS 终端未开启，自动降级为 text 模式")
                else:
                    result = await ActionExecutor._execute_voice(
                        decision, user_id, group_id
                    )
                    if result:
                        result.execution_time_ms = (time.time() - start_time) * 1000
                        if result.success:
                            return result
            
            # 降级到纯文本
            if text:
                result = await ActionExecutor._execute_text(
                    decision, user_id, group_id
                )
                if result:
                    result.execution_time_ms = (time.time() - start_time) * 1000
                    if result.success:
                        return result
            
            # 处理 ignore/delay
            if action == "ignore":
                result = ExecutionResult(
                    success=True,
                    action_type="ignore",
                    message="决策：忽略"
                )
                result.execution_time_ms = (time.time() - start_time) * 1000
                return result
            
            if action == "delay":
                result = ExecutionResult(
                    success=True,
                    action_type="delay",
                    message="决策：延迟回复"
                )
                result.execution_time_ms = (time.time() - start_time) * 1000
                return result
            
            # 默认失败
            return ExecutionResult(
                success=False,
                action_type="error",
                error="没有可用的执行方式",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        
        except Exception as e:
            print(f"[错误] 执行决策异常: {e}")
            return ExecutionResult(
                success=False,
                action_type="error",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    @staticmethod
    async def _execute_voice(
        decision: DecisionOutput,
        user_id: int,
        group_id: Optional[int] = None
    ) -> ExecutionResult:
        """执行语音模式（优先级最高）"""
        try:
            content = decision.content or {}
            voice_text = content.get("voice_text") or content.get("text")
            
            if not voice_text:
                return ExecutionResult(
                    success=False,
                    action_type="voice",
                    error="没有语音文本"
                )
            
            # 合成语音（最可能失败的步骤）
            try:
                wav_path = await synthesize_tts(voice_text)
                print(f"[语音] 合成成功: {wav_path}")
            except Exception as e:
                return ExecutionResult(
                    success=False,
                    action_type="voice",
                    error=f"TTS 合成失败: {e}"
                )
            
            # 发送语音
            try:
                if group_id:
                    result_dict = await send_group_record(group_id, wav_path)
                else:
                    result_dict = await send_private_record(user_id, wav_path)
                
                if result_dict.get("status") == "ok" and result_dict.get("retcode") == 0:
                    print(f"[语音] 发送成功")
                    return ExecutionResult(
                        success=True,
                        action_type="voice",
                        message_id=result_dict.get("data", {}).get("message_id")
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        action_type="voice",
                        error=f"OneBot 返回错误: {result_dict}"
                    )
            
            except Exception as e:
                return ExecutionResult(
                    success=False,
                    action_type="voice",
                    error=f"发送语音异常: {e}"
                )
        
        except Exception as e:
            return ExecutionResult(
                success=False,
                action_type="voice",
                error=f"未知错误: {e}"
            )
    
    @staticmethod
    async def _execute_text(
        decision: DecisionOutput,
        user_id: int,
        group_id: Optional[int] = None
    ) -> ExecutionResult:
        """执行文本模式（最稳定的模式）"""
        try:
            text = (decision.content or {}).get("text")
            
            if not text:
                return ExecutionResult(
                    success=False,
                    action_type="text",
                    error="没有文本内容"
                )
            
            if group_id:
                result_dict = await send_group_text(group_id, text)
            else:
                result_dict = await send_private_text(user_id, text)
            
            if result_dict.get("status") == "ok" and result_dict.get("retcode") == 0:
                print(f"[文本] 发送成功")
                return ExecutionResult(
                    success=True,
                    action_type="text",
                    message_id=result_dict.get("data", {}).get("message_id")
                )
            else:
                return ExecutionResult(
                    success=False,
                    action_type="text",
                    error=f"发送失败: {result_dict}"
                )
        
        except Exception as e:
            return ExecutionResult(
                success=False,
                action_type="text",
                error=f"发送文本异常: {e}"
            )
    
    @staticmethod
    async def _execute_text_image(
        decision: DecisionOutput,
        user_id: int,
        group_id: Optional[int] = None
    ) -> ExecutionResult:
        """执行文本+梗图模式（复杂，易失败，故排在较后）"""
        try:
            content = decision.content or {}
            text = content.get("text")
            meme_tag = content.get("meme_tag")
            meme_text = content.get("meme_text")
            
            if not text:
                return ExecutionResult(
                    success=False,
                    action_type="text_image",
                    error="没有文本内容"
                )
            
            # 获取梗图路径
            meme_path = None
            try:
                meme_path = MemeLibrary.get_meme_path(meme_tag)
            except Exception as e:
                print(f"[梗图] 获取梗图失败: {e}")
            
            # 如果没有梗图，只发文本
            if not meme_path:
                print(f"[梗图] 梗图不存在，降级为纯文本")
                return ExecutionResult(
                    success=False,
                    action_type="text_image",
                    error="梗图不存在"
                )
            
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
                    print(f"[梗图] 动态梗图生成异常: {e}")
            
            # 发送文本 + 梗图
            try:
                if group_id:
                    # 先发文本
                    result_text = await send_group_text(group_id, text)
                    
                    # 再发梗图
                    if meme_path and os.path.exists(meme_path):
                        result_image = await send_group_image(group_id, meme_path)
                        text_ok = result_text.get("status") == "ok" and result_text.get("retcode") == 0
                        image_ok = result_image.get("status") == "ok" and result_image.get("retcode") == 0
                    else:
                        text_ok = result_text.get("status") == "ok" and result_text.get("retcode") == 0
                        image_ok = False
                else:
                    # 先发文本
                    result_text = await send_private_text(user_id, text)
                    
                    # 再发梗图
                    if meme_path and os.path.exists(meme_path):
                        result_image = await send_private_image(user_id, meme_path)
                        text_ok = result_text.get("status") == "ok" and result_text.get("retcode") == 0
                        image_ok = result_image.get("status") == "ok" and result_image.get("retcode") == 0
                    else:
                        text_ok = result_text.get("status") == "ok" and result_text.get("retcode") == 0
                        image_ok = False
                
                if text_ok:
                    if image_ok:
                        print(f"[文本+梗图] 发送成功")
                        return ExecutionResult(
                            success=True,
                            action_type="text_image"
                        )
                    else:
                        # 文本成功，梗图失败
                        print(f"[文本+梗图] 梗图发送失败，但文本已发送")
                        return ExecutionResult(
                            success=True,
                            action_type="text_image",
                            message="文本已发送，梗图发送失败"
                        )
                else:
                    return ExecutionResult(
                        success=False,
                        action_type="text_image",
                        error="文本发送失败"
                    )
            
            except Exception as e:
                print(f"[梗图] 发送异常: {e}")
                return ExecutionResult(
                    success=False,
                    action_type="text_image",
                    error=f"发送异常: {e}"
                )
        
        except Exception as e:
            return ExecutionResult(
                success=False,
                action_type="text_image",
                error=f"未知错误: {e}"
            )
    
    @staticmethod
    async def _execute_poke(
        user_id: int,
        group_id: Optional[int] = None
    ) -> ExecutionResult:
        """执行戳一戳动作"""
        try:
            if group_id:
                result_dict = await send_group_poke(group_id, user_id)
            else:
                result_dict = await send_private_poke(user_id)
            
            if result_dict.get("status") == "ok" and result_dict.get("retcode") == 0:
                print(f"[戳一戳] 发送成功")
                return ExecutionResult(
                    success=True,
                    action_type="poke"
                )
            else:
                return ExecutionResult(
                    success=False,
                    action_type="poke",
                    error=f"戳一戳失败: {result_dict}"
                )
        
        except Exception as e:
            return ExecutionResult(
                success=False,
                action_type="poke",
                error=f"戳一戳异常: {e}"
            )
    
    @staticmethod
    async def _execute_text_image_new(
        text: str,
        meme_tag: Optional[str],
        meme_text: Optional[str],
        should_text: bool,
        user_id: int,
        group_id: Optional[int] = None
    ) -> ExecutionResult:
        """
        执行新的文本+梗图模式 - 支持 should_text 字段
        
        Args:
            text: 主文本
            meme_tag: 梗图标签
            meme_text: 梗图上的文字
            should_text: 是否应该发文本
            user_id: 用户ID
            group_id: 群ID（如果是群聊）
        
        Returns:
            ExecutionResult
        """
        try:
            # 获取梗图路径
            meme_path = None
            if meme_tag:
                try:
                    meme_path = MemeLibrary.get_meme_path(meme_tag)
                except Exception as e:
                    print(f"[梗图] 获取梗图失败: {e}")
            
            # 如果没有梗图，只发文本（如果 should_text）
            if not meme_path:
                print(f"[梗图] 梗图不存在 ({meme_tag})")
                if should_text and text:
                    if group_id:
                        result_dict = await send_group_text(group_id, text)
                    else:
                        result_dict = await send_private_text(user_id, text)
                    
                    if result_dict.get("status") == "ok" and result_dict.get("retcode") == 0:
                        return ExecutionResult(
                            success=True,
                            action_type="text_image",
                            message="仅发送文本"
                        )
                
                return ExecutionResult(
                    success=False,
                    action_type="text_image",
                    error="梗图不存在，文本为空或不发送"
                )
            
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
                    print(f"[梗图] 动态梗图生成异常: {e}")
            
            # 发送文本 + 梗图
            try:
                if group_id:
                    # 先发文本（如果 should_text）
                    text_ok = True
                    if should_text and text:
                        result_text = await send_group_text(group_id, text)
                        text_ok = result_text.get("status") == "ok" and result_text.get("retcode") == 0
                    
                    # 再发梗图
                    if meme_path and os.path.exists(meme_path):
                        result_image = await send_group_image(group_id, meme_path)
                        image_ok = result_image.get("status") == "ok" and result_image.get("retcode") == 0
                    else:
                        image_ok = False
                else:
                    # 先发文本（如果 should_text）
                    text_ok = True
                    if should_text and text:
                        result_text = await send_private_text(user_id, text)
                        text_ok = result_text.get("status") == "ok" and result_text.get("retcode") == 0
                    
                    # 再发梗图
                    if meme_path and os.path.exists(meme_path):
                        result_image = await send_private_image(user_id, meme_path)
                        image_ok = result_image.get("status") == "ok" and result_image.get("retcode") == 0
                    else:
                        image_ok = False
                
                if image_ok:
                    print(f"[文本+梗图] 发送成功")
                    return ExecutionResult(
                        success=True,
                        action_type="text_image"
                    )
                elif text_ok:
                    # 梗图失败但文本成功
                    print(f"[文本+梗图] 梗图发送失败，但文本已发送")
                    return ExecutionResult(
                        success=True,
                        action_type="text_image",
                        message="文本已发送，梗图发送失败"
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        action_type="text_image",
                        error="文本和梗图都未成功发送"
                    )
            
            except Exception as e:
                print(f"[梗图] 发送异常: {e}")
                return ExecutionResult(
                    success=False,
                    action_type="text_image",
                    error=f"发送异常: {e}"
                )
        
        except Exception as e:
            return ExecutionResult(
                success=False,
                action_type="text_image",
                error=f"未知错误: {e}"
            )


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
    enable_grok_refine: bool = False,
    persona_config: Optional[Dict[str, Any]] = None
) -> ExecutionResult:
    """执行决策 - 返回 ExecutionResult 包含详细的执行信息，支持 Grok 润色"""
    return await action_executor.execute_decision(
        decision, 
        user_id, 
        username, 
        group_id,
        enable_grok_refine,
        persona_config
    )
