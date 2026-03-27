# 🤖 LLM 厂商动态切换指南

## 📋 概述

Roxy 现在支持在四个主流 LLM 厂商之间自动切换：
- **DeepSeek** (默认)
- **OpenAI** (ChatGPT)
- **Grok** (XAI)
- **Gemini** (Google)

通过设置 `LLM_PROVIDER` 环境变量或使用**交互式启动菜单**，无需修改代码即可在启动时选择厂商。

---

## 🚀 快速开始（3 种方式）

### 方式 1️⃣ : 使用启动菜单（最简单）⭐ 推荐

直接运行启动脚本，会弹出菜单让你选择：

```bash
# Windows
start_roxy.bat

# 或在 PowerShell 中
.\start_roxy.bat
```

菜单界面：
```
======================================================
           LLM 厂商选择菜单
======================================================

请选择 LLM 服务厂商:

  1) DeepSeek (默认)
  2) OpenAI / ChatGPT
  3) Grok (XAI)
  4) Gemini (Google)

======================================================

请输入选择 (1-4):
```

### 方式 2️⃣ : 修改 .env 文件

编辑 `.env` 文件，修改以下行：

```bash
# 选择要使用的 LLM 厂商: openai, deepseek, grok, gemini (默认: deepseek)
LLM_PROVIDER=deepseek

# 然后根据选择配置相应的 API Key 和模型
DEEPSEEK_API_KEY="sk-..."
DEEPSEEK_BASE_URL="https://api.deepseek.com"
DEEPSEEK_MODEL="deepseek-chat"
```

### 方式 3️⃣ : 通过环境变量临时切换

启动前设置环境变量：

```powershell
# Windows PowerShell
$env:LLM_PROVIDER="grok"
uvicorn app:app --port 9000

# 或一行
$env:LLM_PROVIDER="openai"; uvicorn app:app --port 9000
```

---

## 📊 支持的厂商配置

| 厂商 | LLM_PROVIDER | API Key 环境变量 | 基础 URL 环境变量 | 模型环境变量 | 默认模型 |
|-------|--------------|-----------------|-------------------|------------|---------|
| **DeepSeek** | `deepseek` | DEEPSEEK_API_KEY | DEEPSEEK_BASE_URL | DEEPSEEK_MODEL | deepseek-chat |
| **OpenAI** | `openai` | OPENAI_API_KEY | OPENAI_BASE_URL | OPENAI_MODEL | gpt-4o-mini |
| **Grok** | `grok` | GROK_API_KEY | GROK_BASE_URL | GROK_MODEL | grok-2 |
| **Gemini** | `gemini` | GEMINI_API_KEY | GEMINI_BASE_URL | GEMINI_MODEL | gemini-2.0-flash-001 |

---

## 📝 完整 .env 配置模板

```bash
# ============ LLM 厂商配置 ============
# 选择要使用的 LLM 厂商: openai, deepseek, grok, gemini (默认: deepseek)
LLM_PROVIDER=deepseek

# ===== OpenAI (ChatGPT) 配置 =====
OPENAI_API_KEY="sk-proj-xxxxxxxxxxxx"
OPENAI_BASE_URL="https://api.openai.com/v1"
OPENAI_MODEL="gpt-4o-mini"

# ===== DeepSeek 配置 =====
DEEPSEEK_API_KEY="sk-xxxxxxxxxxxx"
DEEPSEEK_BASE_URL="https://api.deepseek.com"
DEEPSEEK_MODEL="deepseek-chat"

# ===== Grok (XAI) 配置 =====
GROK_API_KEY="xai-xxxxxxxxxxxx"
GROK_BASE_URL="https://api.x.ai/v1"
GROK_MODEL="grok-2"

# ===== Gemini (Google) 配置 =====
GEMINI_API_KEY="xxxxxxxxxxxxxxxx"
GEMINI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL="gemini-2.0-flash-001"

# ============ QQ 机器人配置 ============
NAPCAT_API="http://127.0.0.1:6090"
ONEBOT_TOKEN="KTvC738advK6nemG"
BOT_QQ=3137390061
PORT=9000

# ============ 语音合成配置 ============
TTS_GPU_IP="192.168.31.211"
TTS_SPEAKER="绝区零-中文-铃"

# ============ 群白名单和触发前缀 ============
GROUP_WHITELIST="123456789,987654321"
USER_WHITELIST=""
TRIGGER_PREFIX="Roxy,roxy,洛希,萝西"

# ============ 定时事件配置 (生物钟) ============
TARGET_GROUP_ID="773424895"
```

---

## 🔍 验证配置

启动 Roxy 后，会在控制台输出如下信息：

```
============================================================
🤖 LLM 厂商信息
============================================================
当前选择厂商: GROK (XAI)
服务商标识 (LLM_PROVIDER): grok
模型前缀 (MODEL_NAME): grok-2
API Key 已配置: ✓
============================================================
```

**输出说明：**
- 如果看到 `API Key 已配置: ✗`，说明密钥未正确配置，需要检查 `.env` 文件
- 服务商标识对应 `LLM_PROVIDER` 的值
- 模型前缀是从环境变量中读取的模型名称前缀

---

## 🎯 应用场景示例

### 场景 1: 切换到 OpenAI 进行测试

**方式 A - 通过菜单**（推荐）
```bash
start_roxy.bat
# 输入 2，选择 OpenAI
```

**方式 B - 修改 .env**
```bash
LLM_PROVIDER=openai
```

### 场景 2: 使用 Gemini 节省成本

```bash
start_roxy.bat
# 输入 4，选择 Gemini (Google)
```

### 场景 3: 回到 DeepSeek（默认）

```bash
start_roxy.bat
# 输入 1，选择 DeepSeek
```

### 场景 4: 在启动脚本中硬编码厂商

创建 `start_roxy_deepseek.bat`：
```batch
@echo off
setlocal enabledelayedexpansion
call .venv\Scripts\activate
set LLM_PROVIDER=deepseek
python -m uvicorn app:app --host 127.0.0.1 --port 9000 --reload
pause
```

---

## ⚙️ 内部工作原理

### 配置加载流程

```
1. 读取 .env 文件
   ↓
2. 检查 LLM_PROVIDER 环境变量 (默认: deepseek)
   ↓
3. 根据 LLM_PROVIDER 值查询 _PROVIDER_CONFIG 字典
   ↓
4. 提取对应的 API Key、Base URL、模型名
   ↓
5. 生成 ACTIVE_API_KEY、ACTIVE_BASE_URL、MODEL_NAME、ACTIVE_PROVIDER_NAME
   ↓
6. DecisionEngine 使用动态配置初始化 OpenAI 客户端
   ↓
7. 启动时打印当前厂商信息
```

### 代码位置

- **厂商配置**: [config.py](config.py) (第 7-70 行)
- **启动脚本**: [start_roxy.bat](start_roxy.bat) (第 19-51 行)
- **启动日志**: [app.py](app.py) lifespan 函数
- **动态初始化**: [decision_engine.py](decision_engine.py) (第 88-91 行)

---

## 🐛 故障排查

### 问题 1: 启动菜单显示乱码

**原因**: 编码问题  
**解决方案**:
1. 确保 `start_roxy.bat` 以 UTF-8 BOM 编码保存
2. 使用 VS Code 打开 bat 文件，设置编码为 UTF-8

### 问题 2: 选择后仍然使用旧的模型

**原因**: 虚拟环境没有重新加载 .env 文件  
**解决方案**:
- 重启启动脚本
- 或者关闭 Python 进程后重新运行

### 问题 3: API Key 出现 Permission Denied

**原因**: API Key 已过期或账户未激活  
**解决方案**:
1. 登录对应的 API 控制台验证密钥
2. 重新生成新的 API Key
3. 更新 .env 文件

### 问题 4: 模型返回 404 错误

**原因**: 模型名称不在该厂商的可用列表中  
**解决方案**:
- 查看对应厂商的 API 文档，获取最新的可用模型列表
- 更新 `.env` 中的模型环境变量

---

## 💡 最佳实践

1. **不同用途分别配置**
   - 开发测试用 Gemini（便宜、快速）
   - 生产环境用 DeepSeek 或 OpenAI（稳定、可靠）

2. **定期检查余额**
   - 为每个厂商的 API 账户设置使用额度预警

3. **轮流使用多个模型**
   - 利用 `start_roxy.bat` 菜单灵活切换
   - 获得不同模型风格的回复

4. **备用方案**
   - 至少配置两个不同厂商的完整凭证
   - 防止主模型服务中断时无法运行

---

## 🔗 相关资源

- [DeepSeek API 文档](https://api-docs.deepseek.com)
- [OpenAI API 文档](https://platform.openai.com/docs)
- [Grok API 文档](https://docs.x.ai)
- [Gemini API 文档](https://ai.google.dev)

---

**最后更新**: 2026-03-25  
**版本**: 2.2  
**新增内容**: 
- ✅ Gemini (Google) 支持
- ✅ 交互式启动菜单 (start_roxy.bat)

---

## 🚀 快速开始

### 方式 1: 通过 .env 文件配置

编辑 `.env` 文件，添加或修改以下内容：

```bash
# 选择模型提供商: openai, grok, deepseek
# 如果不设置，默认为 deepseek
LLM_PROVIDER=deepseek

# ===== OpenAI 配置 =====
OPENAI_API_KEY=sk-xxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# ===== Grok 配置 =====
GROK_API_KEY=xxxxxxxxxxxx
GROK_BASE_URL=https://api.x.ai/v1
GROK_MODEL=grok-2

# ===== DeepSeek 配置 =====
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

### 方式 2: 通过环境变量切换

启动时直接指定：

```bash
# Windows PowerShell
$env:LLM_PROVIDER="openai"
python -m uvicorn app:app --port 9000

# Linux/Mac Bash
export LLM_PROVIDER=grok
uvicorn app:app --port 9000

# 或一行命令
LLM_PROVIDER=deepseek uvicorn app:app --port 9000
```

### 方式 3: 通过启动脚本

修改 `start_roxy.bat` 或创建启动脚本：

```batch
@echo off
REM 切换模型：deepseek, grok, openai
set LLM_PROVIDER=grok
set OPENAI_API_KEY=sk-xxxxxxxxxxxx
set GROK_API_KEY=xxxxxxxxxxxx
set DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx

python -m uvicorn app:app --port 9000
```

---

## 📊 支持的模型配置

| 提供商 | LLM_PROVIDER | 模型名称参数 | 默认模型 | 需要的密钥 |
|--------|--------------|----------|---------|----------|
| OpenAI (ChatGPT) | `openai` | OPENAI_MODEL | gpt-4o-mini | OPENAI_API_KEY |
| Grok (XAI) | `grok` | GROK_MODEL | grok-2 | GROK_API_KEY |
| DeepSeek | `deepseek` | DEEPSEEK_MODEL | deepseek-chat | DEEPSEEK_API_KEY |

---

## 🔍 验证配置

启动 Roxy 后，会在控制台输出如下信息：

```
============================================================
🤖 LLM 模型信息
============================================================
当前选择模型 (LLM_PROVIDER): DEEPSEEK
模型名称 (MODEL_NAME): deepseek-chat
API Key 已配置: ✓
============================================================
```

如果看到 `API Key 已配置: ✗`，说明密钥未正确配置，需要检查 `.env` 文件。

---

## 🎯 切换场景示例

### 场景 1: 快速从 DeepSeek 切换到 OpenAI

```bash
# 只需修改环境变量，其他不动
set LLM_PROVIDER=openai
```

### 场景 2: 使用 Grok 进行测试

```bash
LLM_PROVIDER=grok uvicorn app:app --port 9000 --reload
```

### 场景 3: 回退到 DeepSeek（默认）

```bash
# 不设置 LLM_PROVIDER，或显式设置为 deepseek
set LLM_PROVIDER=deepseek
```

---

## ⚙️ 内部工作原理

### 配置加载流程

1. **读取环境变量**  
   - `LLM_PROVIDER` (默认: `deepseek`)  
   - 各模型的 `*_API_KEY`, `*_MODEL` 等配置

2. **自动选择配置**  
   - 根据 `LLM_PROVIDER` 值选择对应的 API 密钥和端点
   - 将选中的配置复制到 `ACTIVE_API_KEY`, `ACTIVE_BASE_URL`, `MODEL_NAME`

3. **初始化 DecisionEngine**  
   - 创建 OpenAI 客户端时使用 `ACTIVE_API_KEY` 和 `ACTIVE_BASE_URL`
   - LLM 调用时使用 `MODEL_NAME`

4. **启动日志输出**  
   - 在 FastAPI 启动时打印选中的模型信息

### 代码位置

- **配置逻辑**: `config.py` (第 7-45 行)
- **初始化逻辑**: `decision_engine.py` (第 88-91 行)
- **启动日志**: `app.py` lifespan 函数 (第 150-151 行)

---

## 🐛 故障排查

### 问题 1: API Key 已配置但仍然报错

**原因**: API Key 格式不正确或已过期  
**解决方案**:
- 检查 `.env` 文件中 API Key 没有多余空格
- 更新到最新的有效 API Key
- 确认模型名称 (`*_MODEL`) 与对应服务的可用模型一致

### 问题 2: 切换模型后无效果

**原因**: 环境变量未正确加载  
**解决方案**:
1. 重新启动应用（必须）
2. 确认 `.env` 文件存在于项目根目录
3. 检查 `LLM_PROVIDER` 拼写（必须小写）

### 问题 3: 某个模型持续超时

**原因**: API 端点不可达或配置的 `*_BASE_URL` 错误  
**解决方案**:
- 测试 API 端点连通性: `curl https://api.example.com/health`
- 确认 `*_BASE_URL` 末尾**没有**斜杠 `/`

---

## 💡 最佳实践

1. **单一真源原则**  
   - 推荐在 `.env` 文件中管理所有配置，避免混淆
   - 不要在代码中硬编码 API Key

2. **定期轮换**  
   - 为不同的模型分别生成独立的 API Key
   - 定期检查密钥使用量和账单

3. **性能对比**  
   - 在切换前使用同一问题测试不同模型的响应时间
   - 根据实际对话效果选择最适合的模型

4. **备用方案**  
   - 配置至少两个模型的完整凭证，以防主模型服务中断

---

## 📝 配置模板

复制以下模板到 `.env` 文件：

```bash
# ===== LLM 模型选择 =====
# 可选值: openai, grok, deepseek (默认: deepseek)
LLM_PROVIDER=deepseek

# ===== OpenAI 配置 =====
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# ===== Grok 配置 =====
GROK_API_KEY=your-grok-key-here
GROK_BASE_URL=https://api.x.ai/v1
GROK_MODEL=grok-2

# ===== DeepSeek 配置 =====
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

---

## 🔗 相关资源

- [OpenAI API 文档](https://platform.openai.com/docs)
- [Grok API 文档](https://x.ai/api)
- [DeepSeek API 文档](https://api-docs.deepseek.com)

---

**最后更新**: 2026-03-25  
**版本**: 2.1
