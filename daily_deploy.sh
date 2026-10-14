#!/bin/bash

# 確保腳本在專案根目錄執行
cd "$(dirname "$0")"

echo "=== 開始執行每日 Tick 歷史資料轉檔 ==="
python3 build_summary_1min.py

echo "=== 準備同步至 GitHub ==="
git add api/paired_1min_history.json
git commit -m "auto-update paired_1min_history: $(date +%F)"
git push origin main

echo "=== 部署完成！Vercel 將自動更新 LINE Bot 數據 ==="
