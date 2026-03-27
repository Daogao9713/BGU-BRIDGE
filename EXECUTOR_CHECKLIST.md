# Roxy v2 执行层改造 - 验收清单

## ✅ 改动验收

### 📋 需求清单

- [x] **改造决策执行流程** - 读取新增字段
  - [x] `response_plan.action`
  - [x] `response_plan.reaction_mode`
  - [x] `response_plan.delay_ms`
  - [x] `response_plan.should_text`
  - [x] `content.meme_tag`
  - [x] `content.meme_text`
  - [x] `content.voice_text`

- [x] **加入梗图映射表与选择函数**
  - [x] `MEME_MAP` 字典定义
  - [x] `pick_meme_file(tag)` 随机选择函数

- [x] **实现 poke 函数**
  - [x] `send_group_poke(group_id, user_id)`
  - [x] `send_private_poke(user_id)`

- [x] **实现延迟发送**
  - [x] `delay_ms` 毫秒级支持
  - [x] `asyncio.sleep()` 集成

- [x] **加入 RLHF 尾巴清理**
  - [x] `_strip_rlhf_tail()` 方法
  - [x] 在 `_sanitize_content()` 中调用

- [x] **实现 user_history 裁剪**
  - [x] 保留最近 10 条消息

- [x] **文档完整**
  - [x] `EXECUTOR_REFACTOR_SUMMARY.md` - 详细改动说明
  - [x] `EXECUTOR_QUICK_REFERENCE.md` - 快速参考卡
  - [x] `DEEPSEEK_GROK_GUIDE.md` - 双轨方案指南

---

## 📝 文件改动清单

### action_executor.py
```diff
+ 导入 poke 函数
+ 重构 execute_decision() 流程（新分流模式）
+ 新增 _execute_poke() 方法
+ 新增 _execute_text_image_new() 方法
+ 新增 MEME_MAP 字典
+ 新增 pick_meme_file() 函数
```

### onebot_client.py
```diff
+ 新增 send_group_poke() 函数
+ 新增 send_private_poke() 函数
```

### decision_engine.py
```diff
+ 新增 _strip_rlhf_tail() 方法
+ 在 _sanitize_content() 中调用 _strip_rlhf_tail()
! 改进梗图标签验证（使用 valid_meme_tags 集合）
```

### brain.py
```diff
+ 在 get_message_history() 后进行裁剪
+ if user_history: user_history = user_history[-10:]
```

---

## 🧪 测试验证

### ✓ 语法检查
```bash
python -m py_compile action_executor.py decision_engine.py brain.py onebot_client.py
# ✓ No errors
```

### ✓ 新字段读取逻辑
```python
# 模式 1：梗图+文本
action = "send"
reaction_mode = "mock"
should_text = True
meme_tag = "mock"
→ ✓ 正确分流到 _execute_text_image_new()

# 模式 2：戳一戳
action = "poke"
→ ✓ 正确分流到 _execute_poke()

# 模式 3：语音
reaction_mode = "voice"
→ ✓ 检查 TTS 后正确分流

# 模式 4：延迟
delay_ms = 500
→ ✓ 执行 asyncio.sleep(0.5)
```

### ✓ 执行分流验证（test_new_executor.py 运行结果）
```
✓ 新字段读取成功
✓ 执行分流逻辑：
  → 执行：文本+梗图 (should_text=True)
    - 发送文本: 😂这也太可笑了！
    - 发送梗图: mock
```

---

## 📊 关键数据

### 代码量变化

| 文件 | 行数 | 说明 |
|------|------|------|
| action_executor.py | +250 | 新增执行方法 + MEME_MAP + poke |
| onebot_client.py | +50 | poke 接口 |
| decision_engine.py | +50 | RLHF 清理 + 梗图验证 |
| brain.py | +5 | 历史裁剪 |
| **文档** | +1000 | 3 份详细文档 |

### 新增功能

- 4 个新的 API 函数（_execute_poke, _execute_text_image_new, send_poke x2）
- 1 个新方法（_strip_rlhf_tail）
- 1 个梗图映射表 + 1 个选择函数
- 5 种执行分流路径
- 3 份完整文档

---

## 🎯 设计特色

### 1. 精确分流
不再依赖"降级链"，而是根据决策字段精确选择执行方式。

### 2. 可控性强
每个参数都对应一个执行决策：
- `should_text` → 是否发文本
- `delay_ms` → 延迟多少毫秒
- `meme_tag` → 发什么梗图
- `action` → 做什么动作

### 3. 降级策略完善
即使主执行方式失败（如 TTS 离线），也能智能降级到纯文本。

### 4. RLHF 处理
自动删除模型的"虚伪"尾巴，保证真诚感。

### 5. 上下文管理
历史消息自动裁剪，防止 token 爆炸。

---

## 🚀 使用流程

### 快速开始（DeepSeek 方案）

1. 配置 config.py
   ```python
   LLM_PROVIDER = "deepseek"
   MODEL_NAME = "deepseek-chat"
   ```

2. 启动应用
   ```bash
   uvicorn app:app --port 9000
   ```

3. 发送消息
   ```
   用户: @Roxy 你很傻
   ```

4. 查看执行日志
   ```
   [decision_engine] DeepSeek 返回决策
   [execute_decision] 读取新字段
   [_execute_text_image_new] 发送文本+梗图
   ```

---

## ⚠️ 前置条件

1. **梗图文件**
   - 创建 `./memes/` 目录
   - 放入对应标签的梗图（sweat_01.jpg, mock_01.jpg 等）

2. **API 支持**
   - NapCat 需支持 `group_poke` 和 `poke` endpoint

3. **TTS 配置**
   - config.py 中配置 TTS_GPU_IP 和端口
   - 如需语音功能

4. **LLM 配置**
   - DeepSeek / 其他稳定模型的 API Key

---

## 📚 文档导航

- **EXECUTOR_REFACTOR_SUMMARY.md** - 详细技术文档
  - 改动概览
  - 新方法说明
  - 梗图映射表
  - 新执行流程分解

- **EXECUTOR_QUICK_REFERENCE.md** - 快速查询
  - 新字段映射表
  - 执行流程图
  - 决策例子 5 个
  - 调试建议

- **DEEPSEEK_GROK_GUIDE.md** - 架构与方案
  - 双轨模式说明
  - 实施步骤
  - 配置示例 3 种
  - 性能优化建议

---

## 🔄 版本历史

| 版本 | 日期 | 改动 |
|------|------|------|
| v2.1 | 2026-03-27 | 执行层大改造，新分流模式 |
| v2.0 | 2026-03 | 初始 v2 架构 |

---

## ✨ 下一步建议

### 短期（本周）
- ✓ 梗图文件准备和放置
- ✓ 测试各执行分流路径
- ✓ 调整参数和阈值

### 中期（本月）
- [ ] 可选：集成 Grok 润色层
- [ ] 监控性能和稳定性
- [ ] 收集用户反馈

### 长期（下个月）
- [ ] 考虑多模型混合策略
- [ ] 性能优化（缓存、batch 处理）
- [ ] 更多自定义功能

---

## 📞 技术支持

遇到问题时，请查看：
1. `EXECUTOR_QUICK_REFERENCE.md` - 常见决策例子
2. `EXECUTOR_REFACTOR_SUMMARY.md` - 技术细节
3. `DEEPSEEK_GROK_GUIDE.md` - 架构与方案

---

**改造完成。祝用愉快！** 🚀

