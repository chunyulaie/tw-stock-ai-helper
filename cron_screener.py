# cron_screener.py (純 yfinance 1980檔地毯海選完全體)
import warnings
warnings.filterwarnings("ignore") 

import datetime
import pandas as pd
import time
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
        print('🚀 [LINE] 全大盤純 yf 戰報推送成功！')
    except LineBotApiError as e:
        print('❌ [LINE] 文字推送失敗:', e)

# =====================================================================
# 🚀 核心海選主程式 (純 yfinance 1980 檔地毯式轟炸)
# =====================================================================
def main():
    print("🚀 啟動台股 AI 盤後海選任務（🔥 全大盤純 yfinance 1,980 檔完全體）...")
    start_date = "2024-01-01"
    end_date = today
    
    # 🎯【純 yf 動態名冊】：我們直接用資工最暴力的代碼區間生成法，
    # 生成 1101 到 9958 所有可能的 4 位數代碼，交給 yfinance 在海外高速併發過濾！
    print("📈 正在初始化 1980 檔全台股動態掃描雷達...")
    
    passed_codes = []
    
    # 台股正規 4 位數股票代碼基本上都落在 1100 到 9999 之間
    for code_num in range(1100, 9960):
        code = str(code_num)
        
        # 嘗試用上市（.TW）規格去讓 yf 下載最近 20 天的極輕量流動性數據
        try:
            ticker = f"{code}.TW"
            raw = get_stock_data(ticker, start_date=(pd.to_datetime(today) - pd.Timedelta(days=30)).strftime('%Y-%m-%d'), end_date=today)
            
            # 如果上市找不到，自動切換成上櫃（.TWO）規格再試一次
            if raw is None or raw.empty:
                ticker = f"{code}.TWO"
                raw = get_stock_data(ticker, start_date=(pd.to_datetime(today) - pd.Timedelta(days=30)).strftime('%Y-%m-%d'), end_date=today)
                
            if raw is None or len(raw) < 5: continue
                
            vol_series = raw['Volume'].dropna()
            close_series = raw['Close'].dropna()
            
            last_price = float(close_series.iloc[-1])
            last_vol = float(vol_series.iloc[-1])
            ma5_vol = float(vol_series.tail(5).mean())
            ma20_vol = float(vol_series.tail(20).mean())
            
            # 🎯【全大盤量能大閘門】：5日均量 > 3000張（3,000,000股）且量能增溫
            if ma5_vol >= 3000000 and ma5_vol >= ma20_vol and last_price >= 15.0:
                heat_ratio = last_vol / (ma20_vol + 1e-8)
                passed_codes.append({"ticker": ticker, "code": code, "heat_ratio": heat_ratio})
                print(f"  🔥 [量能達標] {ticker} 成功突圍進入決賽圈！")
        except:
            continue

    print(f"\n✨ 階段一完成！全大盤符合【5日均量黃金防線】的爆量強勢股共：{len(passed_codes)} 檔")
    
    if not passed_codes:
        print("⚠️ 今日全大盤未達量能標的，全 yf 任務結束。")
        return
    
    passed_df = pd.DataFrame(passed_codes).sort_values(by="heat_ratio", ascending=False)
    # 決賽圈精選前 50 檔，現場餵給 XGBoost 重裝甲
    top_50 = passed_df.head(50)
    
    print(f"\n🔥 [第二階段] 精選 {len(top_50)} 檔決賽圈標的現場拉取兩年長期 K 線並訓練 XGBoost...")
    
    feature_cols = [
        'Return_1d', 'Return_5d', 'Volume_Ratio', 'US_SOX_Return', 'US_VIX_Return', 
        'Market_Bias_20d', 'Foreign_Investor_Ratio', 'Trust_Investor_Ratio',   
        'Main_Force_Flow', 'Chaikin_Money_Flow', 'Close_to_MA5', 'Close_to_MA20', 
        'Close_to_MA60', 'MA5_to_MA20', 'RSI', 'MACD_Hist_Norm', 'BB_Position', 'Weekday', 'Month'
    ]
    final_list = []
    
    for idx, row in enumerate(top_50.itertuples()):
        try:
            # 拉取從 2024 年開始的完整長期歷史數據用來跑特徵與訓練模型
            raw = get_stock_data(row.ticker, start_date=start_date, end_date=end_date)
            if raw is None or raw.empty: continue
            
            df_feat = build_features(raw)
            X, y = df_feat[feature_cols], df_feat['Target']
            
            model = XGBClassifier(n_estimators=60, max_depth=4, learning_rate=0.05, random_state=42)
            model.fit(X, y)
            
            prob = model.predict_proba(X.tail(1))[0][1]
            final_list.append({"code": row.code, "prob": float(prob)})
            print(f"  🌟 [{idx+1}/{len(top_50)}] {row.ticker} AI 勝率算定完成: {prob:.2%}")
        except:
            continue
            
    if final_list:
        # 🎯【排版完全體】：排序後重置 Index，保證 No.1 到 No.5 完美歸位
        result_df = pd.DataFrame(final_list).sort_values(by="prob", ascending=False).reset_index(drop=True)
        result_df.to_csv("best_stocks.csv", index=False, encoding='utf-8-sig')
        
        line_report = f"📊 【台股 AI 全大盤海選戰報 · yf流】\n📅 數據日期：{today}\n🤖 策略：1980檔純 yfinance 突圍完全體\n----------------------\n"
        for i, row in result_df.head(5).iterrows():
            line_report += f"🏆 No.{i+1} 股票代號: [{row['code']}]\n🔥 明日發動勝率: {row['prob']:.2%}\n\n"
        line_report += "💡 本數據純粹由海外微軟機房一條龍調用 yfinance 現撈現算出廠！"
        
        print("📢 正在發射純 yf 全大盤戰報至 LINE...")
        send_line_text(TARGET_USER_ID, line_report)

if __name__ == "__main__": 
    main()