@echo off
cd /d "D:\MT5_Bot - Copy"
title BMT Forex Auto Trading System

echo ========================================
echo 🤖 BMT FOREX AUTO TRADING SYSTEM
echo ========================================
echo.

echo 1. Khoi dong Forward Bot (copy tin nhan)...
start "Forward Bot" cmd /k "python forward_bot.py"

timeout /t 5

echo.
echo 2. Khoi dong Trading Bot (vao lenh)...
start "Trading Bot v2" python trading_bot_v2.py

echo.
echo ✅ Da khoi dong tat ca bot!
echo   - Forward Bot: Copy tin nhan tu BMT FOREX
echo   - Trading Bot: Vao lenh tu dong
echo.
echo De dung: Dong tat ca cua so hoac nhan Ctrl+C
pause
