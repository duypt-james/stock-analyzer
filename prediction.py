import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Tạo features từ price data và indicators."""
    features = pd.DataFrame(index=df.index)

    features["returns_1d"] = df["Close"].pct_change(1)
    features["returns_5d"] = df["Close"].pct_change(5)
    features["returns_10d"] = df["Close"].pct_change(10)
    features["returns_20d"] = df["Close"].pct_change(20)

    features["volatility_10d"] = df["Close"].pct_change().rolling(10).std()
    features["volatility_20d"] = df["Close"].pct_change().rolling(20).std()

    features["high_low_range"] = (df["High"] - df["Low"]) / df["Close"]
    features["close_to_high"] = (df["High"] - df["Close"]) / df["Close"]
    features["close_to_low"] = (df["Close"] - df["Low"]) / df["Close"]

    features["volume_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()

    if "RSI" in df.columns:
        features["rsi"] = df["RSI"]
    if "MACD" in df.columns:
        features["macd"] = df["MACD"]
        features["macd_signal"] = df["MACD_Signal"]
        features["macd_hist"] = df["MACD_Histogram"]
    if "Stoch_K" in df.columns:
        features["stoch_k"] = df["Stoch_K"]
        features["stoch_d"] = df["Stoch_D"]
    if "BB_Width" in df.columns:
        features["bb_width"] = df["BB_Width"]
    if "ATR" in df.columns:
        features["atr"] = df["ATR"]
    if "MA20" in df.columns:
        features["ma20_ratio"] = df["Close"] / df["MA20"]
    if "MA50" in df.columns:
        features["ma50_ratio"] = df["Close"] / df["MA50"]
    if "MA200" in df.columns:
        features["ma200_ratio"] = df["Close"] / df["MA200"]

    return features


def create_target(df: pd.DataFrame, days_ahead: int = 5) -> pd.Series:
    """Tạo target: 1 nếu giá tăng sau N ngày, 0 nếu giảm."""
    future_return = df["Close"].pct_change(days_ahead).shift(-days_ahead)
    target = (future_return > 0).astype(int)
    return target


def train_prediction_model(df: pd.DataFrame, days_ahead: int = 5) -> dict:
    """Train model và trả về kết quả."""
    features = create_features(df)
    target = create_target(df, days_ahead)

    valid_mask = features.notna().all(axis=1) & target.notna()
    features = features[valid_mask]
    target = target[valid_mask]

    if len(features) < 100:
        return {"error": "Không đủ dữ liệu để train model (cần ít nhất 100 dòng)"}

    X_train, X_test, y_train, y_test = train_test_split(
        features, target, test_size=0.2, shuffle=False
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    rf_model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)
    rf_model.fit(X_train_scaled, y_train)
    rf_pred = rf_model.predict(X_test_scaled)

    gb_model = GradientBoostingClassifier(n_estimators=100, random_state=42, max_depth=5)
    gb_model.fit(X_train_scaled, y_train)
    gb_pred = gb_model.predict(X_test_scaled)

    latest_features = features.iloc[[-1]]
    latest_scaled = scaler.transform(latest_features)

    rf_signal = int(rf_model.predict(latest_scaled)[0])
    gb_signal = int(gb_model.predict(latest_scaled)[0])
    rf_prob = rf_model.predict_proba(latest_scaled)[0].tolist()
    gb_prob = gb_model.predict_proba(latest_scaled)[0].tolist()

    ensemble_signal = 1 if (rf_signal + gb_signal) >= 1 else 0
    ensemble_prob = [(rf_prob[i] + gb_prob[i]) / 2 for i in range(2)]

    importances = dict(zip(features.columns, rf_model.feature_importances_))
    top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "rf_accuracy": round(accuracy_score(y_test, rf_pred) * 100, 2),
        "gb_accuracy": round(accuracy_score(y_test, gb_pred) * 100, 2),
        "ensemble_signal": ensemble_signal,
        "ensemble_confidence": round(max(ensemble_prob) * 100, 2),
        "rf_signal": rf_signal,
        "gb_signal": gb_signal,
        "rf_confidence": round(max(rf_prob) * 100, 2),
        "gb_confidence": round(max(gb_prob) * 100, 2),
        "prediction": "TĂNG" if ensemble_signal == 1 else "GIẢM",
        "days_ahead": days_ahead,
        "top_features": top_features,
    }


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Tạo tín hiệu mua/bán dựa trên technical analysis."""
    signals = pd.DataFrame(index=df.index)
    signals["signal"] = 0

    if "RSI" in df.columns:
        signals.loc[df["RSI"] < 30, "signal"] += 1
        signals.loc[df["RSI"] > 70, "signal"] -= 1

    if "MACD" in df.columns and "MACD_Signal" in df.columns:
        macd_cross_up = (df["MACD"] > df["MACD_Signal"]) & (df["MACD"].shift(1) <= df["MACD_Signal"].shift(1))
        macd_cross_down = (df["MACD"] < df["MACD_Signal"]) & (df["MACD"].shift(1) >= df["MACD_Signal"].shift(1))
        signals.loc[macd_cross_up, "signal"] += 1
        signals.loc[macd_cross_down, "signal"] -= 1

    if "Stoch_K" in df.columns and "Stoch_D" in df.columns:
        stoch_cross_up = (df["Stoch_K"] > df["Stoch_D"]) & (df["Stoch_K"].shift(1) <= df["Stoch_D"].shift(1))
        stoch_cross_down = (df["Stoch_K"] < df["Stoch_D"]) & (df["Stoch_K"].shift(1) >= df["Stoch_D"].shift(1))
        signals.loc[stoch_cross_up, "signal"] += 1
        signals.loc[stoch_cross_down, "signal"] -= 1

    if "MA20" in df.columns and "MA50" in df.columns:
        ma_cross_up = (df["MA20"] > df["MA50"]) & (df["MA20"].shift(1) <= df["MA50"].shift(1))
        ma_cross_down = (df["MA20"] < df["MA50"]) & (df["MA20"].shift(1) >= df["MA50"].shift(1))
        signals.loc[ma_cross_up, "signal"] += 1
        signals.loc[ma_cross_down, "signal"] -= 1

    if "BB_Lower" in df.columns:
        signals.loc[df["Close"] < df["BB_Lower"], "signal"] += 1
        signals.loc[df["Close"] > df["BB_Upper"], "signal"] -= 1

    if "Ichimoku_Tenkan" in df.columns and "Ichimoku_Kijun" in df.columns:
        ichi_up = (df["Ichimoku_Tenkan"] > df["Ichimoku_Kijun"]) & (df["Ichimoku_Tenkan"].shift(1) <= df["Ichimoku_Kijun"].shift(1))
        ichi_down = (df["Ichimoku_Tenkan"] < df["Ichimoku_Kijun"]) & (df["Ichimoku_Tenkan"].shift(1) >= df["Ichimoku_Kijun"].shift(1))
        signals.loc[ichi_up, "signal"] += 1
        signals.loc[ichi_down, "signal"] -= 1

    signals["strength"] = signals["signal"].abs()
    signals["type"] = signals["signal"].apply(
        lambda x: "MUA" if x >= 2 else ("BÁN" if x <= -2 else ("MUA nhẹ" if x == 1 else ("BÁN nhẹ" if x == -1 else "TRUNG TÍNH")))
    )

    return signals
