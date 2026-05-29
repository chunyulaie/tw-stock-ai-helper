import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, classification_report
from data_processor import get_stock_data, build_features

def main():
    ticker_code = "2330.TW" 
    raw_data = get_stock_data(ticker_code, start_date="2020-01-01", end_date="2026-05-25")
    df = build_features(raw_data)
    
    # 更新為新版的去量綱特徵
    feature_cols = [
        'Return_1d', 'Return_5d', 'Volume_Ratio', 
        'Close_to_MA5', 'Close_to_MA20', 'Close_to_MA60', 'MA5_to_MA20',
        'RSI', 'MACD_Hist_Norm', 'BB_Position', 'Weekday', 'Month'
    ]
    X = df[feature_cols]
    y = df['Target']
    
    # 時間序列切分 (80% 訓練, 20% 測試)
    split_index = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]
    
    print(f"\n訓練集資料筆數: {len(X_train)} 筆 | 測試集資料筆數: {len(X_test)} 筆")
    
    # 訓練優化後的 XGBoost 模型
    model = XGBClassifier(
        n_estimators=150, 
        max_depth=4,       # 稍微調淺深度防止過擬合
        learning_rate=0.03, # 降低學習率讓模型學得更細緻
        random_state=42
    )
    
    print("\n正在訓練優化後的 XGBoost 模型...")
    model.fit(X_train, y_train)
    
    # 預測與評估
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print("\n================ 新模型評估結果 ================")
    print(f"測試集預測準率 (Accuracy): {accuracy:.2%}")
    print("\n詳細分類報告:")
    print(classification_report(y_test, y_pred, target_names=['預測跌/平', '預測漲']))
    
    # 特徵重要性
    importances = model.feature_importances_
    feat_imp = pd.Series(importances, index=feature_cols).sort_values(ascending=False)
    print("\n--- 新 AI 核心依賴指標排行榜 ---")
    print(feat_imp.head(5))

if __name__ == "__main__":
    main()