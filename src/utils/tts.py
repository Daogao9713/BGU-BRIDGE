# tts.py
import os
import uuid
import socket
import httpx
from config.config import TTS_BASE_URL, TTS_INFER_URL, TTS_SPEAKER

OUT_DIR = "./cache/wav"
os.makedirs(OUT_DIR, exist_ok=True)


def is_tts_alive(host: str = "127.0.0.1", port: int = 8000, timeout: float = 0.1) -> bool:
    """
    极速探测 TTS 终端是否在线。
    使用 socket 连接进行最小化开销的活性检测。
    
    Args:
        host: TTS 服务器地址，默认本地
        port: TTS 服务器端口，默认 8000
        timeout: 连接超时时间，默认 0.1 秒
    
    Returns:
        True 表示 TTS 服务在线，False 表示离线或无法连接
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

async def synthesize_tts(text: str, character_name: str = None) -> str:
    if not text:
        raise ValueError("text 不能为空")

    speaker = character_name or TTS_SPEAKER

    payload = {
        "version": "v4",
        "model_name": speaker,
        "text": text,
        "text_lang": "中文",
        "prompt_text_lang": "中文",
        "emotion": "默认",
        "speed_facter": 1,
        "top_k": 10,
        "top_p": 1,
        "temperature": 1,
        "batch_size": 10,
        "batch_threshold": 0.75,
        "text_split_method": "按标点符号切",
        "parallel_infer": True,
        "split_bucket": True,
        "fragment_interval": 0.3,
        "repetition_penalty": 1.35,
        "sample_steps": 16,
        "seed": -1,
        "if_sr": False,
        "media_type": "wav"
    }

    async with httpx.AsyncClient(timeout=180) as client:
        # 1. 先请求 infer_single
        r = await client.post(TTS_INFER_URL, json=payload)
        r.raise_for_status()
        data = r.json()

        if data.get("msg") != "合成成功" or not data.get("audio_url"):
            raise RuntimeError(f"TTS 合成失败: {data}")

        # 2. 拿到 audio_url，再下载真正音频
        audio_url = data["audio_url"].replace("0.0.0.0", TTS_BASE_URL.replace("http://", "").replace(":8000", ""))
        if not audio_url.startswith("http"):
            audio_url = f"{TTS_BASE_URL}{data['audio_url']}"

        audio_resp = await client.get(audio_url)
        audio_resp.raise_for_status()

        out_path = os.path.abspath(os.path.join(OUT_DIR, f"{uuid.uuid4().hex}.wav"))
        with open(out_path, "wb") as f:
            f.write(audio_resp.content)

        return out_path


async def get_voices():
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{TTS_BASE_URL}/models/v4")
        r.raise_for_status()
        data = r.json()
        if "models" in data:
            return list(data["models"].keys())
        return []