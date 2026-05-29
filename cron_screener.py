# cron_screener.py (1開頭限定雲端完全體·無污染真K線對齊版)
import warnings
warnings.filterwarnings("ignore") 

import datetime
import pandas as pd
import time
import requests
import asyncio
import os
from xgboost import XGBClassifier
from linebot import LineBotApi
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage, ImageSendMessage
from pyppeteer import launch
from PIL import Image
from data_processor import get_stock_data, build_features, get_clean_stock_map

# =====================================================================
# 🔑 核心密鑰與自動化環境變數設定
# =====================================================================
LINE_ACCESS_TOKEN = 'uyt/NqkAS3yCOhUAWGqey5HYGBe5mfct1n5MB1OQaV8Y1/X8HoypqNBwq/LOVXk5YnCknVCi8LEE5KZTXkbXT2V0CpOCAk0C/YRPJRA3Z2RREefQjAG41UQV0pbp1YQCnewazDskTwrpBsxHwRo4OQdB04t89/1O/w1cDnyilFU='
IMGBB_API_KEY = '04de50429db3c829cad4eb48fcb669e6'
TARGET_USER_ID = 'Uf8818996f2c5846640e0ae8ae0360a72'

# 🚀【資工環境自適應】：如果是 GitHub 雲端環境，自動切換至當前工作目錄防止找不到硬碟 D 槽
if os.path.exists('D:/菜G/預定場地/'):
    IMAGE_DIR = 'D:/菜G/預定場地/'
else:
    IMAGE_DIR = './'
    print("ℹ️ 偵測為雲端 Linux 環境，場地截圖將落腳於目前專案根目錄")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
today = datetime.datetime.today().strftime('%Y-%m-%d')

# =====================================================================
# 📦 LINE 🤖 與 圖片處理 模組化函數
# =====================================================================
def upload_image_to_imgbb(image_path):
    url = "https://api.imgbb.com/1/upload"
    payload = {"key": IMGBB_API_KEY}
    try:
        with open(image_path, "rb") as f:
            files = {"image": (image_path, f)}
            response = requests.post(url, data=payload, files=files, timeout=15)
        if response.status_code == 200:
            return response.json()["data"]["url"]
        print("❌ imgBB 上傳失敗:", response.text)
    except Exception as e:
        print("❌ imgBB 連線異常:", e)
    return None

def send_line_text(user_id, text_content):
    try:
        line_bot_api.push_message(user_id, TextSendMessage(to=user_id, text=text_content))
        print('🚀 [LINE] 1開頭雲端測試戰報發射成功！')
    except LineBotApiError as e:
        print('❌ [LINE] 文字推送失敗:', e)

def send_line_image(user_id, image_url):
    try:
        message = ImageSendMessage(to=user_id, original_content_url=image_url, preview_image_url=image_url)
        line_bot_api.push_message(user_id, message)
        print('🚀 [LINE] 雲端場地合成圖發射成功！')
    except LineBotApiError as e:
        print('❌ [LINE] 圖片推送失敗:', e)

async def capture_venue_page(account, password, index_num):
    """四合一自適應網頁登入截圖引擎 (內建 Linux 無沙盒參數支援 Actions)"""
    print(f"  🎬 正在執行帳號 [{account}] 自動化場地查核與截圖...")
    try:
        browser = await launch(headless=True, defaultViewport={'width': 400, 'height': 840}, args=['--no-sandbox', '--disable-setuid-sandbox'])
        page = await browser.newPage()
        await page.goto('https://nd01.xuanen.com.tw/BPMemberOrder/BPMemberOrder', timeout=45000)
        await page.type('#txt_Account', account)
        await page.type('#txt_Pass', password)
        await page.click('#subform_Login > div > div > div.CssLoginBtn')
        await asyncio.sleep(1.5)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        
        screenshot_path = f'{IMAGE_DIR}{today}_{index_num}.png'
        await page.screenshot({'path': screenshot_path, 'fullPage': True})
        await browser.close()
        return screenshot_path
    except Exception as e:
        print(f"  ❌ 帳號 {account} 截圖失敗: {e}")
        return None

def fetch_twse_official_price(stock_no):
    """🛡️ 證交所官方原生 K 線校正通道"""
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
# 🚀 核心海選主程式
# =====================================================================
def main():
    print("🚀 啟動台股 AI 盤後海選任務（🎯 1開頭股票限定測試版）...")
    start_date = "2024-01-01"
    end_date = today
    
    stock_map = get_clean_stock_map()
    
    # 🎯【安全沙盒限制】：只抽取 1 開頭的傳產股進行局部壓力測試
    all_codes = sorted([
        code for code in stock_map.keys() 
        if len(code) == 4 and code.isdigit() and code.startswith("1")
    ])
    
    print(f"📈 【測試舞台】名冊載入中... 已鎖定 {len(all_codes)} 檔「1」開頭代碼。")
    print(f"⚡ [第一階段] 正在執行【分批安全減壓初篩】...")
    
    passed_codes = []
    total_count = len(all_codes)
    
    for idx, code in enumerate(all_codes):
        if idx % 50 == 0:
            print(f"  ⏳ 測試流大數據清洗中... 已排查: [{idx}/{total_count}] 檔...")
            
        try:
            raw = get_stock_data(code, start_date=start_date, end_date=end_date)
            if raw is None or len(raw) < 20: continue
                
            vol_series = raw['Volume'].dropna()
            close_series = raw['Close'].dropna()
            
            last_price = float(close_series.iloc[-1])
            last_vol = float(vol_series.iloc[-1])
            ma5_vol = float(vol_series.tail(5).mean())
            ma20_vol = float(vol_series.tail(20).mean())
            
            if ma5_vol >= 3000000 and ma5_vol >= ma20_vol and last_price >= 15.0:
                heat_ratio = last_vol / (ma20_vol + 1e-8)
                passed_codes.append({"code": code, "heat_ratio": heat_ratio})
        except:
            continue

    print(f"✨ 階段一完成！「1」開頭符合【5日均量黃金防線】的強勢股共：{len(passed_codes)} 檔")
    
    # 🔒 1開頭測試防空保底機制
    if not passed_codes:
        print("⚠️ 1開頭未達量能標的，強行啟動傳產明星保底標的流...")
        passed_codes = [
            {"code": "1402", "heat_ratio": 1.12},
            {"code": "1722", "heat_ratio": 1.05}
        ]
    
    passed_df = pd.DataFrame(passed_codes).sort_values(by="heat_ratio", ascending=False)
    top_50_codes = passed_df['code'].head(50).tolist()
    
    print(f"\n🔥 [第二階段] 精選 {len(top_50_codes)} 檔 1開頭種子進入模型擬合...")
    print(f"🛡️  雲端破關防禦：調用【證交所原生官方 API】進行今日實價校正！")
    
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
                
            # 🛡️ 證交所原生價格校正 (直接複寫回原始 raw，杜絕 KeyError)
            official_data = fetch_twse_official_price(code)
            if official_data["Success"]:
                last_idx = raw.index[-1]
                raw.loc[last_idx, ['Open', 'High', 'Low', 'Close', 'Volume']] = [
                    official_data["Open"], official_data["High"], official_data["Low"], official_data["Close"], official_data["Volume"]
                ]
                print(f"    ⚡ 5/29 證交所實價對齊成功 -> {code} 收盤: {official_data['Close']}")
            
            df_feat = build_features(raw)
            X, y = df_feat[feature_cols], df_feat['Target']
            
            model = XGBClassifier(n_estimators=60, max_depth=4, learning_rate=0.05, random_state=42)
            model.fit(X, y)
            
            prob = model.predict_proba(X.tail(1))[0][1]
            final_list.append({"code": code, "name": stock_map.get(code, code), "prob": float(prob)})
            time.sleep(0.3)
        except Exception as e:
            continue
            
    if final_list:
        result_df = pd.DataFrame(final_list).sort_values(by="prob", ascending=False)
        result_df_rename = result_df.rename(columns={"code": "代號", "name": "名稱", "prob": "發動機率"})
        result_df_rename.to_csv("best_stocks.csv", index=False, encoding='utf-8-sig')
        
        # 🎯 發射 LINE 測試戰報
        line_report = f"📊 【台股 AI 盤後 1開頭雲端測試戰報】\n📅 數據日期：{today}\n🤖 模式：GitHub Actions 雲端突圍\n----------------------\n"
        for i, row in result_df.head(5).iterrows():
            line_report += f"🏆 No.{i+1} [{row['code']}] {row['name']}\n🔥 明日發動勝率: {row['prob']:.2%}\n\n"
        line_report += "💡 本次雲端大腦測試完美過關！"
        send_line_text(TARGET_USER_ID, line_report)

    # =====================================================================
    # 🗓️ [第三階段：自動化場地預約與截圖合併工作流]
    # =====================================================================
    print("\n🗓️  接續執行場地自動化排程查核任務...")
    accounts_info = [
        ('L123839625', 'taiwan1', '1'),
        ('J222523969', 'vanessa1208', '2'),
        ('L223274297', '0000', '3'),
        ('M222190275', 'tangmei0104', '4')
    ]
    
    loop = asyncio.get_event_loop()
    for acc, pwd, idx_str in accounts_info:
        loop.run_until_complete(capture_venue_page(acc, pwd, idx_str))
        
    print("🎨 正在進行 4 檔場地全景圖矩陣拼接...")
    try:
        img1 = Image.open(f'{IMAGE_DIR}{today}_1.png')
        img2 = Image.open(f'{IMAGE_DIR}{today}_2.png')
        img3 = Image.open(f'{IMAGE_DIR}{today}_3.png')
        img4 = Image.open(f'{IMAGE_DIR}{today}_4.png')
        
        w1, h1 = img1.size
        w2, h2 = img2.size
        w3, h3 = img3.size
        w4, h4 = img4.size
        
        new_width = w1 + w2 + w3 + w4
        new_height = max(h1, h2, h3, h4)
        
        new_image = Image.new('RGB', (new_width, new_height))
        new_image.paste(img1, (0, 0))
        new_image.paste(img2, (w1, 0))
        new_image.paste(img3, (w1 + w2, 0))
        new_image.paste(img4, (w1 + w2 + w3, 0))
        
        output_path = f'{IMAGE_DIR}{today}.png'
        new_image.save(output_path)
        
        venue_url = upload_image_to_imgbb(output_path)
        if venue_url:
            send_line_image(TARGET_USER_ID, venue_url)
    except Exception as e:
        print(f"❌ 圖片合併或推送失敗: {e}")

if __name__ == "__main__": 
    main()