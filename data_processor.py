# data_processor.py (Big5 編碼校正·真全台股名冊完全體)
import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import requests
import numpy as np
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

_TW_STOCK_MAP = None
_CHIP_CACHE = None 

def get_official_institutional_investors():
    global _CHIP_CACHE
    if _CHIP_CACHE is not None: return _CHIP_CACHE
    chip_map = {} 
    try:
        url_l = "https://openapi.twse.com.tw/v1/38U/TWT38U"
        res_l = requests.get(url_l, timeout=3)
        if res_l.status_code == 200:
            for row in res_l.json():
                code = row.get("證券代號", "").strip()
                item_name = row.get("三大法人名稱", "").strip()
                try: net_buy = int(row.get("買賣超股數", "0").replace(",", ""))
                except: net_buy = 0
                if code not in chip_map: chip_map[code] = {"Foreign_Buy": 0, "Trust_Buy": 0}
                if "外資" in item_name or "外國機構" in item_name: chip_map[code]["Foreign_Buy"] += net_buy
                elif "投信" in item_name: chip_map[code]["Trust_Buy"] += net_buy
    except: pass
    _CHIP_CACHE = chip_map
    return _CHIP_CACHE

def get_clean_stock_map():
    global _TW_STOCK_MAP
    if _TW_STOCK_MAP is not None: return _TW_STOCK_MAP
    stock_map = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        # 1. 抓取上市最完整名冊網頁 (強制鎖定 Big5 編碼)
        res_l = requests.get("https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", headers=headers, timeout=5)
        if res_l.status_code == 200:
            res_l.encoding = 'big5'
            dfs = pd.read_html(res_l.text)
            if dfs:
                df = dfs[0]
                for val in df[0].dropna():
                    parts = str(val).split('\u3000')
                    if len(parts) >= 2:
                        code, name = parts[0].strip(), parts[1].strip()
                        if len(code) == 4 and code.isdigit():
                            stock_map[code] = name
                            
        # 2. 抓取上櫃最完整名冊網頁 (強制鎖定 Big5 編碼)
        res_o = requests.get("https://isin.twse.com.tw/isin/C_public.jsp?strMode=4", headers=headers, timeout=5)
        if res_o.status_code == 200:
            res_o.encoding = 'big5'
            dfs = pd.read_html(res_o.text)
            if dfs:
                df = dfs[0]
                for val in df[0].dropna():
                    parts = str(val).split('\u3000')
                    if len(parts) >= 2:
                        code, name = parts[0].strip(), parts[1].strip()
                        if len(code) == 4 and code.isdigit():
                            stock_map[code] = name
    except:
        pass
        
    _TW_STOCK_MAP = stock_map
    return _TW_STOCK_MAP

def get_stock_data(user_input, start_date, end_date):
    user_input = user_input.strip()
    stock_map = get_clean_stock_map()
    ticker = f"{user_input}.TW" if user_input in stock_map else user_input
    
    df = yf.download(ticker, start=start_date, end=end_date, group_by='column', progress=False)
    if df.empty and ".TW" in ticker:
        ticker = ticker.replace(".TW", ".TWO")
        df = yf.download(ticker, start=start_date, end=end_date, group_by='column', progress=False)
        
    if df.empty: return None
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).strip() for c in df.columns]
    df.index = pd.to_datetime(df.index)
    pure_code = ticker.split(".")[0]
    
    df['Is_ETF'] = 1 if pure_code.startswith("00") else 0
    official_chips = get_official_institutional_investors()
    
    if official_chips and pure_code in official_chips:
        df['Foreign_Buy'] = official_chips[pure_code]['Foreign_Buy']
        df['Trust_Buy'] = 0
    else:
        close_pct = df['Close'].squeeze().pct_change().fillna(0)
        df['Foreign_Buy'] = df['Volume'] * 0.15 * np.sign(close_pct)
        df['Trust_Buy'] = df['Volume'] * 0.05 * np.sign(close_pct).rolling(3).mean().fillna(0)

    try:
        extended_start = (pd.to_datetime(start_date) - pd.Timedelta(days=90)).strftime('%Y-%m-%d')
        global_df = yf.download(["^SOX", "^VIX", "^TWII"], start=extended_start, end=end_date, progress=False)
        if isinstance(global_df.columns, pd.MultiIndex):
            sox_close = global_df[('Close', '^SOX')].squeeze()
            vix_close = global_df[('Close', '^VIX')].squeeze()
            tw_close = global_df[('Close', '^TWII')].squeeze()
        else:
            sox_close, vix_close, tw_close = 0, 0, 0
            
        df['US_SOX_Return'] = sox_close.pct_change(1).shift(1)
        df['US_VIX_Return'] = vix_close.pct_change(1).shift(1)
        tw_ma20 = SMAIndicator(close=tw_close, n=20).sma_indicator() if len(tw_close)>20 else tw_close
        df['Market_Bias_20d'] = (tw_close / tw_ma20) - 1
        df['US_SOX_Return'] = df['US_SOX_Return'].ffill().fillna(0)
        df['US_VIX_Return'] = df['US_VIX_Return'].ffill().fillna(0)
        df['Market_Bias_20d'] = df['Market_Bias_20d'].ffill().fillna(0)
    except:
        df['US_SOX_Return'], df['US_VIX_Return'], df['Market_Bias_20d'] = 0, 0, 0
        
    df.attrs['stock_name'] = stock_map.get(pure_code, pure_code)
    return df

def build_features(df):
    feat_df = pd.DataFrame(index=df.index)
    close_series = df['Close'].squeeze()
    high_series = df['High'].squeeze()
    low_series = df['Low'].squeeze()
    volume_series = df['Volume'].squeeze()
    
    feat_df['Return_1d'] = close_series.pct_change(1)
    feat_df['Return_5d'] = close_series.pct_change(5)
    feat_df['Volume_Ratio'] = volume_series.pct_change(1)
    feat_df['US_SOX_Return'] = df.get('US_SOX_Return', 0)
    feat_df['US_VIX_Return'] = df.get('US_VIX_Return', 0)
    feat_df['Market_Bias_20d'] = df.get('Market_Bias_20d', 0)
    
    feat_df['Foreign_Investor_Ratio'] = df['Foreign_Buy'] / (volume_series + 1e-8)
    feat_df['Trust_Investor_Ratio'] = df['Trust_Buy'] / (volume_series + 1e-8)
    clv = ((close_series - low_series) - (high_series - close_series)) / (high_series - low_series + 1e-8)
    feat_df['Main_Force_Flow'] = clv * volume_series.pct_change(1)
    feat_df['Chaikin_Money_Flow'] = (clv * volume_series).rolling(20).sum() / (volume_series.rolling(20).sum() + 1e-8)
    
    ma5 = SMAIndicator(close=close_series, n=5).sma_indicator()
    ma20 = SMAIndicator(close=close_series, n=20).sma_indicator()
    ma60 = SMAIndicator(close=close_series, n=60).sma_indicator()
    feat_df['Close_to_MA5'] = (close_series / ma5) - 1
    feat_df['Close_to_MA20'] = (close_series / ma20) - 1
    feat_df['Close_to_MA60'] = (close_series / ma60) - 1
    feat_df['MA5_to_MA20'] = (ma5 / ma20) - 1
    
    feat_df['RSI'] = RSIIndicator(close=close_series, n=14).rsi()
    feat_df['MACD_Hist_Norm'] = MACD(close=close_series, n_fast=12, n_slow=26, n_sign=9).macd_diff() / close_series
    bb_init = BollingerBands(close=close_series, n=20, ndev=2)
    feat_df['BB_Position'] = (close_series - bb_init.bollinger_lband()) / (bb_init.bollinger_hband() - bb_init.bollinger_lband() + 1e-8)
    feat_df['Weekday'] = df.index.weekday
    feat_df['Month'] = df.index.month
    
    future_max_high = high_series.rolling(5).max().shift(-5)
    feat_df['Target'] = ((future_max_high / close_series) - 1 >= 0.025).astype(int)
    feat_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    feat_df.dropna(inplace=True)
    return feat_df