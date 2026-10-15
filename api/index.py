import os
import re
import json
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = FastAPI()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "YOUR_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "YOUR_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 載入 1 分 K 對應歷史資料
json_path = os.path.join(os.path.dirname(__file__), "paired_1min_history.json")
if os.path.exists(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        PAIRED_DATA = json.load(f)
else:
    PAIRED_DATA = [
        {"date": "2026-10-07", "time": "09:00", "etf_close": 13.51, "tx_close": 49979.0}
    ]

def query_etf_to_tx(target_etf: float):
    matched = [d for d in PAIRED_DATA if abs(d["etf_close"] - target_etf) / target_etf <= 0.005]
    max_etf = max(d["etf_close"] for d in PAIRED_DATA)
    min_etf = min(d["etf_close"] for d in PAIRED_DATA)
    
    if matched:
        latest = max(matched, key=lambda x: f"{x['date']} {x['time']}")
        return (
            f"📊 【00685L 對應台指期 (1分K)】\n"
            f"輸入 00685L：{target_etf}\n"
            f"對應台指期點數：{latest['tx_close']}\n"
            f"時間：{latest['date']} {latest['time']}"
        )
    elif target_etf > max_etf:
        latest_max = max(PAIRED_DATA, key=lambda x: x["etf_close"])
        estimated_tx = latest_max["tx_close"] * (target_etf / latest_max["etf_close"])
        return (
            f"🚀 【00685L 超過歷史範圍】\n"
            f"輸入點數 {target_etf} 不在歷史範圍\n"
            f"預估台指期為：{estimated_tx:.1f} 點"
        )
    else:
        return f"💡 輸入值 {target_etf} 低於歷史區間下限 ({min_etf})。"

def query_tx_to_etf(target_tx: float):
    matched = [d for d in PAIRED_DATA if abs(d["tx_close"] - target_tx) / target_tx <= 0.005]
    max_tx = max(d["tx_close"] for d in PAIRED_DATA)
    min_tx = min(d["tx_close"] for d in PAIRED_DATA)
    
    if matched:
        sorted_matches = sorted(matched, key=lambda x: f"{x['date']} {x['time']}", reverse=True)[:3]
        result_str = f"📊 【台指期對應 00685L (近三筆)】\n輸入台指期：{target_tx}\n"
        for m in sorted_matches:
            result_str += f"• 00685L: {m['etf_close']} ({m['date']} {m['time']})\n"
        return result_str.strip()
    elif target_tx > max_tx:
        latest_max = max(PAIRED_DATA, key=lambda x: x["tx_close"])
        estimated_etf = latest_max["etf_close"] * (target_tx / latest_max["tx_close"])
        return (
            f"🚀 【台指期超過歷史範圍】\n"
            f"輸入點數 {target_tx} 不在歷史範圍\n"
            f"預估 00685L 為：{estimated_etf:.2f}"
        )
    else:
        return f"💡 輸入點數 {target_tx} 低於歷史區間下限 ({min_tx})。"

@app.post("/api/index")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature.")
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip().lower()
    # 支援 c txf 與 c 685l 格式（允許中間有空格或直接緊接數字）
    match = re.search(r'c\s*(txf|685l)\s*([0-9.]+)', text)
    if not match:
        reply_text = "指令格式錯誤。\n請輸入例如：\n• c txf48750\n• c 685l13.5"
    else:
        raw_type = match.group(1)
        target_val = float(match.group(2))
        
        if "685l" in raw_type:
            reply_text = query_etf_to_tx(target_val)
        else:
            reply_text = query_tx_to_etf(target_val)
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
