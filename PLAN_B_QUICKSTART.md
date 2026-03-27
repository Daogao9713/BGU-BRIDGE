# 方案 B 实施完成 - 快速启动指南

## 🎯 什么是方案 B？

**方案 B: DeepSeek + Grok 双轨模式**

= 决策稳定（DeepSeek）+ 文案有趣（Grok 润色）

```
用户消息
    ↓
DeepSeek → JSON 决策（稳定、可控）
    ↓
[可选] Grok → 文案润色（更有趣）
    ↓
执行层 → 发送到 QQ
```

---

## ⚡ 一键启动

### Windows 用户

直接运行改进的启动脚本：

```bash
start_roxy.bat
```

会依次提示：

1. **选择决策引擎**
   ```
   请选择主决策引擎 (LLM):
   1) DeepSeek ★ 推荐
   2) OpenAI / ChatGPT
   3) Grok (XAI)
   4) Gemini (Google)
   ```
   → 选择 **1** (DeepSeek)

2. **选择启用方案**
   ```
   是否启用 Grok 润色层? (方案 B - 最灵活)
   
   方案 A: 纯 DeepSeek (推荐首选)
   方案 B: DeepSeek + Grok 双轨 (最灵活)
   ```
   → 选择 **y** 启用方案 B，或 **n** 使用纯 DeepSeek

3. **自动启动**
   ```
   [INFO] 启动配置：
     - 主决策引擎: DeepSeek
     - Grok 润色: true
     - 监听地址: http://127.0.0.1:9000
   ```

---

## 🔧 环境变量配置

### 方案 A：纯 DeepSeek（推荐首选）

**最小配置** - `.env` 文件：

```env
# 主决策引擎
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_key

# 其他必要配置
NAPCAT_API=http://127.0.0.1:6090
BOT_QQ=your_bot_qq
TARGET_GROUP_ID=your_group_id
```

启动：

```bash
start_roxy.bat
→ 选 1 (DeepSeek)
→ 选 n (不用 Grok 润色)
```

**优点**：
- ✓ 配置简单
- ✓ 响应快速
- ✓ 成本低
- ✓ 可控性强

**缺点**：
- ✗ 文案风格一般

---

### 方案 B：DeepSeek + Grok 双轨（最灵活）

**完整配置** - `.env` 文件：

```env
# 主决策引擎（DeepSeek）
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_key

# Grok 润色层（可选）
GROK_API_KEY=your_grok_api_key
GROK_BASE_URL=https://api.x.ai/v1

# 启用 Grok 润色
REFINE_WITH_GROK=true

# Grok 润色参数
GROK_REFINE_TEMPERATURE=0.7      # 越高越创意（0-2.0）
GROK_REFINE_MAX_TOKENS=100        # 最多生成字数
GROK_REFINE_TIMEOUT=5             # 等待超时（秒）

# 其他必要配置
NAPCAT_API=http://127.0.0.1:6090
BOT_QQ=your_bot_qq
TARGET_GROUP_ID=your_group_id
```

启动：

```bash
start_roxy.bat
→ 选 1 (DeepSeek)
→ 选 y (启用 Grok 润色)
```

**优点**：
- ✓ 决策稳定（DeepSeek）
- ✓ 文案有趣（Grok）
- ✓ 精确控制
- ✓ 个性化强

**缺点**：
- ✗ 需要两个 API Key
- ✗ 延迟稍高（多一层 API）
- ✗ 成本稍高

---

## 📚 获取 API Key

### DeepSeek API Key

1. 访问 https://platform.deepseek.com/
2. 注册登录
3. 左侧 "API Keys" → "Create API Key"
4. 复制 Key 到 `.env` 中的 `DEEPSEEK_API_KEY`

### Grok API Key

1. 访问 https://console.x.ai/
2. 注册登录
3. "API Keys" → "Create API Key"
4. 复制 Key 到 `.env` 中的 `GROK_API_KEY`

---

## 🚀 启动后的日志

### 方案 A 日志示例

```
[INFO] 启动配置：
  - 主决策引擎: DeepSeek
  - Grok 润色: false
  - 监听地址: http://127.0.0.1:9000

INFO:     Uvicorn running on http://127.0.0.1:9000

[decision_engine] 调用 DeepSeek API...
[brain] decision = DecisionOutput(...)
[executor] 执行分流逻辑
[文本+梗图] 发送成功
```

### 方案 B 日志示例

```
[INFO] 启动配置：
  - 主决策引擎: DeepSeek
  - Grok 润色: true
  - 监听地址: http://127.0.0.1:9000

INFO:     Uvicorn running on http://127.0.0.1:9000

[decision_engine] 调用 DeepSeek API...
[Grok 润色] 开始润色文案
[Grok 润色] '这也太可笑了' → '不屑一顾但想吐槽你的样子'
[Grok 润色] 完成 → {...}
[executor] 执行分流逻辑
[文本+梗图] 发送成功
```

---

## 🎯 改动快速总结

### 新建文件

- ✅ `content_refiner.py` - Grok 润色引擎

### 改动文件

- ✅ `config.py` - 新增 Grok 润色配置
- ✅ `action_executor.py` - 支持 `enable_grok_refine` 参数
- ✅ `app.py` - 集成 Grok 润色到执行流程
- ✅ `start_roxy.bat` - 改进启动脚本，支持双轨模式选择

### 修复

- ✅ 修复 action="meme" 的处理（原来没有显式处理）

---

## 🧪 测试命令

### 纯 Python 测试（无需启动服务）

```python
# 测试 Grok 润色
from content_refiner import refine_with_grok
import asyncio

async def test():
    result = await refine_with_grok("这也太可笑了", style="playful")
    print(f"润色结果: {result}")

asyncio.run(test())
```

### 完整流程测试

1. 启动服务
   ```bash
   start_roxy.bat
   ```

2. 发送测试消息到 QQ 机器人
   ```
   用户: @Roxy 你很傻
   ```

3. 查看控制台日志
   ```
   [Grok 润色] '你才傻呢' → '我比你聪明一万倍呢'
   [文本+梗图] 发送成功
   ```

---

## 💡 配置建议

### 场景 1：个人使用（推荐方案 A）

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
REFINE_WITH_GROK=false
```

- 快速响应
- 成本低
- 决策稳定

### 场景 2：追求个性化（推荐方案 B）

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
GROK_API_KEY=...
REFINE_WITH_GROK=true
GROK_REFINE_TEMPERATURE=0.8  # 更有创意
```

- 文案更有趣
- 个性化强
- 成本稍高

### 场景 3：低成本优先

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
REFINE_WITH_GROK=false
```

与场景 1 相同

### 场景 4：生产环境

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
GROK_API_KEY=...
REFINE_WITH_GROK=true
GROK_REFINE_TEMPERATURE=0.6  # 保守一些
GROK_REFINE_TIMEOUT=3        # 缩短超时
```

- 稳定 + 有趣
- 快速降级
- 自动容错

---

## 🔍 故障排查

### 问题 1：启动脚本选项不出现

**症状**：启动后直接崩溃或没有菜单

**解决**：
```bash
# 手动启动
cd E:\Project\bgu-qq-bridge
.venv\Scripts\activate
python -m uvicorn app:app --port 9000
```

### 问题 2：Grok 润色失败，但系统继续运行

**症状**：日志显示 `[Grok 润色失败] ...，使用原文`

**原因**：
- Grok API Key 无效
- 网络问题
- API 超时

**解决**：
- 检查 `.env` 中的 `GROK_API_KEY`
- 增加 `GROK_REFINE_TIMEOUT`
- 禁用 Grok 润色：`REFINE_WITH_GROK=false`

### 问题 3：梗图不显示

**症状**：日志显示 `[梗图] 梗图不存在`

**原因**：梗图文件不存在或标签错误

**解决**：
- 检查 `./memes/` 目录是否有对应文件
- 查看 `action_executor.py` 中的 `MEME_MAP`

---

## 📖 完整文档

- [EXECUTOR_REFACTOR_SUMMARY.md](EXECUTOR_REFACTOR_SUMMARY.md) - 技术细节
- [EXECUTOR_QUICK_REFERENCE.md](EXECUTOR_QUICK_REFERENCE.md) - 快速查询
- [DEEPSEEK_GROK_GUIDE.md](DEEPSEEK_GROK_GUIDE.md) - 架构指南

---

## ✅ 收检清单

- [x] Grok 润色引擎 (`content_refiner.py`)
- [x] 配置项新增 (`REFINE_WITH_GROK` 等)
- [x] 执行层集成 (`enable_grok_refine` 参数)
- [x] 应用层集成 (`app.py` 调用处)
- [x] 启动脚本改进 (双轨模式选择)
- [x] 梗图 action 修复 (`action="meme"`)
- [x] 语法验证通过

---

## 🚀 立即开始

```bash
# 1. 配置 .env 文件
# 2. 运行启动脚本
start_roxy.bat

# 3. 选择模式
# 方案 A: 纯 DeepSeek (快速/稳定) ← 推荐首选
# 方案 B: DeepSeek + Grok (有趣/灵活) ← 可选升级

# 4. 等待启动完成
# 5. 发送消息到 QQ 机器人测试
```

---

**方案 B 已完全实施。祝你使用愉快！** 🎉

