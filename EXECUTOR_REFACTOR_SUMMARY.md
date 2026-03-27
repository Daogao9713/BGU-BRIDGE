# Roxy v2 执行层改造 - 实现总结

## 📝 改动概览

按照你的建议，重构了整个消息发送执行层，使其能够读取 decision_engine 中的新增字段，支持更精细的控制。

---

## ✅ 完成的改动

### 1️⃣ **action_executor.py** - 重构执行逻辑

#### 新的 `execute_decision()` 流程

从旧的"降级链"模式改为**新的分流模式**：

```python
action = response_plan.get("action")           # "send", "delay_send", "poke"
reaction_mode = response_plan.get("reaction_mode")  # "voice", "text", etc
delay_ms = response_plan.get("delay_ms", 0)
should_text = response_plan.get("should_text", True)

# 读取内容字段
meme_tag = content.get("meme_tag")
meme_text = content.get("meme_text")
text = content.get("text") or ""
voice_text = content.get("voice_text") or text
```

#### 新增方法

- **`_execute_poke(user_id, group_id)`** - 执行戳一戳动作
- **`_execute_text_image_new(text, meme_tag, meme_text, should_text, user_id, group_id)`** - 新的文本+梗图执行（支持 `should_text` 控制是否发文本）

#### 梗图映射表与选择函数

```python
MEME_MAP = {
    "sweat": ["memes/sweat_01.jpg", "memes/sweat_02.jpg"],
    "stare": ["memes/stare_01.jpg"],
    "mock": ["memes/mock_01.jpg", "memes/mock_02.jpg"],
    "silent": ["memes/silent_01.jpg"],
    "disgust": ["memes/disgust_01.jpg"],
}

def pick_meme_file(tag: str) -> Optional[str]:
    """随机选择一个梗图"""
    files = MEME_MAP.get(tag, [])
    return random.choice(files) if files else None
```

---

### 2️⃣ **onebot_client.py** - 新增 poke 接口

```python
async def send_group_poke(group_id: int, user_id: int):
    """发送群戳一戳"""
    # 调用 NapCat API: group_poke

async def send_private_poke(user_id: int):
    """发送私聊戳一戳"""
    # 调用 NapCat API: poke
```

---

### 3️⃣ **decision_engine.py** - 增强内容清理

#### 新方法：`_strip_rlhf_tail(text)`

清理常见的 RLHF 尾巴：
- "如果你愿意，我可以继续帮你。"
- "希望这对你有帮助。"
- "请随时告诉我。"
- 等等...

#### 在 `_sanitize_content()` 中应用

```python
# 清理 RLHF 尾巴
text = self._strip_rlhf_tail(text)
voice_text = self._strip_rlhf_tail(voice_text)
```

#### 改进梗图标签验证

```python
valid_meme_tags = {"sweat", "stare", "mock", "silent", "disgust"}
if meme_tag not in valid_meme_tags:
    meme_tag = None
```

---

### 4️⃣ **brain.py** - 历史上下文裁剪

在获取用户历史后进行裁剪，防止上下文爆炸：

```python
user_history = get_message_history(user_id)

# 新增：只保留最近 10 条消息
if user_history:
    user_history = user_history[-10:]
    print(f"[brain] 裁剪后的历史记录条数: {len(user_history)}")
```

---

## 🎯 新执行流程分解

在 `execute_decision()` 中：

```
1. 读取 response_plan 中的 action / reaction_mode / delay_ms / should_text
2. 读取 content 中的 text / voice_text / meme_tag / meme_text

3. 如果 delay_ms > 0:
   → await asyncio.sleep(delay_ms / 1000)

4. 识别 action:

   a) action == "poke":
      → send_group_poke(group_id, user_id) 或 send_private_poke(user_id)
      
   b) action == "send" && meme_tag:
      → 执行文本+梗图混合
      → 如果 should_text，先发文本
      → 然后发梗图
      
   c) reaction_mode == "voice":
      → 检查 TTS 是否在线
      → 如果在线，合成语音 + 发送
      → 如果离线，降级到纯文本
      
   d) 其他情况（纯文本）:
      → 直接发送 text 字段
      
   e) action == "ignore" / "delay":
      → 返回相应的结果（不发送任何消息）
```

---

## 💾 文件修改清单

| 文件 | 改动 | 说明 |
|------|------|------|
| `action_executor.py` | 重构 `execute_decision()` + 新增 2 个方法 + MEME_MAP | 核心执行层改造 |
| `onebot_client.py` | 新增 `send_group_poke()` 和 `send_private_poke()` | poke 接口 |
| `decision_engine.py` | 新增 `_strip_rlhf_tail()` + 调用它 + 梗图标签验证 | 内容清理增强 |
| `brain.py` | 新增历史记录裁剪逻辑 | 防止上下文爆炸 |

---

## 🔍 关键改进点

### ✓ 精细控制
- **should_text**: 决策层可以明确说"只发梗图，不发文本"
- **delay_ms**: 支持精确的毫秒级延迟
- **action**: 统一的动作枚举（send, delay_send, poke, ignore, delay）

### ✓ RLHF 清理
- 自动去掉模型生成的"虚伪"尾巴
- 文本和语音都会清理

### ✓ 历史管理
- 防止上下文窗口被老消息填满
- 每次调用 LLM 时仅使用最近 10 条消息

### ✓ Poke 支持
- 支持"戳一戳"作为动作
- 可以在"被激怒"时戳人一下

---

## 🚀 下一步：DeepSeek + Grok 双轨方案

你提到的架构现在可以实现了：

### DeepSeek 层（决策）
```
决策引擎 (decision_engine) 输出 JSON:
- thought
- emotion_update  
- response_plan (含 action, delay_ms, should_text)
- content (含 text, voice_text, meme_tag, voice_text)

↓
稳定、可控、可降级
```

### Grok 层（润色）
```
可选：将 content["text"] 再送给 Grok 做风格转移

例如：
- DeepSeek: "这也太可笑了"
- Grok: "我，傲娇AI，不屑一顾但又想吐槽你"

这样既保证决策稳定，又能增加口吻的"Roxy 味"
```

---

## 📐 架构图

```
OneBot Event
    ↓
[event_mapper] 快速分析 + apply_emotion_event
    ↓
[decision_engine] LLM 决策
    ├─ thought
    ├─ emotion_update
    ├─ response_plan (action, reaction_mode, delay_ms, should_text)
    └─ content (text, voice_text, meme_tag, meme_text)
    ↓
[action_executor] 执行分流 ← 此次改造的核心
    ├─ 延迟 (delay_ms)
    ├─ 戳一戳 (poke)
    ├─ 梗图+文本 (text_image)
    ├─ 语音 (voice)
    └─ 纯文本 (fallback)
    ↓
[onebot_client] 发送给 NapCat
    ↓
QQ
```

---

## ✨ 特色

1. **有状态** - 情绪累积、衰减、恢复
2. **有关系** - 同样的话来自不同人反应不同
3. **可控性** - 规则保底 + LLM 负责风格
4. **模块化** - 情绪/档案/决策/执行完全解耦
5. **精确** - 新的字段允许细粒度控制

---

## 🎓 快速验证

运行测试脚本查看新流程：

```bash
python test_new_executor.py
```

输出示例：
```
✓ 新字段读取成功：
  action: send
  reaction_mode: mock
  delay_ms: 0
  should_text: True
  meme_tag: mock
  meme_text: None

✓ 执行分流逻辑：
  → 执行：文本+梗图 (should_text=True)
    - 发送文本: 😂这也太可笑了！
    - 发送梗图: mock
```

---

## 📌 注意事项

1. **梗图文件夹**：确保 `./memes/` 目录存在并放入梗图
2. **OneBot 版本**：确保 NapCat 支持 `group_poke` 和 `poke` API
3. **TTS 探针**：语音模式自动探测 TTS 是否在线
4. **MEME_MAP 维护**：如果加新梗图，需要在 `action_executor.py` 中更新映射表

