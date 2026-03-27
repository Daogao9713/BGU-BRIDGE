"""
可选的内容润色层 - 用 Grok 转换文案风格
支持将 DeepSeek 的决策文案进一步润色成更有"Roxy 味"的表达
"""
import asyncio
from typing import Optional
from openai import AsyncOpenAI
import os

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


async def refine_with_grok(
    text: str,
    style: str = "playful",
    persona_config: Optional[dict] = None
) -> str:
    """
    用 Grok 把文案转换成更有 Roxy 味
    
    Args:
        text: 原文案（比如 "这也太可笑了"）
        style: 风格（从 decision_engine 中传来）
        persona_config: 人物档案配置字典
    
    Returns:
        改写后的文案，如果失败则返回原文
    """
    
    if not text or not GROK_CLIENT:
        return text
    
    # 根据 style 准备提示词
    style_guide = {
        "playful": "用调皮捣蛋的口气，带点得意",
        "tsundere": "用傲娇的口气，口是心非，嘴硬",
        "sarcastic": "用阴阳怪气的口气，带着讽刺",
        "cold": "用冷漠高傲的口气",
        "soft": "用温柔但略带嫌弃的口气"
    }
    
    persona_hint = ""
    if persona_config:
        sharpness = persona_config.get("sharpness", 0.65)
        tsundere = persona_config.get("tsundere_level", 0.8)
        if sharpness > 0.7:
            persona_hint = "你是个锋利的、毒舌的 AI。"
        if tsundere > 0.7:
            persona_hint += "你有点傲娇，但其实很在乎用户。"
    
    prompt = f"""你是 Roxy，一个高冷傲娇的 AI，{persona_hint}

回复应该{style_guide.get(style, '随意')}。

原文案是："{text}"

用 Roxy 的风格改写，保持原意，但加上更多个性和趣味。改写后的文案应该：
1. 不超过 50 字
2. 符合 {style} 风格
3. 更有"Roxy 味"，带点感情

直接输出改写后的文案，不要前缀或解释。"""
    
    try:
        response = await GROK_CLIENT.chat.completions.create(
            model="grok-3",  # 或你使用的 Grok 模型
            messages=[
                {"role": "system", "content": "你是一个文案改写专家。精准、有趣、富有表现力。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=100,
            timeout=5  # 超时 5 秒
        )
        
        refined = response.choices[0].message.content.strip()
        print(f"[Grok 润色] '{text}' → '{refined}'")
        return refined
    
    except asyncio.TimeoutError:
        print(f"[Grok 润色超时] 使用原文: '{text}'")
        return text
    
    except Exception as e:
        print(f"[Grok 润色失败] {e}，使用原文: '{text}'")
        return text


async def refine_content_with_grok(
    decision_content: dict,
    response_plan: dict,
    persona_config: Optional[dict] = None
) -> dict:
    """
    对整个 content 对象进行润色
    
    Args:
        decision_content: decision.content 字典
        response_plan: decision.response_plan 字典
        persona_config: 人物档案
    
    Returns:
        润色后的 content 字典
    """
    
    if not decision_content:
        return decision_content
    
    style = response_plan.get("style", "playful")
    
    # 只润色 text 和 voice_text
    text = decision_content.get("text", "")
    voice_text = decision_content.get("voice_text", "")
    
    enriched_content = dict(decision_content)  # 浅拷贝
    
    # 润色主文案
    if text:
        enriched_content["text"] = await refine_with_grok(text, style, persona_config)
    
    # 润色语音文案（如果和主文案不同）
    if voice_text and voice_text != text:
        enriched_content["voice_text"] = await refine_with_grok(voice_text, style, persona_config)
    elif voice_text and text:
        # 如果 voice_text 为空但 text 有值，同步更新
        enriched_content["voice_text"] = enriched_content["text"]
    
    return enriched_content
