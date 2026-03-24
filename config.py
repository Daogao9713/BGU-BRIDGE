import os
from dotenv import load_dotenv

load_dotenv()

# ============ LLM 配置 ============
# OpenAI 配置（备用）
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY", "") or "").strip()
OPENAI_BASE_URL = (os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1") or "").strip()
OPENAI_MODEL = (os.getenv("OPENAI_MODEL", "gpt-4o-mini") or "").strip()

# Grok (xAI) 配置 - 主服务
GROK_API_KEY = (os.getenv("GROK_API_KEY", "") or "").strip()
GROK_BASE_URL = (os.getenv("GROK_BASE_URL", "https://api.x.ai/v1") or "").strip()
MODEL_NAME = (os.getenv("MODEL_NAME", "grok-3-mini") or "").strip()  # grok-beta 或 grok-2-latest

NAPCAT_API = (os.getenv("NAPCAT_API", "http://127.0.0.1:6090") or "").strip().rstrip("/")
ONEBOT_TOKEN = (os.getenv("ONEBOT_TOKEN", "") or "").strip()

BOT_QQ = int(os.getenv("BOT_QQ", "0"))
PORT = int(os.getenv("PORT", "9000"))

TTS_GPU_IP = (os.getenv("TTS_GPU_IP", "127.0.0.1") or "").strip()
TTS_BASE_URL = f"http://{TTS_GPU_IP}:8000"
TTS_INFER_URL = f"{TTS_BASE_URL}/infer_single"
TTS_SPEAKER = (os.getenv("TTS_SPEAKER", "绝区零-中文-铃") or "").strip()

GROUP_WHITELIST = {
    int(x.strip()) for x in os.getenv("GROUP_WHITELIST", "").split(",") if x.strip()
}

USER_WHITELIST = {
    int(x.strip()) for x in os.getenv("USER_WHITELIST", "").split(",") if x.strip()
}

TRIGGER_PREFIX = tuple(
    x.strip() for x in os.getenv("TRIGGER_PREFIX", "Roxy,roxy").split(",") if x.strip()
)

# ============ 定时事件配置 (生物钟) ============
# Roxy 的主阵地群号（用于定时冷场检测和新闻评论）
TARGET_GROUP_ID = (os.getenv("TARGET_GROUP_ID", "") or "").strip()

# ============ Roxy v2 引擎配置 ============

# 情绪基线配置
EMOTION_BASELINE = {
    "anger": 20.0,       # 愤怒
    "affection": 55.0,   # 亲近感
    "playfulness": 60.0, # 玩心
    "fatigue": 15.0,     # 疲惫
    "pride": 70.0,       # 傲娇
    "stress": 10.0       # 群聊压力
}

# 人格强度控制器
PERSONA_CONFIG = {
    "sharpness": 0.65,          # 嘴上锋利程度 [0-1]
    "voice_preference": 0.7,    # 倾向发语音 [0-1]
    "meme_preference": 0.5,     # 倾向发梗图 [0-1]
    "tsundere_level": 0.8,      # 傲娇程度 [0-1]
    "mercy": 0.4                # 收手概率 [0-1]
}

# 冷却配置
GROUP_COOLDOWN_SEC = 10
USER_COOLDOWN_SEC = 6

# 梗图目录
MEME_DIR = "./memes"