# 执行层重构总结 - 2026.03.27

## 概述
完成了两个核心模块的大幅重构：
1. **Grok 润色器** (content_refiner.py) - 从"升级攻击性"模式改为"同强度自然化"
2. **执行层** (action_executor.py) - 从灵活的降级链改为严格的 5 条硬规则驱动

---

## 改动详情

### 1️⃣ Grok 润色器重写 (content_refiner.py)

#### 核心改变

**新 System Prompt：** `GROK_POLISH_SYSTEM_PROMPT`
- 只做"口语微调"，不做"重写"或"升级攻击性"
- 10 条硬性规则（包括长度限制、风格保持等）
- 明确禁止操作：新增嘲讽、羞辱、命令、PUA、阴阳怪气、威胁

**新函数：**
- `build_grok_polish_user_prompt()` - 构建带完整上下文的 Prompt
- `should_skip_polish()` - 6 个跳过条件（serious_mode, ignore, should_text=false 等）
- `looks_more_aggressive()` - 9 种关键词的攻击性升级检测
- `polish_decision_with_grok()` - 异步润色主函数，包含 4 层安全护栏

**硬规则跳过条件：**
```python
if serious_mode:  # 严肃模式不润
if mode == "ignore":  # 忽略模式不润
if not should_text:  # 表示不要文本时，不能乱补字
if style in {"cold"}:  # 冷态只有边界，不能升级
if intent in {"boundary", "ignore", "stabilize", "comfort"}:  # 边界意图不升级
if len(text) <= 4:  # 原文很短就保持短
```

**安全护栏：**
1. 不允许把空文本润出来（要么有要么无）
2. 长度不膨胀超过 +20% 或 +8 字
3. 润色失败回滚到原文
4. 检测攻击性升级，如有则回滚

---

### 2️⃣ 执行层重写 (action_executor.py)

#### 5 条执行层硬规则

```
规则 1: mode == ignore → 绝不发任何文本
规则 2: should_text == false 且 mode != voice → 绝不补文本
规则 3: meme 发失败 → 只有 should_text == true 才能回退文本
规则 4: delay_send 发出前 → 检查是不是最新请求
规则 5: 执行层不能自己造句（无 "……" / "收到" / "嗯" 补充）
```

#### 新数据结构

**`normalize_decision_for_execution()`** - 决策归一化函数
- 确保执行前决策对象已清洁
- 阻止执行层自作主张补文本
- 4 层防护规则检查

#### 并发控制

**用户级串行化 + 请求 ID：**
```python
class ActionExecutor:
    def __init__(self):
        self.user_locks = defaultdict(asyncio.Lock)  # 每用户一把锁
        self.latest_req_id = defaultdict(int)  # 请求 ID 计数
    
    def next_req_id(self, user_id: int) -> int:
        self.latest_req_id[user_id] += 1
        return self.latest_req_id[user_id]
```

**防旧请求晚到：**
- 每个用户的每条新消息都分配一个递增 ID
- delay 执行前检查是否已被新请求覆盖
- 旧请求自动丢弃（不会重复回复）

#### 执行矩阵（严格模式）

新的 `_execute_decision_sync()` 方法：
1. 先 normalize 决策
2. 更新用户交互统计
3. 应用情绪更新
4. 按 mode 分流执行

**模式分流：**
- `ignore` → 直接返回，不发
- `delay` / `delay_send` → 延迟后重新进入流程
- `voice` → 只发声音，不补文本
- `text_image` → 先尝试梗图，失败时检查 should_text 再降级
- `text` → 只有 should_text==true 才发，否则跳过

#### 实例方法替代静态方法

旧方式（静态）：
```python
@staticmethod
async def _execute_voice(...): ...
```

新方式（实例）：
```python
async def _execute_voice(self, user_id: int, group_id: Optional[int], voice_text: str):
    # 可以访问 self.user_locks, self.latest_req_id 等
```

#### 关键方法

- `execute_decision()` - 入口，获取用户锁后调用 sync 版本
- `_execute_decision_sync()` - 核心流程（归一化、分流、执行）
- `_execute_delay()` - 延迟执行，防旧请求
- `_execute_voice()` - 语音发送，TTS 离线自动跳过
- `_execute_text()` - 文本发送，保留 clean_roxy_text 护栏
- `_execute_meme()` - 梗图发送，返回 bool 决定是否降级

---

### 3️⃣ app.py 调整

**导入更新：**
```python
from .core.action_executor import execute_decision, action_executor
```

**两处调用都添加了请求 ID：**
```python
# 私聊处理
req_id = action_executor.next_req_id(user_id)
exec_result = await execute_decision(
    decision=decision,
    user_id=user_id,
    username=username,
    group_id=None,
    req_id=req_id,  # 新增
    enable_grok_refine=REFINE_WITH_GROK,
    persona_config=PERSONA_CONFIG
)

# 群聊处理
req_id = action_executor.next_req_id(user_id)
exec_result = await execute_decision(
    decision=decision,
    user_id=user_id,
    username=username,
    group_id=group_id,
    req_id=req_id,  # 新增
    enable_grok_refine=REFINE_WITH_GROK,
    persona_config=PERSONA_CONFIG
)
```

---

## 核心改进

### ✅ Grok 润色器改进

| 方面 | 之前 | 之后 |
|------|------|------|
| 能力 | 大幅改写文案 | 微调措辞保持原意 |
| Prompt | 单一通用 Prompt | 带完整上下文的 Prompt |
| 长度 | 可能膨胀到 2 倍 | 最多 +20% 或 +8 字 |
| 风格升级 | 可以升级攻击性 | 禁止升级攻击性 |
| 失败处理 | 无特殊处理 | 4 层安全护栏 |
| 跳过逻辑 | 无 | 6 个明确跳过条件 |

### ✅ 执行层改进

| 方面 | 之前 | 之后 |
|------|------|------|
| 架构 | 降级链模式（灵活） | 硬规则驱动（严格） |
| 并发 | 无保护 | 用户级串行锁 |
| 延迟问题 | 可能重复回复 | 请求 ID 防止旧请求 |
| 文本补充 | 可能乱补 "……" | 严禁补充任何内容 |
| 执行逻辑 | 静态方法，难以跟踪 | 实例方法，可访问状态 |

---

## 调用示例

### 私聊处理
```python
req_id = action_executor.next_req_id(user_id)
exec_result = await execute_decision(
    decision=llm_output,
    user_id=123456789,
    username="Alice",
    group_id=None,
    req_id=req_id,
    enable_grok_refine=True,
    persona_config=PERSONA_CONFIG
)
```

### 群聊处理
```python
req_id = action_executor.next_req_id(user_id)
exec_result = await execute_decision(
    decision=llm_output,
    user_id=123456789,
    username="Alice",
    group_id=987654321,
    req_id=req_id,
    enable_grok_refine=True,
    persona_config=PERSONA_CONFIG
)
```

---

## 测试要点

### Grok 润色器
- ✓ 跳过条件：serious_mode, ignore, should_text=false, cold 风格
- ✓ 长度限制：不超过原文 +20% 或 +8 字
- ✓ 安全护栏：检测攻击性升级，如有则回滚
- ✓ 空文本保护：不允许把空变成有，也不允许把有变成空

### 执行层 5 条规则
- ✓ mode=ignore 不发任何东西
- ✓ should_text=false 不补文本
- ✓ meme 失败时只有 should_text==true 才降级到文本
- ✓ delay 检查请求 ID，旧请求自动丢弃
- ✓ 执行层不补"……"等词

### 并发处理
- ✓ 同一用户多条消息不会并发执行（串行锁）
- ✓ delay_send 10 秒内新消息覆盖旧消息

---

## 文件修改列表

1. `src/utils/content_refiner.py` - 完全重写，280+ 行
2. `src/core/action_executor.py` - 核心方法改写，500+ 行
3. `src/app.py` - 两处调用添加 req_id

---

## 后续工作

- [ ] 测试 Grok 润色器跳过条件是否正确
- [ ] 测试延迟消息防重复
- [ ] 测试 meme 失败时的降级逻辑
- [ ] 监控执行层异常日志
- [ ] 可选：添加执行层性能指标

---

## 关键设计决策

### 为什么用硬规则而不是灵活降级链？
**原因：** 降级链虽然灵活，但执行层容易自作主张补文本。硬规则强制约束，防止意外。

### 为什么要请求 ID？
**原因：** delay_send 可能导致旧请求晚到，重复回复。请求 ID 确保只有最新请求被执行。

### 为什么用实例方法而不是静态方法？
**原因：** 需要访问 user_locks 和 latest_req_id，实例方法更自然。

### 为什么 Grok 只做"同强度自然化"？
**原因：** 升级攻击性是 LLM 的职责，不是润色器的职责。润色器应该保持中立。

