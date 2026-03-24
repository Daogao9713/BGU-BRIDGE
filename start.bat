# 1. 创建梗图目录并放入图片
mkdir -p ./memes
# 放入: sneer.jpg, slap_table.jpg, speechless.jpg, smug.jpg, cold_stare.jpg

# 2. 安装新依赖
pip install pillow

# 3. 启动服务
uvicorn app:app --host 0.0.0.0 --port 9000 --reload

# 4. 发送消息测试
# @机器人 "你好呀" → 应该收到语音或文字回复

# 1. 安装依赖
pip install -r requirements.txt  # 自动加入 pydantic>=2.0

# 2. 创建必要目录
mkdir -p logs

# 3. 启动服务
uvicorn app:app --port 9000 --reload

# 4. 查看日志
tail -f logs/action.log      # 看执行结果和降级链
tail -f logs/decision.log    # 看 LLM 决策
tail -f logs/emotion.log     # 看情绪变化