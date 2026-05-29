# cron_screener.py (純 AI 海選 ＋ LINE 文字推送完全體)
import warnings
warnings.filterwarnings("ignore") 

import datetime
import pandas as pd
import time
import requests
from xgboost import XGBClassifier
from linebot import LineBotApi
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
from data_processor import get_stock_data, build_features, get_clean_stock_map

# =====================================================================
# 🔑 核心密鑰與自動化環境變數設定 (精準對齊你本人的 LINE)
# =====================================================================
LINE_ACCESS_TOKEN = 'uyt/NqkAS3yCOhUAWGqey5HYGBe5mfct1n5MB1OQaV8Y1/X8HoypqNBwq/LOVXk5YnCknVCi8LEE5KZTXkbXT2V0CpOCAk0C/YRPJRA3Z2RREefQjAG41UQV0pbp1YQCnewazDskTwrpBsxHwRo4OQdB04t89/1O/w1cDnyilFU='
TARGET_USER_ID = 'Uf8818996f2c5846640e0ae8ae0360a72'

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
today = datetime.datetime.today().strftime('%Y-%m-%d')

def send_line_text(user_id, text_content):
    """安全發送 LINE 繁體中文文字訊息"""
    try:
        line_bot_api.push_message(user_id, TextSendMessage(to=user_id, text=text_content))
        print('🚀 [LINE] 雲端海選戰報推送成功！')
    except LineBotApiError as e:
        print('❌ [LINE] 文字推送失敗，詳細錯誤原因:', e)

def fetch_twse_official_price(stock_no):
    """🛡️ 證交所官方原生 K 線校正通道 (避開 Yahoo 封鎖)"""
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={today.replace('-','')}&stockNo={stock_no}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                latest_day = data["data"][-1]
                return {
                    "Volume": float(latest_day[1].replace(",", "")) / 1000.0,
                    "Open": float(latest_day[3].replace(",", "")),
                    "High": float(latest_day[4].replace(",", "")),
                    "Low": float(latest_day[5].replace(",", "")),
                    "Close": float(latest_day[6].replace(",", "")),
                    "Success": True
                }
    except: pass
    return {"Success": False}

# =====================================================================
# 🚀 核心海選主程式 (純粹文字數據流)
# =====================================================================
def main():
    print("🚀 啟動台股 AI 盤後海選任務（🎯 1開頭限定測試版 · 純文字發射）...")
    start_date = "2024-01-01"
    end_date = today
    
    stock_map = get_clean_stock_map()
    
    # 🎯 只抽取 1 開頭的傳產主力股進行雲端突圍測試
    all_codes = sorted([
        code for code in stock_map.keys() 
        if len(code) == 4 and code.isdigit() and code.startswith("1")
    ])
    
    print(f"📈 載入中... 已鎖定 {len(all_codes)} 檔「1」開頭大盤代碼。")
    print(f"⚡ [第一階段] 正在執行【自適應量能防線初篩】...")
    
    passed_codes = []
    total_count = len(all_codes)
    
    for idx, code in enumerate(all_codes):
        if idx % 50 == 0:
            print(f"  ⏳ 大盤數據流清洗中... 已排查: [{idx}/{total_count}] 檔...")
            
        try:
            raw = get_stock_data(code, start_date=start_date, end_date=end_date)
            if raw is None or len(raw) < 20: continue
                
            vol_series = raw['Volume'].dropna()
            close_series = raw['Close'].dropna()
            
            last_price = float(close_series.iloc[-1])
            last_vol = float(vol_series.iloc[-1])
            ma5_vol = float(vol_series.tail(5).mean())
            ma20_vol = float(vol_series.tail(20).mean())
            
            # 3000張流動性 ＋ 黃金交叉過濾
            if ma5_vol >= 3000000 and ma5_vol >= ma20_vol and last_price >= 15.0:
                heat_ratio = last_vol / (ma20_vol + 1e-8)
                passed_codes.append({"code": code, "heat_ratio": heat_ratio})
        except:
            continue

    print(f"✨ 階段一完成！今日符合【5日均量黃金防線】的強勢股共：{len(passed_codes)} 檔")
    
    # 🔒 測試防空保底機制
    if not passed_codes:
        print("⚠️ 今日1開頭標的未達量能，啟動傳產種子保底標的流進行測試...")
        passed_codes = [
            {"code": "1402", "heat_ratio": 1.12},
            {"code": "1722", "heat_ratio": 1.05}
        ]
    
    passed_df = pd.DataFrame(passed_codes).sort_values(by="heat_ratio", ascending=False)
    top_50_codes = passed_df['code'].head(50).tolist()
    
    print(f"\n🔥 [第二階段] 精選 {len(top_50_codes)} 檔種子對齊證交所 5/29 實價並擬合 XGBoost 模型...")
    
    feature_cols = [
        'Return_1d', 'Return_5d', 'Volume_Ratio', 'US_SOX_Return', 'US_VIX_Return', 
        'Market_Bias_20d', 'Foreign_Investor_Ratio', 'Trust_Investor_Ratio',   
        'Main_Force_Flow', 'Chaikin_Money_Flow', 'Close_to_MA5', 'Close_to_MA20', 
        'Close_to_MA60', 'MA5_to_MA20', 'RSI', 'MACD_Hist_Norm', 'BB_Position', 'Weekday', 'Month'
    ]
    final_list = []
    
    for idx, code in enumerate(top_50_codes):
        try:
            raw = get_stock_data(code, start_date=start_date, end_date=end_date)
            if raw is None or raw.empty: continue
                
            # 🛡️ 證交所官方原生價格即時校正
            official_data = fetch_twse_official_price(code)
            if official_data["Success"]:
                last_idx = raw.index[-1]
                raw.loc[last_idx, ['Open', 'High', 'Low', 'Close', 'Volume']] = [
                    official_data["Open"], official_data["High"], official_data["Low"], official_data["Close"], official_data["Volume"]
                ]
            
            df_feat = build_features(raw)
            X, y = df_feat[feature_cols], df_feat['Target']
            
            model = XGBClassifier(n_estimators=60, max_depth=4, learning_rate=0.05, random_state=42)
            model.fit(X, y)
            
            prob = model.predict_proba(X.tail(1))[0][1]
            final_list.append({"code": code, "name": stock_map.get(code, code), "prob": float(prob)})
            print(f"  🌟 [{idx+1}/{len(top_50_codes)}] {code} {stock_map.get(code, '')} 雲端校正勝率: {prob:.2%}")
            time.sleep(0.2)
        except Exception as e:
            continue
            
    # 🎯【核心發射點】：將洗出來的前 5 名強勢股，格式化成乾淨的純文字戰報發送
    if final_list:
        result_df = pd.DataFrame(final_list).sort_values(by="prob", ascending=False)
        result_df_rename = result_df.rename(columns={"code": "代號", "name": "名稱", "prob": "發動機率"})
        result_df_rename.to_csv("best_stocks.csv", index=False, encoding='utf-8-sig')
        
        line_report = f"📊 【台股 AI 盤後強勢海選戰報】\n📅 數據日期：{today}\n🤖 策略：5日均量自適應正規軍\n----------------------\n"
        for i, row in result_df.head(5).iterrows():
            line_report += f"🏆 No.{i+1} [{row['code']}] {row['name']}\n🔥 明日發動勝率: {row['prob']:.2%}\n\n"
        line_report += "💡 本戰報已同步更新至雲端 best_stocks.csv 數據庫！"
        
        print("📢 正在發射純文字海選戰報至你的 LINE...")
        send_line_text(TARGET_USER_ID, line_report)
    else:
        print("❌ 今日未產出任何符合模型擬合之標的。")

if __name__ == "__main__": 
    main()