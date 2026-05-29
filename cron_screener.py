# cron_screener.py (🔥 股名完美縫合·全大盤純 yfinance 突圍終極完全體)
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
from data_processor import get_stock_data, build_features

# =====================================================================
# 🔑 核心密鑰與自動化環境變數設定
# =====================================================================
LINE_ACCESS_TOKEN = 'uyt/NqkAS3yCOhUAWGqey5HYGBe5mfct1n5MB1OQaV8Y1/X8HoypqNBwq/LOVXk5YnCknVCi8LEE5KZTXkbXT2V0CpOCAk0C/YRPJRA3Z2RREefQjAG41UQV0pbp1YQCnewazDskTwrpBsxHwRo4OQdB04t89/1O/w1cDnyilFU='
TARGET_USER_ID = 'Uf8818996f2c5846640e0ae8ae0360a72'

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
today = datetime.datetime.today().strftime('%Y-%m-%d')

def send_line_text(user_id, text_content):
    try:
        line_bot_api.push_message(user_id, TextSendMessage(to=user_id, text=text_content))
        print('🚀 [LINE] 終極完全體戰報推送成功！')
    except LineBotApiError as e:
        print('❌ [LINE] 文字推送失敗:', e)

def get_all_taiwan_stock_codes_with_names():
    """🛡️ 鋼鐵查字典大腦：0秒拉取官方不鎖IP的開放名冊，把【股名】與【股號】完美綁定"""
    stock_dict = {}
    stock_list = []
    
    # 🎯 核心補完：利用不擋海外 IP 的上市公司基本資料開放 API 來抓繁體中文名字
    try:
        url_names = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
        res_n = requests.get(url_names, timeout=10)
        if res_n.status_code == 200:
            for row in res_n.json():
                code = row.get("公司代號", "").strip()
                name = row.get("公司簡稱", "").strip()
                if len(code) == 4 and code.isdigit():
                    stock_dict[code] = name
    except:
        pass

    # 1. 抓取上市合規活股
    try:
        url_tw = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        res = requests.get(url_tw, timeout=10)
        if res.status_code == 200:
            for row in res.json():
                code = row.get("證券代號", "").strip()
                if len(code) == 4 and code.isdigit():
                    name = stock_dict.get(code, row.get("證券名稱", code).strip())
                    stock_list.append({"code": code, "name": name, "ticker": f"{code}.TW"})
    except:
        pass

    # 2. 抓取上櫃合規活股
    try:
        url_two = "https://openapi.tpex.org.tw/v1/opendata/TPExDailyOfficialPrice"
        res = requests.get(url_two, timeout=10)
        if res.status_code == 200:
            for row in res.json():
                code = row.get("SecuritiesCompanyCode", "").strip()
                name = row.get("CompanyName", code).strip() # 上櫃 API 通常內建中文名字
                if len(code) == 4 and code.isdigit():
                    stock_list.append({"code": code, "name": name, "ticker": f"{code}.TWO"})
    except:
        pass

    # 備援通道
    if not stock_list:
        core_fallback = {"2330": "台積電", "2317": "鴻海", "2454": "聯發科", "1503": "士電", "2409": "友達"}
        for c, n in core_fallback.items():
            stock_list.append({"code": c, "name": n, "ticker": f"{c}.TW"})
            
    df_list = pd.DataFrame(stock_list).drop_duplicates(subset=['code']).sort_values(by="code")
    return df_list.to_dict(orient="records")

# =====================================================================
# 🚀 核心海選主程式 (全台股高效實行完全體)
# =====================================================================
def main():
    print("🚀 啟動台股 AI 盤後海選任務（🔥 全大盤純 yfinance 1,980 檔終極完全體）...")
    start_date = "2024-01-01"
    end_date = today
    
    print("📈 正在透過開放數據通道載入 1980 檔全台股雷達（中文名稱自動對齊）...")
    active_stocks = get_all_taiwan_stock_codes_with_names()
    
    # 建立一個快速反查中文名稱的記憶體字典
    name_lookup = {s["code"]: s["name"] for s in active_stocks}
    print(f"✅ 載入成功！當前大盤真正合規活股共：{len(active_stocks)} 檔（股名已綁定）。")
    
    print(f"⚡ [第一階段] 正在海外微軟機房執行【自適應量能防線初篩】...")
    passed_codes = []
    total_count = len(active_stocks)
    
    for idx, stock in enumerate(active_stocks):
        code = stock["code"]
        ticker = stock["ticker"]
        
        try:
            raw = get_stock_data(ticker, start_date=(pd.to_datetime(today) - pd.Timedelta(days=30)).strftime('%Y-%m-%d'), end_date=today)
            if raw is None or len(raw) < 5: continue
                
            vol_series = raw['Volume'].dropna()
            close_series = raw['Close'].dropna()
            
            last_price = float(close_series.iloc[-1])
            last_vol = float(vol_series.iloc[-1])
            ma5_vol = float(vol_series.tail(5).mean())
            ma20_vol = float(vol_series.tail(20).mean())
            
            if ma5_vol >= 3000000 and ma5_vol >= ma20_vol and last_price >= 15.0:
                heat_ratio = last_vol / (ma20_vol + 1e-8)
                passed_codes.append({"ticker": ticker, "code": code, "heat_ratio": heat_ratio})
        except:
            continue

    print(f"\n✨ 階段一完成！全大盤符合【5日均量黃金防線】的爆量強勢股共：{len(passed_codes)} 檔")
    if not passed_codes:
        print("⚠️ 今日全大盤未達量能標的，全 yf 任務結束。")
        return
    
    passed_df = pd.DataFrame(passed_codes).sort_values(by="heat_ratio", ascending=False)
    top_50 = passed_df.head(50)
    
    print(f"\n🔥 [第二階段] 精選 {len(top_50)} 檔進入模型擬合，現場計算 XGBoost 特徵工程...")
    
    feature_cols = [
        'Return_1d', 'Return_5d', 'Volume_Ratio', 'US_SOX_Return', 'US_VIX_Return', 
        'Market_Bias_20d', 'Foreign_Investor_Ratio', 'Trust_Investor_Ratio',   
        'Main_Force_Flow', 'Chaikin_Money_Flow', 'Close_to_MA5', 'Close_to_MA20', 
        'Close_to_MA60', 'MA5_to_MA20', 'RSI', 'MACD_Hist_Norm', 'BB_Position', 'Weekday', 'Month'
    ]
    final_list = []
    
    for idx, row in enumerate(top_50.itertuples()):
        try:
            raw = get_stock_data(row.ticker, start_date=start_date, end_date=end_date)
            if raw is None or raw.empty: continue
            
            df_feat = build_features(raw)
            X, y = df_feat[feature_cols], df_feat['Target']
            
            model = XGBClassifier(n_estimators=60, max_depth=4, learning_rate=0.05, random_state=42)
            model.fit(X, y)
            
            prob = model.predict_proba(X.tail(1))[0][1]
            final_list.append({"code": row.code, "name": name_lookup.get(row.code, row.code), "prob": float(prob)})
        except:
            continue
            
    if final_list:
        result_df = pd.DataFrame(final_list).sort_values(by="prob", ascending=False).reset_index(drop=True)
        result_df.to_csv("best_stocks.csv", index=False, encoding='utf-8-sig')
        
        line_report = f"📊 【台股 AI 全大盤海選戰報 · 終極版】\n📅 數據日期：{today}\n🤖 策略：1980檔純 yfinance 突圍完全體\n----------------------\n"
        for i, row in result_df.head(5).iterrows():
            # 🎯 終極修正點：把 [代號] ＋ 中文股名 完美整合在一起發送！
            line_report += f"🏆 No.{i+1} [{row['code']}] {row['name']}\n🔥 明日發動勝率: {row['prob']:.2%}\n\n"
        line_report += "💡 本數據由海外微軟機房現撈現算，股名對齊通關！"
        
        print("📢 正在發射終極全大盤戰報至 LINE...")
        send_line_text(TARGET_USER_ID, line_report)

if __name__ == "__main__": 
    main()