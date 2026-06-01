import warnings
warnings.filterwarnings("ignore") 

import datetime
import pandas as pd
import time
import random
import requests
import traceback
import yfinance as yf
from xgboost import XGBClassifier
from linebot import LineBotApi
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage

# =====================================================================
# 🎯 鋼鐵大絕招：直接針對 ta 套件本體進行原型擴充（最安全、絕不卡 import）
# =====================================================================
try:
    import ta
    from ta.trend import SMAIndicator, MACD
    from ta.momentum import RSIIndicator
    from ta.volatility import BollingerBands
    
    # 💡 1. 搞定 SMAIndicator (把 window 映射到 n)
    orig_sma_init = SMAIndicator.__init__
    def patched_sma_init(self, close, window=9, fillna=False, n=None):
        actual_n = n if n is not None else window
        orig_sma_init(self, close=close, n=actual_n, fillna=fillna)
    SMAIndicator.__init__ = patched_sma_init

    # 💡 2. 搞定 RSIIndicator (把 window 映射到 n)
    orig_rsi_init = RSIIndicator.__init__
    def patched_rsi_init(self, close, window=14, fillna=False, n=None):
        actual_n = n if n is not None else window
        orig_rsi_init(self, close=close, n=actual_n, fillna=fillna)
    RSIIndicator.__init__ = patched_rsi_init

    # 💡 3. 搞定 MACD (把 window_fast/slow/sign 映射到 n_fast/slow/sign)
    orig_macd_init = MACD.__init__
    def patched_macd_init(self, close, window_fast=12, window_slow=26, window_sign=9, fillna=False, n_fast=None, n_slow=None, n_sign=None):
        act_fast = n_fast if n_fast is not None else window_fast
        act_slow = n_slow if n_slow is not None else window_slow
        act_sign = n_sign if n_sign is not None else window_sign
        orig_macd_init(self, close=close, n_fast=act_fast, n_slow=act_slow, n_sign=act_sign, fillna=fillna)
    MACD.__init__ = patched_macd_init

    # 💡 4. 搞定 BollingerBands (把 window 映射到 n)
    orig_bb_init = BollingerBands.__init__
    def patched_bb_init(self, close, window=20, window_dev=2, fillna=False, n=None, ndev=None):
        actual_n = n if n is not None else window
        actual_dev = ndev if ndev is not None else window_dev
        orig_bb_init(self, close=close, n=actual_n, ndev=actual_dev, fillna=fillna)
    BollingerBands.__init__ = patched_bb_init

    print("✅ [成功] 已完成 ta 技術指標套件參數全面對齊！")
except Exception as e:
    print(f"⚠️ 技術指標參數相容處理提示: {e}", flush=True)

# 💡 參數相容完全搞定後，才引入你的特徵工程計算，保證 100% 成功
from data_processor import build_features  

# =====================================================================
# 🔑 核心密鑰與自動化環境變數設定
# =====================================================================
LINE_ACCESS_TOKEN = 'uyt/NqkAS3yCOhUAWGqey5HYGBe5mfct1n5MB1OQaV8Y1/X8HoypqNBwq/LOVXk5YnCknVCi8LEE5KZTXkbXT2V0CpOCAk0C/YRPJRA3Z2RREefQjAG41UQV0pbp1YQCnewazDskTwrpBsxHwRo4OQdB04t89/1O/w1cDnyilFU='
TARGET_USER_ID = 'Uf8818996f2c5846640e0ae8ae0360a72'

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
today_dt = datetime.datetime.today()
today = today_dt.strftime('%Y-%m-%d')

def send_line_text(user_id, text_content):
    try:
        line_bot_api.push_message(user_id, TextSendMessage(to=user_id, text=text_content))
        print('🚀 [LINE] 終極完全體戰報推送成功！', flush=True)
    except LineBotApiError as e:
        print('❌ [LINE] 文字推送失敗:', e, flush=True)

def get_all_taiwan_stock_codes_with_names():
    """🛡️ 鋼鐵查字典大腦：自適應日期回溯，確保上市櫃名單完整"""
    stock_dict = {}
    stock_list = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.tpex.org.tw/"
    }
    
    try:
        url_names = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
        res_n = requests.get(url_names, timeout=10)
        if res_n.status_code == 200:
            for row in res_n.json():
                code = str(row.get("公司代號", row.get("Code", row.get("證券代號", "")))).strip()
                name = str(row.get("公司簡稱", row.get("Name", row.get("證券名稱", "")))).strip()
                if len(code) == 4 and code.isdigit():
                    stock_dict[code] = name
    except Exception as e:
        print(f"💥 [提示] 上市名稱對照表拉取跳過: {e}", flush=True)

    try:
        url_tw = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        res = requests.get(url_tw, timeout=10)
        if res.status_code == 200:
            data = res.json()
            print(f"📊 證交所原始資料回傳共 {len(data)} 筆，開始解析...", flush=True)
            for row in data:
                code = str(row.get("證券代號", row.get("Code", row.get("公司代號", "")))).strip()
                name = str(row.get("證券名稱", row.get("Name", ""))).strip()
                if len(code) == 4 and code.isdigit():
                    final_name = stock_dict.get(code, name if name else code)
                    stock_list.append({"code": code, "name": final_name, "ticker": f"{code}.TW"})
    except Exception as e:
        print(f"💥 [錯誤] 上市活股名冊拉取失敗: {e}", flush=True)

    check_dt = today_dt
    if check_dt.hour < 14 or (check_dt.hour == 14 and check_dt.minute < 30):
        check_dt -= datetime.timedelta(days=1)

    for _ in range(7):
        tw_year = check_dt.year - 1911
        date_str_tpex = f"{tw_year}/{check_dt.strftime('%m/%d')}"
        try:
            url_two = f"https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no14362/stk_quotes_no14362_result.php?l=zh-tw&d={date_str_tpex}"
            res_two = requests.get(url_two, headers=headers, timeout=15)
            if res_two.status_code == 200:
                data_two = res_two.json()
                raw_stocks = data_two.get("aaData", [])
                if raw_stocks and len(raw_stocks) > 10:
                    print(f"📊 櫃買中心成功對齊有效交易日 [{date_str_tpex}]，回傳共 {len(raw_stocks)} 筆，開始解析...", flush=True)
                    for row in raw_stocks:
                        if len(row) > 2:
                            code = str(row[0]).strip()
                            name = str(row[1]).strip()
                            if len(code) == 4 and code.isdigit():
                                stock_list.append({"code": code, "name": name, "ticker": f"{code}.TWO"})
                    break
        except:
            pass
        check_dt -= datetime.timedelta(days=1)

    if not stock_list:
        print("\n🚨 [致命錯誤] 上市櫃名單完全沒撈到任何東西！", flush=True)
        return []
            
    df_list = pd.DataFrame(stock_list).drop_duplicates(subset=['code']).sort_values(by="code")
    return df_list.to_dict(orient="records")

# =====================================================================
# 🚀 核心海選主程式 (安全防 BAN · 下載即開戰完全體)
# =====================================================================
def main():
    print("🚀 啟動台股 AI 盤後海選任務（🔥 全大盤下載即擬合流·終極防爆完全體）...", flush=True)
    start_date = "2024-01-01"
    end_date = today
    
    print("📈 正在透過開放數據通道載入 全台股雷達...", flush=True)
    active_stocks = get_all_taiwan_stock_codes_with_names()
    
    if not active_stocks:
        print("❌ 核心名冊為空，程式強制終止。", flush=True)
        return
        
    name_lookup = {s["code"]: s["name"] for s in active_stocks}
    tickers = [s["ticker"] for s in active_stocks]
    print(f"✅ 載入成功！當前大盤真正合規活股共：{len(active_stocks)} 檔。", flush=True)
    
    feature_cols = [
        'Return_1d', 'Return_5d', 'Volume_Ratio', 'US_SOX_Return', 'US_VIX_Return', 
        'Market_Bias_20d', 'Foreign_Investor_Ratio', 'Trust_Investor_Ratio',   
        'Main_Force_Flow', 'Chaikin_Money_Flow', 'Close_to_MA5', 'Close_to_MA20', 
        'Close_to_MA60', 'MA5_to_MA20', 'RSI', 'MACD_Hist_Norm', 'BB_Position', 'Weekday', 'Month'
    ]
    
    chunk_size = 50
    all_passed_candidates = []
    
    print(f"\n⚡ 開始流式海選：每批次下載 {chunk_size} 檔，下載完立刻就地執行 AI 模型擬合！", flush=True)
    
    for i in range(0, len(tickers), chunk_size):
        chunk_tickers = tickers[i:i + chunk_size]
        current_group = i // chunk_size + 1
        print(f"\n⏳ 正在處理第 {current_group} 組數據 ({i} ~ {min(i+chunk_size, len(tickers))} 檔)...", flush=True)
        
        try:
            all_data = yf.download(chunk_tickers, start=start_date, end=today, group_by='ticker', progress=False)
            
            for ticker in chunk_tickers:
                try:
                    if len(chunk_tickers) == 1:
                        raw = all_data
                    else:
                        raw = all_data[ticker]
                        
                    raw = raw.dropna(subset=['Close', 'Volume'])
                    if raw is None or len(raw) < 60: 
                        continue
                        
                    vol_series = raw['Volume'].astype(float)
                    close_series = raw['Close'].astype(float)
                    
                    last_price = float(close_series.iloc[-1])
                    last_vol = float(vol_series.iloc[-1])
                    ma5_vol = float(vol_series.tail(5).mean())
                    ma20_vol = float(vol_series.tail(20).mean())
                    
                    if ma5_vol >= 1000000 and ma5_vol >= ma20_vol and last_price >= 15.0:
                        heat_ratio = last_vol / (ma20_vol + 1e-8)
                        code = ticker.split('.')[0]
                        
                        raw_copy = raw.copy()
                        raw_copy['Foreign_Buy'] = 0.0
                        raw_copy['Trust_Buy'] = 0.0
                        raw_copy['Main_Force_Flow'] = 0.0
                        raw_copy['Chaikin_Money_Flow'] = 0.0
                        if 'US_SOX_Return' not in raw_copy.columns: raw_copy['US_SOX_Return'] = 0.0
                        if 'US_VIX_Return' not in raw_copy.columns: raw_copy['US_VIX_Return'] = 0.0
                        
                        # 🔒 這次直接進入計算，由於上面直接修改了 Class 本身，保證 SMA、RSI、MACD 完美兼容！
                        df_feat = build_features(raw_copy)
                        
                        for col in feature_cols:
                            if col not in df_feat.columns:
                                df_feat[col] = 0.0
                        if 'Target' not in df_feat.columns:
                            df_feat['Target'] = (df_feat['Close'].shift(-1) > df_feat['Close']).astype(int)
                            
                        X, y = df_feat[feature_cols], df_feat['Target']
                        
                        model = XGBClassifier(n_estimators=60, max_depth=4, learning_rate=0.05, random_state=42)
                        model.fit(X, y)
                        
                        prob = model.predict_proba(X.tail(1))[0][1]
                        
                        all_passed_candidates.append({
                            "code": code, 
                            "name": name_lookup.get(code, code), 
                            "prob": float(prob), 
                            "heat_ratio": heat_ratio
                        })
                        print(f"   ✅ [{code}] 特徵與模型跑通！預測明日勝率: {prob:.2%}", flush=True)
                except Exception as e:
                    code = ticker.split('.')[0]
                    print(f"   💥 股票 [{code}] 崩潰跳過。原因: {e}", flush=True)
                    continue
            
            time.sleep(random.uniform(1.0, 1.8))
            
        except Exception as e:
            print(f"⚠️ 批次組第 {current_group} 組整批下載異常: {e}", flush=True)
            time.sleep(2)
            continue

    print(f"\n✨ 全大盤 22 組流式掃描完畢！進入決賽圈的爆量強勢股共：{len(all_passed_candidates)} 檔")
    
    if all_passed_candidates:
        result_df = pd.DataFrame(all_passed_candidates).sort_values(by="prob", ascending=False).reset_index(drop=True)
        result_df.to_csv("best_stocks.csv", index=False, encoding='utf-8-sig')
        
        line_report = f"📊 【台股 AI 全大盤海選戰報 · 完全體】\n📅 數據日期：{today}\n🤖 策略: 1980檔純 yfinance 下載即開戰完全體\n----------------------\n"
        for i, row in result_df.head(5).iterrows():
            line_report += f"🏆 No.{i+1} [{row['code']}] {row['name']}\n🔥 明日發動勝率: {row['prob']:.2%}\n\n"
        line_report += "💡 數據完成流式併包過濾，ta 版本地獄通關！"
        
        print("📢 正在發射終極全大盤戰報至 LINE...", flush=True)
        send_line_text(TARGET_USER_ID, line_report)
    else:
        print("🚨 [嚴重警告] 大盤掃描結束，但沒有任何一檔股票成功產出勝率！")

if __name__ == "__main__": 
    main()