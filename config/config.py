import os
from pathlib import Path
from dotenv import load_dotenv

# 加载根目录的 .env 文件
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# ============ LLM 厂商配置 - 动态选择 ============
# 支持的厂商 provider: openai, deepseek, grok, gemini
# 默认使用 deepseek，可通过 LLM_PROVIDER 环境变量切换
LLM_PROVIDER = (os.getenv("LLM_PROVIDER", "deepseek").lower() or "deepseek").strip()

# ===== OpenAI (ChatGPT) 配置 =====
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY", "") or "").strip()
OPENAI_BASE_URL = (os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1") or "").strip()
OPENAI_MODEL_PREFIX = (os.getenv("OPENAI_MODEL", "gpt-4o-mini") or "").strip()

# ===== DeepSeek 配置 =====
DEEPSEEK_API_KEY = (os.getenv("DEEPSEEK_API_KEY", "") or "").strip()
DEEPSEEK_BASE_URL = (os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com") or "").strip()
DEEPSEEK_MODEL_PREFIX = (os.getenv("DEEPSEEK_MODEL", "deepseek-chat") or "").strip()

# ===== Grok (XAI) 配置 =====
GROK_API_KEY = (os.getenv("GROK_API_KEY", "") or "").strip()
GROK_BASE_URL = (os.getenv("GROK_BASE_URL", "https://api.x.ai/v1") or "").strip()
GROK_MODEL_PREFIX = (os.getenv("GROK_MODEL", "grok-4-1-fast-non-reasoning") or "").strip()

# ===== Gemini (Google) 配置 =====
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY", "") or "").strip()
GEMINI_BASE_URL = (os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/") or "").strip()
GEMINI_MODEL_PREFIX = (os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest") or "").strip()

# ============ 动态厂商选择 ============
_PROVIDER_CONFIG = {
    "openai": {
        "api_key": OPENAI_API_KEY,
        "base_url": OPENAI_BASE_URL,
        "model_prefix": OPENAI_MODEL_PREFIX,
        "name": "OpenAI (ChatGPT)"
    },
    "deepseek": {
        "api_key": DEEPSEEK_API_KEY,
        "base_url": DEEPSEEK_BASE_URL,
        "model_prefix": DEEPSEEK_MODEL_PREFIX,
        "name": "DeepSeek"
    },
    "grok": {
        "api_key": GROK_API_KEY,
        "base_url": GROK_BASE_URL,
        "model_prefix": GROK_MODEL_PREFIX,
        "name": "Grok (XAI)"
    },
    "gemini": {
        "api_key": GEMINI_API_KEY,
        "base_url": GEMINI_BASE_URL,
        "model_prefix": GEMINI_MODEL_PREFIX,
        "name": "Gemini (Google)"
    }
}

# 获取当前选择的厂商配置
if LLM_PROVIDER in _PROVIDER_CONFIG:
    _ACTIVE_CONFIG = _PROVIDER_CONFIG[LLM_PROVIDER]
else:
    # 默认 deepseek
    _ACTIVE_CONFIG = _PROVIDER_CONFIG["deepseek"]
    LLM_PROVIDER = "deepseek"

ACTIVE_PROVIDER_NAME = _ACTIVE_CONFIG["name"]
ACTIVE_API_KEY = _ACTIVE_CONFIG["api_key"]
ACTIVE_BASE_URL = _ACTIVE_CONFIG["base_url"]
MODEL_NAME = _ACTIVE_CONFIG["model_prefix"]

# 向后兼容（旧代码可能直接使用）
GROK_API_KEY = ACTIVE_API_KEY
GROK_BASE_URL = ACTIVE_BASE_URL

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
    "sharpness": 0.8,          # 嘴上锋利程度 [0-1]
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

# ============ 方案 B: DeepSeek + Grok 双轨配置 ============
# 是否启用 Grok 润色层（可选）
# 当启用时，执行层会用 Grok 对 DeepSeek 的文案进一步润色
# 使得回复更有"Roxy 味"但要求同时有 Grok API Key 配置
REFINE_WITH_GROK = os.getenv("REFINE_WITH_GROK", "false").lower() in ("true", "1", "yes")

# Grok 润色温度参数（0.0-2.0），更高=更创意
GROK_REFINE_TEMPERATURE = float(os.getenv("GROK_REFINE_TEMPERATURE", "0.7"))

# Grok 润色最大 token 数
GROK_REFINE_MAX_TOKENS = int(os.getenv("GROK_REFINE_MAX_TOKENS", "100"))

# Grok 请求超时时间（秒）
GROK_REFINE_TIMEOUT = int(os.getenv("GROK_REFINE_TIMEOUT", "5"))