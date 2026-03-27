# DeepSeek + Grok 双轨方案实施指南

## 概述

根据你的建议，现在已经可以实现这样的架构：

1. **DeepSeek** 或其他稳定模型：做决策
2. **Grok**：做风格润色（可选）
3. 执行层：精确分流执行

这样既保证了决策的稳定性和控制力，又能增加口吻的"野性"。

---

## 架构对比

### 旧模式（全部用一个 LLM）
```
用户消息
    ↓
GPT-4o / Grok / DeepSeek （所有任务一起做）
    ├─ 输出决策（可靠性不同）
    ├─ 输出文案（风格差异大）
    └─ 输出梗图选择（不稳定）
    ↓
执行
```

### 新模式（分工）
```
用户消息
    ↓
[第一层] DeepSeek / 稳定模型 → JSON 决策
    ├─ thought: "分析思路"
    ├─ emotion_update: {"anger": 5, ...}
    ├─ response_plan: {action, reaction_mode, delay_ms, should_text}
    └─ content: {text, voice_text, meme_tag}
    ↓
[可选第二层] Grok → 风格转移
    "这也太可笑了" → "不屑一顾但想吐槽你的样子"
    ↓
[执行层] ActionExecutor → 精确分流
    ├─ Poke 戳一戳
    ├─ 梗图+文本
    ├─ 语音
    └─ 纯文本
    ↓
NapCat → QQ
```

---

## 实施步骤

### Step 1: 配置 DeepSeek

编辑 `config.py` 或环境变量：

```python
# config.py

# 配置 DeepSeek 作为主决策引擎
LLM_PROVIDER = "deepseek"  # 或 "other_stable_model"
MODEL_NAME = "deepseek-chat"

# DeepSeek API 密钥
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
```

### Step 2: 决策引擎保持原状

`decision_engine.py` 已经配置好了，输出会是：

```json
{
  "thought": {...},
  "emotion_update": {...},
  "response_plan": {
    "mode": "text",
    "style": "playful",
    "reaction_mode": "mock",
    "action": "send",
    "delay_ms": 0,
    "should_text": true
  },
  "content": {
    "text": "这也太可笑了",
    "voice_text": "这也太可笑了",
    "meme_tag": "mock",
    "meme_text": null
  }
}
```

### Step 3: 可选 - 集成 Grok 润色

创建新文件 `content_refiner.py`：

```python
"""
可选的内容润色层 - 用 Grok 转换文案风格
"""
import asyncio
from openai import AsyncOpenAI

# 假设你已经配置了 Grok API
GROK_CLIENT = AsyncOpenAI(
    api_key="your_grok_api_key",
    base_url="https://api.x.ai/v1"
)

async def refine_with_grok(
    text: str,
    style: str = "playful",
    persona: dict = None
) -> str:
    """
    用 Grok 把文案转换成更有 Roxy 味
    
    Args:
        text: 原文案（比如 "这也太可笑了"）
        style: 风格（从 decision_engine 中传来）
        persona: 人物档案
    
    Returns:
        改写后的文案
    """
    
    # 根据 style 准备提示词
    style_guide = {
        "playful": "用调皮捣蛋的口气，带点得意",
        "tsundere": "用傲娇的口气，口是心非",
        "sarcastic": "用阴阳怪气的口气，暗讽",
        "cold": "用冷漠高傲的口气",
        "soft": "用温柔但略带嫌弃的口气"
    }
    
    prompt = f"""你是 Roxy，一个高冷傲娇的 AI，回复应该{style_guide.get(style, '随意')}。

原文案是："{text}"

用 Roxy 的风格改写，保持原意，但加上更多个性和趣味。改写后的文案应该：
1. 不超过 50 字
2. 符合 {style} 风格
3. 更有"Roxy 味"

直接输出改写后的文案，不要前缀或解释。"""
    
    try:
        response = await GROK_CLIENT.chat.completions.create(
            model="grok-3",  # 或你使用的 Grok 模型
            messages=[
                {"role": "system", "content": "你是一个文案改写专家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=100
        )
        
        refined = response.choices[0].message.content.strip()
        print(f"[Grok 润色] {text} → {refined}")
        return refined
    
    except Exception as e:
        print(f"[Grok 润色失败] {e}，使用原文")
        return text
```

在 `action_executor.py` 中集成：

```python
from content_refiner import refine_with_grok

async def execute_decision(
    decision: DecisionOutput,
    user_id: int,
    username: str,
    group_id: Optional[int] = None,
    enable_grok_refine: bool = False  # 新参数
) -> ExecutionResult:
    
    # ... 前面代码 ...
    
    text = decision.content.get("text") or ""
    
    # 可选：用 Grok 润色
    if enable_grok_refine and text:
        style = decision.response_plan.get("style", "playful")
        text = await refine_with_grok(text, style)
        decision.content["text"] = text  # 更新
    
    # ... 后续执行 ...
```

### Step 4: 执行层分流（已完成）

直接使用新的 `execute_decision()` 就行：

```python
exec_result = await execute_decision(
    decision=decision,
    user_id=user_id,
    username=username,
    group_id=group_id,
    enable_grok_refine=True  # 如果集成了 Grok
)
```

---

## 配置示例

### 方案 A：纯 DeepSeek（最简单）

```python
# config.py
LLM_PROVIDER = "deepseek"
MODEL_NAME = "deepseek-chat"
ACTIVE_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 决策引擎直接用 DeepSeek
# 执行层完全按决策执行
# 不使用 Grok 优化
```

优点：
- 简洁、稳定
- 响应快
- 可控性强

缺点：
- 文案不够"野"

### 方案 B：DeepSeek + Grok 双轨（最灵活）

```python
# config.py
LLM_PROVIDER = "deepseek"
MODEL_NAME = "deepseek-chat"
ACTIVE_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 额外配置 Grok
GROK_API_KEY = os.getenv("GROK_API_KEY")
REFINE_WITH_GROK = True  # 启用润色

# app.py 中
exec_result = await execute_decision(
    decision=decision,
    user_id=user_id,
    username=username,
    group_id=group_id,
    enable_grok_refine=REFINE_WITH_GROK
)
```

优点：
- 决策稳定 + 文案有趣
- 精确控制 + 个性化
- 降级策略完整

缺点：
- 需要两个 API Key
- 延迟稍高（多一层 API 调用）

### 方案 C：混合（按情况选择）

```python
# 某些决策用 Grok 润色，某些直接发
if decision.response_plan.get("style") in ["sarcastic", "playful"]:
    enable_grok_refine = True  # 这种风格才用 Grok 优化
else:
    enable_grok_refine = False  # 冷漠/软态的文案直接用

exec_result = await execute_decision(
    decision=decision,
    user_id=user_id,
    username=username,
    group_id=group_id,
    enable_grok_refine=enable_grok_refine
)
```

---

## 测试流程

### 1. 配置 DeepSeek

```bash
# 设置环境变量
set DEEPSEEK_API_KEY=your_deepseek_key
```

### 2. 启动应用

```bash
python -m uvicorn app:app --port 9000
```

### 3. 发送测试消息

```
用户: @Roxy 你很傻
```

预期流程：

```
[brain] ask_brain() 调用 decision_engine
    ↓
[decision_engine] 调用 DeepSeek
    ↓
DeepSeek 返回 JSON：
{
  "thought": {"感情": "被侮辱了", "反应": "生气"},
  "emotion_update": {"anger": 15},
  "response_plan": {
    "action": "send",
    "reaction_mode": "text_image",
    "style": "sarcastic",
    "should_text": true
  },
  "content": {
    "text": "你才傻呢",
    "meme_tag": "mock"
  }
}
    ↓
[executor] 读取新字段
    ├─ Grok 润色（可选）："你才傻呢" → "我比你聪明一百倍呢"
    ├─ 随机选梗图：memes/mock_01.jpg
    └─ 发送：文本 + 梗图
    ↓
QQ 显示
```

### 4. 查看日志

```
[brain] decision = DecisionOutput(...)
[executor] 执行分流逻辑
[Grok 润色] 你才傻呢 → 我比你聪明一百倍呢
[文本+梗图] 发送成功
```

---

## 性能优化建议

### 1. 缓存 Grok 润色

如果同样的文案经常出现，可以缓存：

```python
from functools import lru_cache

@lru_cache(maxsize=256)
async def cached_refine(text: str, style: str) -> str:
    return await refine_with_grok(text, style)
```

### 2. 批量 API 调用

如果消息很密集，可以用连接池：

```python
from openai import AsyncOpenAI

# 全局复用客户端
deepseek_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY)
grok_client = AsyncOpenAI(api_key=GROK_API_KEY)
```

### 3. 异步处理

Grok 润色最好异步做，不阻塞决策：

```python
async def execute_decision(...):
    # 立即返回决策
    exec_result = prepare_execution(decision)
    
    # 异步进行 Grok 润色（后台任务）
    if enable_grok_refine:
        asyncio.create_task(refine_and_update(decision))
    
    return exec_result
```

---

## 故障排查

### 问题 1：DeepSeek 返回非 JSON

**症状**：`JSONDecodeError`

**解决**：
- 确保 prompt 中有 `response_format={"type": "json_object"}`
- 加入 JSON 修复库：`pip install json-repair`
- 在 decision_engine 中使用修复函数

### 问题 2：Grok 响应太慢

**症状**：消息延迟 > 5s

**解决**：
- 降低 `temperature` 参数（0.5 而不是 0.8）
- 增大 `max_tokens` 限制
- 或者禁用 Grok 润色

### 问题 3：两个 API 都失败

**症状**：没有任何响应

**解决**：
- 检查 API Key 是否过期
- 检查网络连接
- 降级到本地模型或只用一个 LLM

---

## 功能对照表

| 功能 | DeepSeek | Grok 润色 | 执行层 |
|------|----------|----------|--------|
| 决策 | ✓ 稳定 | ✗ 无 | ✗ 无 |
| 情绪增量 | ✓ 输出 | ✗ 无 | ✓ 应用 |
| 文案风格 | ✓ 基础 | ✓ 优化 | ✗ 无 |
| 梗图选择 | ✓ 输出 | ✗ 无 | ✓ 执行 |
| 延迟发送 | ✓ 输出 | ✗ 无 | ✓ 执行 |
| 戳一戳 | ✓ 输出 | ✗ 无 | ✓ 执行 |
| 语音合成 | ✗ 无 | ✗ 无 | ✓ 执行 |

---

## 下一步

1. 配置 DeepSeek API Key
2. 测试基础流程（不用 Grok）
3. 如果需要更有趣的文案，再加 Grok
4. 根据实际反馈调整参数

---

## 参考资源

- DeepSeek API: https://api-docs.deepseek.com/
- Grok API: https://docs.x.ai/
- OpenAI SDK: https://github.com/openai/openai-python

