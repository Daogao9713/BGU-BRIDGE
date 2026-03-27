@echo off
setlocal enabledelayedexpansion
title Roxy QQ Bridge v2.1 - DeepSeek + Grok 双轨模式
color 0b

:: 强制切换代码页为 65001 (UTF-8) 以防乱码
chcp 65001 >nul

:menu
cls
echo ======================================================
echo           Roxy v2.1 - 决策引擎选择
echo ======================================================
echo.
echo 请选择主决策引擎 (LLM):
echo.
echo   1) DeepSeek ★ 推荐 (稳定+快速)
echo   2) OpenAI / ChatGPT
echo   3) Grok (XAI)
echo   4) Gemini (Google)
echo.
echo ======================================================
echo.

set /p choice="请输入选择 (1-4, 默认 1): "

:: 如果不输入，默认为 1
if "!choice!"=="" set "choice=1"

:: 去除可能的空格
set "choice=!choice: =!"

if "!choice!"=="1" (
    set "LLM_PROVIDER=deepseek"
    set "provider_name=DeepSeek"
) else if "!choice!"=="2" (
    set "LLM_PROVIDER=openai"
    set "provider_name=OpenAI"
) else if "!choice!"=="3" (
    set "LLM_PROVIDER=grok"
    set "provider_name=Grok"
) else if "!choice!"=="4" (
    set "LLM_PROVIDER=gemini"
    set "provider_name=Gemini"
) else (
    echo.
    echo [ERROR] 无效选择，请重试...
    pause
    goto menu
)

:refine_menu
cls
echo ======================================================
echo           Roxy v2.1 - 方案选择
echo ======================================================
echo.
echo 选中的决策引擎: %provider_name%
echo.
echo 是否启用 Grok 润色层? (方案 B - 最灵活)
echo.
echo   方案 A: 纯 %provider_name% (推荐首选)
echo           ✓ 稳定、快速、低成本
echo           ✗ 文案风格一般
echo.
echo   方案 B: %provider_name% + Grok 双轨 (最灵活)
echo           ✓ 决策稳定 + 文案有趣
echo           ✓ 精确控制、个性化强
echo           ✗ 需要 Grok API Key
echo           ✗ 延迟较高 (多一层 API)
echo.
echo ======================================================
echo.

set /p enable_grok="启用 Grok 润色? (y/n, 默认 n): "

if "!enable_grok!"=="" set "enable_grok=n"
set "enable_grok=!enable_grok: =!"

if /i "!enable_grok!"=="y" (
    set "REFINE_WITH_GROK=true"
    echo.
    echo [INFO] 已启用 Grok 润色层
    echo [INFO] 确保你的环境变量中设置了 GROK_API_KEY
) else (
    set "REFINE_WITH_GROK=false"
    echo.
    echo [INFO] 使用纯 %provider_name% 模式 (方案 A)
)

:startup
echo.
echo ======================================================
echo [INFO] 启动配置：
echo   - 主决策引擎: %provider_name%
echo   - Grok 润色: %REFINE_WITH_GROK%
echo   - 监听地址: http://127.0.0.1:9000
echo ======================================================
echo.
echo [INFO] 进入项目目录...
cd /d E:\Project\bgu-qq-bridge

if not exist .venv (
    echo [ERROR] 未找到 .venv! 请检查虚拟环境是否已创建。
    echo [HINT] 运行: python -m venv .venv
    pause
    exit
)

echo [INFO] 激活虚拟环境...
call .venv\Scripts\activate

if !errorlevel! neq 0 (
    echo [ERROR] 虚拟环境激活失败!
    pause
    exit
)

echo.
echo [INFO] 正在启动 Roxy Bridge...
echo [INFO] 按 Ctrl+C 停止服务
echo.

:: 导出环境变量并启动
set "LLM_PROVIDER=!LLM_PROVIDER!"
set "REFINE_WITH_GROK=!REFINE_WITH_GROK!"

python -m uvicorn src.app:app --host 127.0.0.1 --port 9000 --reload

pause