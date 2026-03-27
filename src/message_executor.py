import asyncio
import random
from pathlib import Path
from typing import Optional, Dict, Any, List

import httpx

from config.config import (
    NAPCAT_BASE_URL,
    NAPCAT_ACCESS_TOKEN,
    MEME_DIR,
)

from .core.decision_engine import DecisionOutput


# =========================
# 适配你当前的 tts.py
# =========================
try:
    from .utils.tts import synthesize_tts, is_tts_alive
except Exception:
    synthesize_tts = None
    is_tts_alive = None


MEME_MAP = {
    "sweat": [
        "sweat_01.jpg",
        "sweat_02.jpg",
        "sweat_03.png",
    ],
    "stare": [
        "stare_01.jpg",
        "stare_02.png",
    ],
    "mock": [
        "mock_01.jpg",
        "mock_02.png",
    ],
    "silent": [
        "silent_01.jpg",
        "silent_02.png",
    ],
    "disgust": [
        "disgust_01.jpg",
        "disgust_02.png",
    ],
}


class MessageExecutor:
    def __init__(self):
        self.base_url = NAPCAT_BASE_URL.rstrip("/")
        self.token = NAPCAT_ACCESS_TOKEN.strip() if NAPCAT_ACCESS_TOKEN else ""

    # =========================
    # 基础 HTTP
    # =========================

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _call_api(self, action: str, **params) -> Dict[str, Any]:
        url = f"{self.base_url}/{action.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=self._headers(), json=params)
            resp.raise_for_status()
            data = resp.json()

        status = data.get("status")
        retcode = data.get("retcode", 0)
        if status not in [None, "ok"] and retcode != 0:
            raise RuntimeError(f"NapCat API failed: action={action}, data={data}")

        return data

    # =========================
    # 文件 / 资源
    # =========================

    def _to_file_uri(self, path: str) -> str:
        return Path(path).resolve().as_uri()

    def _scan_meme_candidates(self, tag: str) -> List[str]:
        meme_root = Path(MEME_DIR)
        if not meme_root.exists():
            return []

        candidates: List[str] = []

        for name in MEME_MAP.get(tag, []):
            p = meme_root / name
            if p.exists() and p.is_file():
                candidates.append(str(p.resolve()))

        subdir = meme_root / tag
        if subdir.exists() and subdir.is_dir():
            for p in subdir.iterdir():
                if p.is_file() and p.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                    candidates.append(str(p.resolve()))

        for p in meme_root.iterdir():
            if p.is_file() and p.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                if tag.lower() in p.name.lower():
                    candidates.append(str(p.resolve()))

        return list(dict.fromkeys(candidates))

    def pick_meme_file(self, tag: str) -> Optional[str]:
        if not tag or tag == "none":
            return None
        candidates = self._scan_meme_candidates(tag)
        if not candidates:
            return None
        return random.choice(candidates)

    # =========================
    # 消息段构造
    # =========================

    def _seg_text(self, text: str) -> Dict[str, Any]:
        return {"type": "text", "data": {"text": text}}

    def _seg_reply(self, message_id: int) -> Dict[str, Any]:
        return {"type": "reply", "data": {"id": str(message_id)}}

    def _seg_image(self, file_path: str) -> Dict[str, Any]:
        return {"type": "image", "data": {"file": self._to_file_uri(file_path)}}

    def _seg_record(self, file_path: str) -> Dict[str, Any]:
        return {"type": "record", "data": {"file": self._to_file_uri(file_path)}}

    def _seg_music(self, music_type: str, music_id: str) -> Dict[str, Any]:
        return {
            "type": "music",
            "data": {
                "type": music_type,
                "id": str(music_id)
            }
        }

    # =========================
    # 发送方法
    # =========================

    async def send_private_segments(self, user_id: int, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        return await self._call_api(
            "send_private_msg",
            user_id=user_id,
            message=segments
        )

    async def send_group_segments(self, group_id: int, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        return await self._call_api(
            "send_group_msg",
            group_id=group_id,
            message=segments
        )

    async def send_segments(
        self,
        source: str,
        user_id: int,
        group_id: int,
        segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if source == "group":
            return await self.send_group_segments(group_id=group_id, segments=segments)
        return await self.send_private_segments(user_id=user_id, segments=segments)

    async def send_text(
        self,
        source: str,
        user_id: int,
        group_id: int,
        text: str,
        reply_to_message_id: Optional[int] = None
    ) -> Dict[str, Any]:
        segments: List[Dict[str, Any]] = []
        if reply_to_message_id:
            segments.append(self._seg_reply(reply_to_message_id))
        segments.append(self._seg_text(text))
        return await self.send_segments(source, user_id, group_id, segments)

    async def send_image(
        self,
        source: str,
        user_id: int,
        group_id: int,
        image_path: str,
        text: Optional[str] = None,
        reply_to_message_id: Optional[int] = None
    ) -> Dict[str, Any]:
        segments: List[Dict[str, Any]] = []
        if reply_to_message_id:
            segments.append(self._seg_reply(reply_to_message_id))
        if text:
            segments.append(self._seg_text(text))
        segments.append(self._seg_image(image_path))
        return await self.send_segments(source, user_id, group_id, segments)

    async def send_voice(
        self,
        source: str,
        user_id: int,
        group_id: int,
        voice_path: str,
        reply_to_message_id: Optional[int] = None
    ) -> Dict[str, Any]:
        segments: List[Dict[str, Any]] = []
        if reply_to_message_id:
            segments.append(self._seg_reply(reply_to_message_id))
        segments.append(self._seg_record(voice_path))
        return await self.send_segments(source, user_id, group_id, segments)

    async def send_music(
        self,
        source: str,
        user_id: int,
        group_id: int,
        music_type: str,
        music_id: str,
        reply_to_message_id: Optional[int] = None
    ) -> Dict[str, Any]:
        segments: List[Dict[str, Any]] = []
        if reply_to_message_id:
            segments.append(self._seg_reply(reply_to_message_id))
        segments.append(self._seg_music(music_type, music_id))
        return await self.send_segments(source, user_id, group_id, segments)

    async def send_poke(
        self,
        source: str,
        user_id: int,
        group_id: int
    ) -> Optional[Dict[str, Any]]:
        if source != "group" or not group_id:
            return None

        candidate_actions = [
            "send_group_poke",
            "group_poke",
        ]

        last_error = None
        for action in candidate_actions:
            try:
                return await self._call_api(
                    action,
                    group_id=group_id,
                    user_id=user_id
                )
            except Exception as e:
                last_error = e

        if last_error:
            print(f"[message_executor] poke failed: {last_error}")
        return None

    # =========================
    # 行为执行
    # =========================

    def _default_delay_ms(self, decision: DecisionOutput) -> int:
        plan = decision.response_plan or {}
        style = plan.get("style", "cold")
        intensity = float(plan.get("intensity", 0.5) or 0.5)

        if style == "cold":
            return random.randint(1200, 2800)
        if style == "sarcastic":
            return random.randint(800, 1800)
        if style == "playful":
            return random.randint(500, 1200)
        if style == "soft":
            return random.randint(300, 900)

        base = 800 + int(intensity * 1200)
        return max(300, min(base, 3000))

    async def _maybe_delay(self, decision: DecisionOutput):
        plan = decision.response_plan or {}
        action = plan.get("action", "none")
        mode = plan.get("mode", "text")
        delay_ms = int(plan.get("delay_ms", 0) or 0)

        if action == "delay_send" or mode == "delay":
            if delay_ms <= 0:
                delay_ms = self._default_delay_ms(decision)
            await asyncio.sleep(delay_ms / 1000)

    async def _execute_meme_action(
        self,
        decision: DecisionOutput,
        source: str,
        user_id: int,
        group_id: int,
        reply_to_message_id: Optional[int]
    ) -> Dict[str, Any]:
        plan = decision.response_plan or {}
        content = decision.content or {}

        should_text = bool(plan.get("should_text", True))
        text = (content.get("text") or "").strip()
        meme_tag = (content.get("meme_tag") or plan.get("reaction_mode") or "").strip().lower()

        image_path = self.pick_meme_file(meme_tag)
        if not image_path:
            fallback_text = text or "……"
            return await self.send_text(
                source=source,
                user_id=user_id,
                group_id=group_id,
                text=fallback_text,
                reply_to_message_id=reply_to_message_id
            )

        if not should_text or not text:
            segments: List[Dict[str, Any]] = []
            if reply_to_message_id:
                segments.append(self._seg_reply(reply_to_message_id))
            segments.append(self._seg_image(image_path))
            return await self.send_segments(source, user_id, group_id, segments)

        return await self.send_image(
            source=source,
            user_id=user_id,
            group_id=group_id,
            image_path=image_path,
            text=text,
            reply_to_message_id=reply_to_message_id
        )

    async def _execute_voice_action(
        self,
        decision: DecisionOutput,
        source: str,
        user_id: int,
        group_id: int,
        reply_to_message_id: Optional[int]
    ) -> Dict[str, Any]:
        content = decision.content or {}
        voice_text = (content.get("voice_text") or content.get("text") or "").strip()

        if not voice_text:
            voice_text = "……"

        if synthesize_tts is None:
            return await self.send_text(
                source=source,
                user_id=user_id,
                group_id=group_id,
                text=voice_text,
                reply_to_message_id=reply_to_message_id
            )

        try:
            if is_tts_alive is not None and not is_tts_alive():
                print("[message_executor] TTS offline, fallback to text")
                return await self.send_text(
                    source=source,
                    user_id=user_id,
                    group_id=group_id,
                    text=voice_text,
                    reply_to_message_id=reply_to_message_id
                )

            voice_path = await synthesize_tts(voice_text)

            if not voice_path or not Path(voice_path).exists():
                return await self.send_text(
                    source=source,
                    user_id=user_id,
                    group_id=group_id,
                    text=voice_text,
                    reply_to_message_id=reply_to_message_id
                )

            return await self.send_voice(
                source=source,
                user_id=user_id,
                group_id=group_id,
                voice_path=voice_path,
                reply_to_message_id=reply_to_message_id
            )

        except Exception as e:
            print(f"[message_executor] voice synth failed: {e}")
            return await self.send_text(
                source=source,
                user_id=user_id,
                group_id=group_id,
                text=voice_text,
                reply_to_message_id=reply_to_message_id
            )

    async def _execute_music_action(
        self,
        decision: DecisionOutput,
        source: str,
        user_id: int,
        group_id: int,
        reply_to_message_id: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        content = decision.content or {}
        music_type = (content.get("music_type") or "").strip()
        music_id = (content.get("music_id") or "").strip()

        if not music_type or not music_id:
            return None

        return await self.send_music(
            source=source,
            user_id=user_id,
            group_id=group_id,
            music_type=music_type,
            music_id=music_id,
            reply_to_message_id=reply_to_message_id
        )

    async def execute_decision(
        self,
        decision: DecisionOutput,
        user_id: int,
        source: str = "private",
        group_id: int = 0,
        reply_to_message_id: Optional[int] = None
    ) -> Dict[str, Any]:
        plan = decision.response_plan or {}
        content = decision.content or {}

        action = plan.get("action", "none")
        mode = plan.get("mode", "text")
        should_text = bool(plan.get("should_text", True))

        text = (content.get("text") or "").strip()
        voice_text = (content.get("voice_text") or text).strip()

        result: Dict[str, Any] = {
            "sent": False,
            "action": action,
            "mode": mode,
            "detail": None,
        }

        if mode == "ignore":
            result["detail"] = "ignored"
            return result

        await self._maybe_delay(decision)

        effective_reply_id = reply_to_message_id
        if action == "quote_reply" and not effective_reply_id:
            action = "none"

        if action == "music":
            music_ret = await self._execute_music_action(
                decision=decision,
                source=source,
                user_id=user_id,
                group_id=group_id,
                reply_to_message_id=effective_reply_id
            )
            if music_ret:
                result["sent"] = True
                result["detail"] = music_ret
                return result

        if action == "voice" or mode == "voice":
            voice_ret = await self._execute_voice_action(
                decision=decision,
                source=source,
                user_id=user_id,
                group_id=group_id,
                reply_to_message_id=effective_reply_id
            )
            result["sent"] = True
            result["detail"] = voice_ret
            return result

        if action == "meme" or mode == "text_image":
            meme_ret = await self._execute_meme_action(
                decision=decision,
                source=source,
                user_id=user_id,
                group_id=group_id,
                reply_to_message_id=effective_reply_id
            )
            result["sent"] = True
            result["detail"] = meme_ret
            return result

        if should_text and text:
            text_ret = await self.send_text(
                source=source,
                user_id=user_id,
                group_id=group_id,
                text=text,
                reply_to_message_id=effective_reply_id
            )
            result["sent"] = True
            result["detail"] = text_ret

        if action == "poke":
            if result["sent"]:
                await asyncio.sleep(random.uniform(0.2, 0.8))
            poke_ret = await self.send_poke(
                source=source,
                user_id=user_id,
                group_id=group_id
            )
            result["sent"] = result["sent"] or (poke_ret is not None)
            result["detail"] = {
                "message": result["detail"],
                "poke": poke_ret
            }
            return result

        if not result["sent"]:
            fallback = text or voice_text or "……"
            text_ret = await self.send_text(
                source=source,
                user_id=user_id,
                group_id=group_id,
                text=fallback,
                reply_to_message_id=effective_reply_id
            )
            result["sent"] = True
            result["detail"] = text_ret

        return result


message_executor = MessageExecutor()


async def execute_message(
    decision: DecisionOutput,
    user_id: int,
    source: str = "private",
    group_id: int = 0,
    reply_to_message_id: Optional[int] = None
) -> Dict[str, Any]:
    return await message_executor.execute_decision(
        decision=decision,
        user_id=user_id,
        source=source,
        group_id=group_id,
        reply_to_message_id=reply_to_message_id
    )