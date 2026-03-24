# Roxy v2 部署后行动清单

## ✅ 立即验证 (启动后 5 分钟)

```
□ 服务正常启动
  监听: http://0.0.0.0:9000
  
□ 发送测试消息到机器人
  期望: 收到语音或文字回复
  
□ 检查缓存目录
  ./cache/emotion_state.json (应该存在并有内容)
  ./cache/user_profiles.json (应该存在并有内容)
  
□ 查看日志输出
  决策成功: "决策成功: voice"
  情绪分析: "事件分析: praise"
```

## 📊 功能验证 (24 小时内)

```
□ 情绪衰减测试
  - 发送激怒消息让 anger 升高
  - 等待 10 分钟，重新查询情绪
  - 验证 anger 是否下降
  
□ 多种回复测试
  - 发送夸奖 → 期望语音+傲娇
  - 发送骂人 → 期望文字+冷脸
  - 发送重复消息 → 期望冷却或短回复
  
□ 梗图系统验证
  - 激怒机器人 (anger > 60)
  - 期望收到文字+梗图组合
  
□ 用户档案验证
  - 同一个人和陌生人说同样的话
  - 观察反应是否不同
```

## 🎯 性能基准 (首周内)

```
□ 响应延迟测试
  - 记录 10 条消息的回复时间
  - 平均应该在 2-5 秒
  
□ 错误率监控
  - 记录失败的请求数
  - 应该 < 5%
  
□ 情绪稳定性
  - 观察情绪是否在合理范围内
  - anger 不应该超过 90
  - affection 不应该低于 10
```

## 🔧 优化建议 (第一周)

### 如果回复太凶
```python
# 在 config.py 中降低 sharpness
PERSONA_CONFIG["sharpness"] = 0.5  # 从 0.65 改到 0.5

# 或提高 mercy (怜悯心)
PERSONA_CONFIG["mercy"] = 0.6  # 从 0.4 改到 0.6
```

### 如果总是发文字不发语音
```python
# 提高语音倾向
PERSONA_CONFIG["voice_preference"] = 0.85  # 从 0.7 改到 0.85

# 或在 event_mapper.py 中降低 spam_risk 的 anger 增量
INSULT_KEYWORDS = [...]  # 移除不必要的贬低词汇
```

### 如果梗图不行
```
□ 确认 ./memes/ 目录存在
□ 确认有梗图文件（.jpg/.png）2KB+
□ 确认文件名在 action_executor.py 的 MEME_MAP 中
□ 尝试用绝对路径测试 MemeLibrary.create_dynamic_meme()
```

## 📈 数据分析任务 (第一个月)

```
□ 收集统计数据
  - 日均回复消息数
  - 情绪变化分布（histogram）
  - 最常见的事件类型
  
□ 用户行为分析
  - 用户 favorability 分布
  - 高频用户 vs 低频用户 对比
  - 群聊 vs 私聊 的回复差异
  
□ 回复质量评估
  - 主观：回复是否符合性格
  - 定性：收集用户反馈
  - 迭代：根据反馈调整参数
```

## 🎨 个性化调教 (第 2-4 周)

### 第 2 周：调整关键词
```python
# event_mapper.py
# 加入更多领域特定的关键词
PRAISE_KEYWORDS.extend(["优秀", "绝地", "超神", "666666"])
TEASE_KEYWORDS.extend(["逗你玩", "骗你呢", "你信不信"])
```

### 第 3 周：调整决策规则
```python
# 在 decision_engine._build_system_prompt() 中
# 根据实际效果微调阈值：
# "anger < 45" → "anger < 50"
# "fatigue > 70" → "fatigue > 60"
```

### 第 4 周：梗图扩展
```
□ 增加梗图库（5+ 种）
□ 按情绪分类梗图
□ 实验动态生成效果
□ 决定是否接入 SD
```

## 🚨 故障应急方案

### 突发：机器人不回复
```bash
# 1. 检查服务是否还在运行
# 2. 查看日志是否有报错
tail -f app.log

# 3. 强制重启
# Ctrl+C 停止，然后重新启动

# 4. 如果还不行：清除缓存
rm cache/emotion_state.json
rm cache/user_profiles.json

# 5. 重启服务
```

### 突发：一直发语音
```python
# 临时应急方案1：强制改成文字
# 在 action_executor.py 的 execute_decision() 中
if decision.response_plan["mode"] == "voice":
    decision.response_plan["mode"] = "text"  # 临时禁用语音

# 应急方案2：降低 voice_preference
# config.py
PERSONA_CONFIG["voice_preference"] = 0.0
```

### 突发：梗图炸了
```python
# 禁用梗图系统
# 在 action_executor._send_text_and_image() 中
# 直接改为 _send_text()

# 或在决策时禁用
# decision.content["meme_tag"] = None
```

## 📞 需要帮助？

### 问题排查流程
1. 查看 console 日志 (应该很详细)
2. 查看 `cache/emotion_state.json` (是否正常更新)
3. 手工调用 Python API
4. 阅读对应模块的 docstring
5. 查看 ROXY_IMPLEMENTATION.md 的"故障排查"节

### 常见问题
```
Q: 为什么只发文字不发语音？
A: 检查 anger 是否过高，或 affection 过低

Q: 决策很慢（>5秒）？
A: 这是正常的（LLM调用），可以缓存或并发

Q: 梗图不显示？
A: 检查文件路径是否正确，./memes/ 是否有文件

Q: 情绪总是不变？
A: 检查是否定期调用 get_emotion()（衰减需要触发）

Q: 如何让她更傲娇？
A: tsundere_level 改大，或调整 decision_engine 的 prompt
```

## 📅 长期维护计划

```
每周：
  □ 检查错误率趋势
  □ 快速人格调整
  
每月：
  □ 数据分析和报告
  □ 情绪参数优化
  □ 梗图库扩展
  
每季度：
  □ 大规模A/B测试
  □ 新功能评估
  □ 系统架构审查
```

## 🎊 成功标志

- ✨ 用户能明显感受到"她"在生气、开心、傲娇
- 😄 每个群聊的反应都不一样（群体情绪独立）
- 💬 同一个人反复交互，接收方式会变化（学习）
- 🎯 错误率 < 2%，响应时间稳定在 2-3s
- 📊 回复多样化程度明显提升

---

**准备好了吗？让我们让 Roxy 真正活过来吧！** 🚀💕
