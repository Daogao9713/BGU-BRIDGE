# Roxy v2 Grok 迁移总结

## 📝 改动概览

本次升级完成了两个重要功能改进：
1. **LLM 迁移**：从 OpenAI 切换到 Grok (xAI)
2. **记忆系统**：引入滑动记忆窗口，实现上下文连贯

---

## 🔧 详细改动

### 1️⃣ config.py - LLM 配置扩展

**新增配置项**：
```python
# Grok (xAI) 配置 - 主服务
GROK_API_KEY = (os.getenv("GROK_API_KEY", "") or "").strip()
GROK_BASE_URL = (os.getenv("GROK_BASE_URL", "https://api.x.ai/v1") or "").strip()
MODEL_NAME = (os.getenv("MODEL_NAME", "grok-3-mini") or "").strip()
```

**说明**：
- 保留了 OpenAI 配置作为备用
- 新增了 Grok 专用配置（优先级更高）
- `MODEL_NAME` 支持 `grok-beta` 或 `grok-2-latest`

---

### 2️⃣ decision_engine.py - Grok 客户端集成

#### 改动点 A：导入更新
```python
# 旧配置
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

# 新配置
from config import GROK_API_KEY, GROK_BASE_URL, MODEL_NAME
```

#### 改动点 B：客户端初始化
```python
class DecisionEngine:
    def __init__(self):
        # 使用 Grok (xAI) API - OpenAI SDK 兼容
        self.client = OpenAI(
            api_key=GROK_API_KEY,
            base_url=GROK_BASE_URL
        )
```

#### 改动点 C：API 调用更新
```python
resp = self.client.chat.completions.create(
    model=MODEL_NAME,  # 使用 Grok 模型
    response_format={"type": "json_object"},  # 强制 JSON 输出 ⭐
    messages=[
        {"role": "system", "content": system_prompt}
    ] + messages,
    temperature=0.7
)
```

**关键点**：
- `response_format={"type": "json_object"}` 确保 Grok 返回有效 JSON
- OpenAI SDK 完全兼容 Grok API（通过 base_url 重定向）

---

### 3️⃣ user_profiles.py - 滑动记忆窗口

#### 改动点 A：数据模型更新
```python
@dataclass
class UserProfile:
    # ... 原有字段 ...
    history: List[Dict[str, str]] = field(default_factory=list)
    # 对话历史 - 滑动窗口（最多 8 条消息）
```

#### 改动点 B：向后兼容处理
```python
@staticmethod
def from_dict(data: dict) -> "UserProfile":
    # 处理向后兼容 - 旧数据可能没有 history 字段
    if "history" not in data:
        data["history"] = []
    return UserProfile(**data)
```

#### 改动点 C：记忆管理方法

**添加到历史**：
```python
def add_message_to_history(self, user_id: int, role: str, content: str) -> None:
    profile = self.get_or_create(user_id)
    profile.history.append({"role": role, "content": content})
    
    # 滑动窗口：只保留最近的 8 条对话（4个回合）
    max_history = 8
    if len(profile.history) > max_history:
        profile.history = profile.history[-max_history:]
    
    self.save_profiles()
```

**获取历史**：
```python
def get_message_history(self, user_id: int) -> List[Dict[str, str]]:
    profile = self.get_or_create(user_id)
    if not hasattr(profile, "history") or profile.history is None:
        return []
    return profile.history
```

#### 改动点 D：便利函数
```python
def add_message_to_history(user_id: int, role: str, content: str) -> None:
    """向用户对话历史中添加消息"""
    user_profile_manager.add_message_to_history(user_id, role, content)

def get_message_history(user_id: int) -> List[Dict[str, str]]:
    """获取用户对话历史"""
    return user_profile_manager.get_message_history(user_id)
```

---

### 4️⃣ brain.py - 记忆集成层

#### 改动点 A：导入更新
```python
from user_profiles import get_message_history, add_message_to_history
```

#### 改动点 B：三步流程
```python
async def ask_brain(...):
    # 🎯 第一步：获取用户的对话历史（滑动窗口）
    user_history = get_message_history(user_id)
    
    # 🎯 第二步：将当前用户消息添加到历史
    add_message_to_history(user_id, "user", user_text)
    
    # 调用决策引擎（传递历史上下文）
    decision = await make_decision(
        user_message=user_text,
        user_id=user_id,
        username=username,
        source=source,
        persona_config=PERSONA_CONFIG,
        user_history=user_history  # 把历史记录传给 LLM ⭐
    )
    
    # 🎯 第三步：如果决策成功，将 Roxy 的回复也添加到历史
    if decision:
        reply_text = decision.content.get("text", "")
        if reply_text:
            add_message_to_history(user_id, "assistant", reply_text)
```

---

## 📊 消息流程图

```
用户消息到达
    ↓
ask_brain() - 大脑控制层
    ├─ 获取历史：get_message_history(user_id)
    ├─ 记录提问：add_message_to_history(user_id, "user", text)
    ├─ 调用 LLM：await make_decision(..., user_history)
    │   ├─ 系统提示词
    │   ├─ 历史消息（最近 8 条）⭐
    │   └─ 当前消息
    ├─ Grok 响应（JSON 格式）
    └─ 记录回复：add_message_to_history(user_id, "assistant", reply)
        ↓
    执行决策（语音/文字/梗图）
```

---

## 🎯 环境变量要求

在 `.env` 文件中配置：

```bash
# Grok (xAI) - 必需
GROK_API_KEY="xai-..."
GROK_BASE_URL="https://api.x.ai/v1"
MODEL_NAME="grok-3-mini"  # 或 grok-2-latest

# OpenAI - 可选（备用）
OPENAI_API_KEY="sk-..."
OPENAI_BASE_URL="https://api.openai.com/v1"
OPENAI_MODEL="gpt-4o-mini"
```

---

## 💡 核心改进点

| 方面 | 改进前 | 改进后 |
|------|--------|--------|
| **LLM** | OpenAI (ChatGPT) | Grok (xAI) |
| **上下文** | 无记忆（每次单条消息） | 滑动窗口（最近 8 条消息） |
| **Token 效率** | ❌ 无法感知历史 | ✅ 理解对话上下文，避免重复 |
| **人物连贯性** | 有情绪但无记忆 | 🎯 有情绪 + 有记忆 = 真正的对话 |
| **成本** | 取决于 OpenAI 定价 | 取决于 xAI 定价（通常更便宜） |

---

## 🧪 测试检查清单

- [ ] 确认 `.env` 中配置了 `GROK_API_KEY` 和 `GROK_BASE_URL`
- [ ] 运行 `python -c "from decision_engine import DecisionEngine; print('OK')"` 验证导入
- [ ] 在私聊中发送消息，验证 Roxy 能正确响应
- [ ] 连续发送 3+ 条消息，验证 Roxy 能引用之前的内容
- [ ] 检查 `./cache/user_profiles.json` 中的 `history` 字段是否被正确保存
- [ ] 监控日志 `[brain] 用户 X 的历史记录条数: Y` 确认滑动窗口工作正常

---

## 🔄 向后兼容性

✅ **完全兼容旧数据**：
- 旧 `user_profiles.json` 在加载时自动添加 `history: []`
- 现有的情绪、好感度、熟悉度数据保持不变
- 第一次运行时会自动生成 history 字段

---

## 📚 相关文档

- `ROXY_V2_GUIDE.md` - 完整使用指南（已过期部分可忽略）
- `QUICK_REFERENCE.md` - 快速参考卡（仍然适用）
- `DEPLOYMENT_CHECKLIST.md` - 部署清单

---

## ❓ 常见问题

**Q: Grok API 是否支持 JSON 模式？**
A: 是的，Grok 完全支持 OpenAI 的 `response_format={"type": "json_object"}`

**Q: 历史记忆会导致 Token 爆炸吗？**
A: 不会，我们限制了滑动窗口为最近 8 条消息（4个回合）

**Q: 如何清除某用户的历史记忆？**
A: 编辑 `./cache/user_profiles.json`，删除 `history` 数组即可

**Q: decision_engine.py 还支持 OpenAI 吗？**
A: 目前以 Grok 为主。如需切换，可改回配置或修改导入

---

**更新时间**：2026-03-24  
**改动者**：GitHub Copilot  
**版本**：Roxy v2.2 (Grok Edition + Memory)
