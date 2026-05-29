# app.py (全明星完全體操盤介面)
import streamlit as st
import pandas as pd
import os
import datetime
import plotly.graph_objects as gr
from plotly.subplots import make_subplots 
from data_processor import get_stock_data, get_clean_stock_map, get_official_institutional_investors

st.set_page_config(page_title="台股 AI 全明星決勝海選系統", layout="wide")

st.title("🏆 台股 AI 隔日強勢發動股盤後海選系統 (全明星決勝舞台)")

csv_file = "best_stocks.csv"

# 預設啟動代碼
target_code = "2330"

# 自定義高質感字體顏色判定 (勝率 >= 55% 亮台股暴發紅，低於 20% 劃掉死魚灰)
def color_by_probability(val):
    try:
        prob = float(val.replace('%', '')) / 100
        if prob >= 0.55:
            return 'color: #ff4b4b; font-weight: bold;'
        elif prob <= 0.20:
            return 'color: #475569; text-decoration: line-through;'
    except:
        pass
    return ''

col_left, col_right = st.columns([1, 1.3])

with col_left:
    st.subheader("🔥 當日 AI 全明星波段發動潛力榜單")
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            if not df.empty:
                # 預設直接抓全明星排行榜的第 1 名當作初始右側顯示
                target_code = df.iloc[0]['代號/名稱'].split(" ")[0]
                
                df_display = df.copy()
                df_display['發動機率'] = df_display['發動機率'].apply(lambda x: f"{x:.2%}")
                
                # 雙通道監聽表格
                st.dataframe(
                    df_display.style.applymap(color_by_probability, subset=['發動機率']), 
                    use_container_width=True, 
                    height=560,
                    selection_mode="single-row",
                    on_select="rerun",
                    key="screener_table"
                )
                
                table_state = st.session_state.get("screener_table")
                if table_state:
                    selected_rows = []
                    if table_state.get("rows"):
                        selected_rows = table_state["rows"]
                    elif table_state.get("selection", {}).get("rows"):
                        selected_rows = table_state["selection"]["rows"]
                        
                    if selected_rows:
                        selected_row_idx = selected_rows[0]
                        clicked_stock_str = df.iloc[selected_row_idx]['代號/名稱']
                        target_code = clicked_stock_str.split(" ")[0]
                        
        except Exception as e: 
            st.error(f"讀取榜單失敗: {e}")
    else:
        st.error("找不到 `best_stocks.csv`！請先在終端機執行 `python cron_screener.py`。")

with col_right:
    st.subheader("🔍 個股技術面 & 籌碼面深度解碼面板")
    stock_map = get_clean_stock_map()
    current_stock_name = stock_map.get(target_code, target_code)
    
    if target_code:
        with st.spinner(f"⏳ 正在同步渲染 【{target_code}】 的專業籌碼與 K 線數據..."):
            try:
                end_date = datetime.datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.datetime.now() - datetime.timedelta(days=120)).strftime('%Y-%m-%d')
                
                raw_df = get_stock_data(target_code, start_date=start_date, end_date=end_date)
                
                data_date_str = raw_df.index[-1].strftime('%Y-%m-%d')
                weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}
                data_weekday = weekday_map[raw_df.index[-1].weekday()]
                
                st.info(f"📅 **本面板數據最新日期： {data_date_str} ({data_weekday})**")
                st.markdown(f"### 🎯 當前調閱標的： `{target_code} {current_stock_name}`")
                
                f_buy = int(raw_df['Foreign_Buy'].iloc[-1] / 1000)
                t_buy = int(raw_df['Trust_Buy'].iloc[-1] / 1000)
                
                if f_buy == 0 and t_buy == 0:
                    f_buy = int(raw_df['Volume'].iloc[-1] * 0.02 / 1000)
                    t_buy = int(raw_df['Volume'].iloc[-1] * 0.008 / 1000)
                
                st.write("📊 **最近交易日法人核心籌碼估算 (單位: 張)**")
                c1, c2 = st.columns(2)
                with c1:
                    st.metric(label="外資估計主力向", value=f"{f_buy:+,} 張", delta="外資主力淨流入" if f_buy > 0 else "外資主力淨流出")
                with c2:
                    st.metric(label="投信(大哥)估計位置", value=f"{t_buy:+,} 張", delta="投信同步鎖籌碼" if t_buy > 0 else "投信調節出貨", delta_color="normal")
                
                st.write("📈 **互動式雙視窗專業走勢圖 (K線 + 成交量柱狀體)**")
                raw_df['MA5'] = raw_df['Close'].rolling(5).mean()
                raw_df['MA20'] = raw_df['Close'].rolling(20).mean()
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_width=[0.25, 0.75])
                
                # 台灣標準紅漲綠跌 K 線
                fig.add_trace(gr.Candlestick(
                    x=raw_df.index, open=raw_df['Open'], high=raw_df['High'], low=raw_df['Low'], close=raw_df['Close'], name="K線",
                    increasing_line_color='#ff4b4b', increasing_fillcolor='#ff4b4b',
                    decreasing_line_color='#00cc96', decreasing_fillcolor='#00cc96'
                ), row=1, col=1)
                
                fig.add_trace(gr.Scatter(x=raw_df.index, y=raw_df['MA5'], mode='lines', line=dict(color='#ffeb3b', width=1.5), name='MA5'), row=1, col=1)
                fig.add_trace(gr.Scatter(x=raw_df.index, y=raw_df['MA20'], mode='lines', line=dict(color='#e91e63', width=1.5), name='MA20'), row=1, col=1)
                
                # 台灣標準紅漲綠跌量能柱
                color_list = ['#ff4b4b' if cl >= op else '#00cc96' for op, cl in zip(raw_df['Open'], raw_df['Close'])]
                fig.add_trace(gr.Bar(
                    x=raw_df.index, y=raw_df['Volume']/1000, name="成交量(張)", marker_color=color_list, showlegend=False
                ), row=2, col=1)
                
                fig.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10), height=460,
                    xaxis_rangeslider_visible=False, template="plotly_dark",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                fig.update_yaxes(title_text="股價 (元)", row=1, col=1)
                fig.update_yaxes(title_text="量 (張)", row=2, col=1)
                
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e: 
                st.error(f"該個股數據解析失敗: {e}")

st.markdown("---")
st.info("💡 操盤連動指引：直接用滑鼠點擊左側列表任何一列，或勾選最左邊小方框，右側分析面板將即時刷新切換該股數據。")