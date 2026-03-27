# 执行层快速参考卡

## 新字段映射表

### response_plan
| 字段 | 类型 | 含义 | 例值 |
|------|------|------|------|
| `action` | str | 动作类型 | `"send"` / `"poke"` / `"delay_send"` / `"ignore"` |
| `reaction_mode` | str | 反应模式 | `"voice"` / `"text"` / `"text_image"` / `"silence"` |
| `delay_ms` | int | 延迟毫秒数 | `500` |
| `should_text` | bool | 是否发送文本 | `true` / `false` |

### content
| 字段 | 类型 | 含义 | 例值 |
|------|------|------|------|
| `text` | str | 主要文本 | `"这太可笑了"` |
| `voice_text` | str | 语音文本 | `"这太可笑了"` |
| `meme_tag` | str | 梗图标签 | `"mock"` / `"sweat"` / `"stare"` |
| `meme_text` | str | 梗图文字 | `"🤔"` |

---

## 执行决策的流程图

```
╔════════════════════════════════════════════╗
║     execute_decision(decision)              ║
╚════════════════════════════════════════════╝
                      ↓
          读取 response_plan 和 content
                      ↓
        ┌────────────────────────────────┐
        │ 检查 delay_ms                  │
        │ 如果 > 0: await sleep()        │
        └────────────────────────────────┘
                      ↓
    ┌──────────────────────────────────────┐
    │ 根据 action 分流：                   │
    └──────────────────────────────────────┘
            ↙         ↓          ↘
       "poke"    "send"+梗图   其他
           ↓           ↓         ↓
       发戳一戳   发文本+梗图  检查模式
           ↓           ↓         ↓
         成功      (可选)    voice/text
                   检查TTS
                      ↓
                   在线→语音
                  离线→文本
```

---

## 梗图映射表

```python
MEME_MAP = {
    "sweat": ["memes/sweat_01.jpg", "memes/sweat_02.jpg"],  # 冷汗
    "stare": ["memes/stare_01.jpg"],                         # 瞪眼
    "mock": ["memes/mock_01.jpg", "memes/mock_02.jpg"],     # 嘲笑
    "silent": ["memes/silent_01.jpg"],                       # 沉默
    "disgust": ["memes/disgust_01.jpg"],                     # 厌恶
}

# 使用：
meme_file = pick_meme_file("mock")  # 随机选择 memes/mock_*.jpg
```

---

## 新 API - Poke（戳一戳）

### 群聊戳一戳
```python
await send_group_poke(group_id=123456, user_id=789012)
# 在群 123456 中戳用户 789012 一下
```

### 私聊戳一戳
```python
await send_private_poke(user_id=789012)
# 给用户 789012 戳一下
```

---

## 决策例子

### 例 1：发送梗图+文本

```python
decision.response_plan = {
    "action": "send",
    "reaction_mode": "text_image",
    "delay_ms": 0,
    "should_text": True
}

decision.content = {
    "text": "😂 这也太可笑了！",
    "voice_text": "这也太可笑了",
    "meme_tag": "mock",
    "meme_text": None
}

# 执行流：
# 1. 检查 meme_tag: "mock" ✓ 有效
# 2. 从 MEME_MAP 中随机选 memes/mock_*.jpg
# 3. should_text = True，先发 "😂 这也太可笑了！"
# 4. 再发梗图 (mock_01.jpg 或 mock_02.jpg)
```

### 例 2：戳一戳 + 纯文本

```python
decision.response_plan = {
    "action": "poke",
    "reaction_mode": "none",
    "delay_ms": 500,
    "should_text": False
}

decision.content = {
    "text": "你！",
    "voice_text": None,
    "meme_tag": None,
    "meme_text": None
}

# 执行流：
# 1. delay_ms = 500，等待 500ms
# 2. action = "poke"，发戳一戳
# 3. 不发文本（should_text=False）
```

### 例 3：冷静期回复（纯文本）

```python
decision.response_plan = {
    "action": "send",
    "reaction_mode": "text",
    "delay_ms": 0,
    "should_text": True
}

decision.content = {
    "text": "……",
    "voice_text": "……",
    "meme_tag": None,
    "meme_text": None
}

# 执行流：
# 1. meme_tag = None，不发梗图
# 2. reaction_mode = "text"，检查 TTS
# 3. TTS 不在线或无必要，降级到纯文本
# 4. 发送 "……"
```

### 例 4：语音回复

```python
decision.response_plan = {
    "action": "send",
    "reaction_mode": "voice",
    "delay_ms": 0,
    "should_text": False
}

decision.content = {
    "text": None,
    "voice_text": "你这是什么意思呢？",
    "meme_tag": None,
    "meme_text": None
}

# 执行流：
# 1. reaction_mode = "voice"
# 2. 检查 TTS 服务 (TTS_GPU_IP:8000)
# 3. TTS 在线 → 合成语音 "你这是什么意思呢？"
# 4. 发送语音文件
# 5. 如果 TTS 离线 → 降级纯文本（但 text 为空，所以什么也不发）
```

### 例 5：无视（既不发文本也不发梗图）

```python
decision.response_plan = {
    "action": "ignore",
    "reaction_mode": "none",
    "delay_ms": 0,
    "should_text": False
}

decision.content = {}

# 执行流：
# 1. action = "ignore"
# 2. 不做任何事
# 3. 返回 ExecutionResult(success=True, action_type="ignore")
```

---

## RLHF 尾巴清理

自动删除的"虚伪"尾巴包括：

- "如果你愿意，我可以继续帮你。"
- "如果你愿意，我可以继续帮助你。"
- "希望这对你有帮助。"
- "希望有帮助。"
- "如果你需要，我可以继续。"
- "请随时告诉我。"
- "请随时告诉我你需要什么。"
- "有其他问题吗？"
- "还有其他问题吗？"
- "希望能帮上忙。"
- "感谢理解。"
- "如果还有其他需要，请随时告诉我。"

---

## 历史记录裁剪

在 `brain.py` 中：

```python
user_history = get_message_history(user_id)  # 可能很长，比如 50+ 条
if user_history:
    user_history = user_history[-10:]  # 只保留最后 10 条
# 这样即使用户聊天很久，上下文窗口也不会爆炸
```

---

## 调试建议

### 打印决策对象
```python
print(f"decision.response_plan = {decision.response_plan}")
print(f"decision.content = {decision.content}")
```

### 打印执行结果
```python
exec_result = await execute_decision(decision, user_id, username, group_id)
print(f"success={exec_result.success}")
print(f"action_type={exec_result.action_type}")
print(f"error={exec_result.error}")
print(f"fallback_chain={exec_result.fallback_chain}")
```

### 验证梗图映射
```python
from action_executor import pick_meme_file
path = pick_meme_file("mock")
print(f"Selected meme: {path}")
```

---

## 完整的执行栈

```
app.py handle_group_message()
    ↓
    ask_brain()  ← 调用决策引擎
        ↓
        decision_engine.make_decision()
            ↓
            LLM (DeepSeek / 任一稳定模型)
                ↓
        返回 DecisionOutput
    ↓
    execute_decision()  ← 执行层（此次改造）
        ↓
        ActionExecutor.execute_decision()
            ├─ _execute_poke()
            ├─ _execute_text_image_new()
            ├─ _execute_voice()
            └─ _execute_text()
        ↓
        onebot_client  ← 发送驱动
            ├─ send_group_poke()
            ├─ send_group_text()
            ├─ send_group_image()
            ├─ send_group_record()
            └─ ...
        ↓
    返回 ExecutionResult
        ↓
    log_action()  ← 日志记录
```

---

## 关键改进 vs 旧版本

| 功能 | 旧版本 | 新版本 |
|------|--------|--------|
| 梗图控制 | 固定映射 | MEME_MAP + pick_meme_file |
| 文本选择 | 总是发 | should_text 控制 |
| 延迟发送 | 无 | delay_ms 毫秒级精确控制 |
| 戳一戳 | 无 | 支持作为单独的 action |
| RLHF 清理 | 无 | 自动清理尾巴 |
| 降级策略 | 硬编码链 | 智能分流 + TTS 探针 |
| 历史大小 | 无限制 | 自动裁剪 ≤10 条 |

