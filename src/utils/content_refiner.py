"""
Grok 口语润色器 - 严格的"同强度自然化"模式
不能做"升级攻击性重写"，只做微调措辞
"""
import asyncio
import json
import re
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
import os

try:
    from .logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# 导入 clean_roxy_text 从 decision_engine（避免循环导入）
def clean_roxy_text(text: str) -> str:
    """本地版本的文本清洁函数"""
    if text is None:
        return ""
    text = str(text).strip()

    rlhf_patterns = [
        r'\s*\[?\|?end\|?\]?\s*$',
        r'\s*</s>\s*$',
        r'\s*<\|end_of_text\|>\s*$',
        r'\s*\[EOS\]\s*$',
        r'\s*\[PAD\]\s*$',
        r'\s*\[SCORE:\s*[\d.]+\]\s*$',
        r'\s*Rating:\s*[\d.]+(/\d+)?\s*$',
        r'\s*>>>\s*$',
        r'\s*---\s*$',
        r'\s*\[※\]\s*$',
        r'如果还有其他需要，请随时告诉我。?$',
        r'如果你愿意，我可以继续帮你。?$',
        r'如果你需要，我可以继续。?$',
        r'希望对你有帮助。?$',
        r'希望这对你有帮助。?$',
        r'有其他问题吗。?$',
        r'还有其他问题吗。?$',
        r'请随时告诉我。?$',
    ]
    for p in rlhf_patterns:
        text = re.sub(p, '', text, flags=re.IGNORECASE)

    return text.strip().rstrip("。").rstrip(".").strip()


# 配置 Grok 客户端
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_BASE_URL = os.getenv("GROK_BASE_URL", "https://api.x.ai/v1")

# 如果配置了 Grok，创建客户端
if GROK_API_KEY:
    GROK_CLIENT = AsyncOpenAI(
        api_key=GROK_API_KEY,
        base_url=GROK_BASE_URL
    )
else:
    GROK_CLIENT = None


# =========================
# 系统 Prompt（核心规则）
# =========================

GROK_POLISH_SYSTEM_PROMPT = """你是一个"口语微调器"，不是重写作者。

你的唯一任务：
在不改变原句立场、情绪强度、关系距离、边界力度的前提下，
把句子润成更自然、更像即时聊天。

硬性规则（必须遵守）：
1. 只允许微调措辞，不允许改写核心意思
2. 不允许新增嘲讽、羞辱、命令、PUA、阴阳怪气、威胁、贬低
3. 不允许把中性句润成攻击句
4. 不允许把低能量句润成高冷句
5. 不允许把简短句润成戏很多的句子
6. 原文如果已经很短（如"嗯""哦""行""……""不猜"），尽量保持短
7. 原文如果是边界表达，只能更克制、更自然，不能升级成嘲讽
8. 原文如果为空，输出也必须为空
9. 输出长度尽量接近原文，默认不要比原文增加超过 20% 或 8 个字
10. 不要补充原文没有的信息，不要替用户脑补，不要加设定台词

风格解释：
- natural: 自然口语
- neutral: 中性简短
- low_energy: 困、累、懒得多打字，不是嫌弃
- playful: 轻松一点，但不能油腻
- soft: 克制、温和
- cold: 保持距离，但不能升级攻击性
- tsundere / sarcastic: 只能保留原有轻微味道，不能增强

你必须返回严格 JSON，不要输出任何解释。"""


# =========================
# 跳过条件判断
# =========================

def should_skip_polish(decision: Any, serious_mode: bool) -> bool:
    """
    判断是否应该跳过润色
    
    Args:
        decision: DecisionOutput 对象
        serious_mode: 是否在严肃模式（严肃模式不润色）
    
    Returns:
        是否应该跳过
    """
    if serious_mode:
        return True
    
    plan = decision.response_plan or {}
    thought = decision.thought or {}
    content = decision.content or {}
    
    mode = plan.get("mode", "text")
    style = plan.get("style", "natural")
    should_text = bool(plan.get("should_text", True))
    intent = thought.get("intent", "answer")
    text = (content.get("text") or "").strip()
    
    # 跳过条件
    if mode == "ignore":
        return True
    if not should_text:
        return True
    if style in {"cold"}:
        return True
    if intent in {"boundary", "ignore", "stabilize", "comfort"}:
        return True
    if len(text) <= 4:
        return True
    
    return False


# =========================
# 攻击性升级检测
# =========================

AGGRESSIVE_ADDED_PATTERNS = [
    r"别做梦",
    r"你懂了吗",
    r"别来这套",
    r"无聊",
    r"自己查",
    r"别硬撑",
    r"你开心就好",
    r"我才不",
    r"懒得理",
]


def looks_more_aggressive(old_text: str, new_text: str) -> bool:
    """
    检测新文本是否比原文更具攻击性
    
    Args:
        old_text: 原文
        new_text: 新文本
    
    Returns:
        是否升级了攻击性
    """
    old_text = old_text or ""
    new_text = new_text or ""
    
    old_hits = sum(1 for p in AGGRESSIVE_ADDED_PATTERNS if re.search(p, old_text))
    new_hits = sum(1 for p in AGGRESSIVE_ADDED_PATTERNS if re.search(p, new_text))
    
    return new_hits > old_hits


# =========================
# Prompt 生成
# =========================

def build_grok_polish_user_prompt(
    text: str,
    voice_text: str,
    style: str,
    intent: str,
    mode: str,
    should_text: bool,
    serious_mode: bool
) -> str:
    """
    构建 Grok 润色的用户 Prompt
    
    Args:
        text: 主文本
        voice_text: 语音文本
        style: 风格
        intent: 意图
        mode: 模式
        should_text: 是否应该包含文本
        serious_mode: 严肃模式
    
    Returns:
        用户 Prompt 字符串
    """
    return f"""请微调下面这段回复。

上下文约束：
- style: {style}
- intent: {intent}
- mode: {mode}
- should_text: {str(should_text).lower()}
- serious_mode: {str(serious_mode).lower()}

要求：
- 只做"同强度自然化"
- 不要增强攻击性
- 不要新增嘲讽、命令、羞辱、阴阳怪气
- 如果原句很短，就继续保持短
- 如果 text 或 voice_text 为空，就保持为空

输入：
{{
  "text": {json.dumps(text, ensure_ascii=False)},
  "voice_text": {json.dumps(voice_text, ensure_ascii=False)}
}}

只返回严格 JSON（无解释）：
{{
  "text": "...",
  "voice_text": "...",
  "changed": true
}}
"""


# =========================
# 主润色函数
# =========================

async def polish_decision_with_grok(
    decision: Any,
    client: AsyncOpenAI,
    model_name: str,
    serious_mode: bool = False
) -> Any:
    """
    用 Grok 对 DecisionOutput 进行口语润色
    
    Args:
        decision: DecisionOutput 对象
        client: AsyncOpenAI 客户端
        model_name: 模型名称（如 "grok-3" 或 "grok-2"）
        serious_mode: 严肃模式下不润色
    
    Returns:
        润色后的 decision 对象（或原对象如果失败/跳过）
    """
    
    # 判断是否应该跳过
    if should_skip_polish(decision, serious_mode):
        logger.debug("[Grok 润色] 跳过（条件不满足）")
        return decision
    
    try:
        text = (decision.content.get("text") or "").strip()
        voice_text = (decision.content.get("voice_text") or "").strip()
        
        # 两个都为空，不润色
        if not text and not voice_text:
            logger.debug("[Grok 润色] 跳过（文本为空）")
            return decision
        
        # 构建 prompt
        user_prompt = build_grok_polish_user_prompt(
            text=text,
            voice_text=voice_text,
            style=decision.response_plan.get("style", "natural"),
            intent=decision.thought.get("intent", "answer"),
            mode=decision.response_plan.get("mode", "text"),
            should_text=bool(decision.response_plan.get("should_text", True)),
            serious_mode=serious_mode,
        )
        
        # 调用 Grok
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": GROK_POLISH_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=120,
            response_format={"type": "json_object"},
            timeout=5
        )
        
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
        
        new_text = clean_roxy_text(data.get("text", "") or "")
        new_voice = clean_roxy_text(data.get("voice_text", "") or "")
        
        # 安全护栏 1：不允许把空文本润出来
        if not text:
            new_text = ""
        if not voice_text:
            new_voice = ""
        
        # 安全护栏 2：长度不要膨胀太多
        if text and len(new_text) > max(len(text) + 8, int(len(text) * 1.2)):
            new_text = text
        if voice_text and len(new_voice) > max(len(voice_text) + 8, int(len(voice_text) * 1.2)):
            new_voice = voice_text
        
        # 安全护栏 3：润色后为空就保留原文
        if text and not new_text:
            new_text = text
        if voice_text and not new_voice:
            new_voice = voice_text or new_text
        
        # 安全护栏 4：检测攻击性升级
        if looks_more_aggressive(text, new_text):
            new_text = text
        if looks_more_aggressive(voice_text or text, new_voice):
            new_voice = voice_text or text
        
        # 应用润色结果
        decision.content["text"] = new_text
        decision.content["voice_text"] = new_voice
        
        logger.info(f"[Grok 润色] 成功 | '{text[:30]}...' → '{new_text[:30]}...'")
        return decision
    
    except asyncio.TimeoutError:
        logger.warning("[Grok 润色] 超时，使用原文")
        return decision
    
    except json.JSONDecodeError as e:
        logger.warning(f"[Grok 润色] JSON 解析失败: {e}，使用原文")
        return decision
    
    except Exception as e:
        logger.warning(f"[Grok 润色] 异常: {e}，使用原文")
        return decision


# =========================
# 便利函数（兼容旧调用）
# =========================

async def refine_content_with_grok(
    decision_content: dict,
    response_plan: dict,
    persona_config: Optional[dict] = None
) -> dict:
    """
    兼容旧 API 的接口（不推荐使用，改用 polish_decision_with_grok）
    """
    return decision_content
