import pandas as pd
import numpy as np
from scipy.signal import argrelextrema


def add_moving_averages(df: pd.DataFrame, periods: list[int] = [10, 20, 50, 200]) -> pd.DataFrame:
    for p in periods:
        df[f"MA{p}"] = df["Close"].rolling(window=p).mean()
    return df


def add_exponential_moving_averages(df: pd.DataFrame, periods: list[int] = [12, 26]) -> pd.DataFrame:
    for p in periods:
        df[f"EMA{p}"] = df["Close"].ewm(span=p, adjust=False).mean()
    return df


def add_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
    df["BB_Middle"] = df["Close"].rolling(window=period).mean()
    rolling_std = df["Close"].rolling(window=period).std()
    df["BB_Upper"] = df["BB_Middle"] + (rolling_std * std_dev)
    df["BB_Lower"] = df["BB_Middle"] - (rolling_std * std_dev)
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Middle"]
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_Signal"] = df["MACD"].ewm(span=signal, adjust=False).mean()
    df["MACD_Histogram"] = df["MACD"] - df["MACD_Signal"]
    return df


def add_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    low_min = df["Low"].rolling(window=k_period).min()
    high_max = df["High"].rolling(window=k_period).max()
    df["Stoch_K"] = 100 * (df["Close"] - low_min) / (high_max - low_min)
    df["Stoch_D"] = df["Stoch_K"].rolling(window=d_period).mean()
    return df


def add_ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    nine_high = df["High"].rolling(window=9).max()
    nine_low = df["Low"].rolling(window=9).min()
    df["Ichimoku_Tenkan"] = (nine_high + nine_low) / 2

    twenty_six_high = df["High"].rolling(window=26).max()
    twenty_six_low = df["Low"].rolling(window=26).min()
    df["Ichimoku_Kijun"] = (twenty_six_high + twenty_six_low) / 2

    df["Ichimoku_Senkou_A"] = ((df["Ichimoku_Tenkan"] + df["Ichimoku_Kijun"]) / 2).shift(26)

    fifty_two_high = df["High"].rolling(window=52).max()
    fifty_two_low = df["Low"].rolling(window=52).min()
    df["Ichimoku_Senkou_B"] = ((fifty_two_high + fifty_two_low) / 2).shift(26)

    df["Ichimoku_Chikou"] = df["Close"].shift(-26)
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR"] = true_range.rolling(window=period).mean()
    return df


def add_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df["Volume_MA20"] = df["Volume"].rolling(window=20).mean()
    df["OBV"] = (np.sign(df["Close"].diff()) * df["Volume"]).fillna(0).cumsum()
    return df


# ===================== DONG TIEN (MONEY FLOW) =====================

def add_money_flow(df: pd.DataFrame) -> pd.DataFrame:
    """Thêm các chỉ báo dòng tiền."""
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    raw_mf = typical_price * df["Volume"]
    df["MFI"] = _calc_mfi(typical_price, df["Volume"], period=14)

    df["CMF"] = _calc_cmf(df, period=20)

    df["OBV_MA"] = df["OBV"].rolling(window=20).mean()

    price_change = df["Close"].pct_change()
    volume_change = df["Volume"].pct_change()
    df["Volume_Price_Corr"] = price_change.rolling(20).corr(volume_change)

    df["Force_Index"] = df["Close"].diff() * df["Volume"]
    df["Force_Index_EMA"] = df["Force_Index"].ewm(span=13, adjust=False).mean()

    return df


def _calc_mfi(typical_price: pd.Series, volume: pd.Series, period: int = 14) -> pd.Series:
    """Tính Money Flow Index."""
    delta = typical_price.diff()
    positive_flow = (delta.where(delta > 0, 0) * volume).rolling(window=period).sum()
    negative_flow = ((-delta).where(delta < 0, 0) * volume).rolling(window=period).sum()
    mfi = 100 - (100 / (1 + positive_flow / negative_flow))
    return mfi


def _calc_cmf(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Tính Chaikin Money Flow."""
    mfm = ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / (df["High"] - df["Low"])
    mfm = mfm.fillna(0)
    mfv = mfm * df["Volume"]
    cmf = mfv.rolling(window=period).sum() / df["Volume"].rolling(window=period).sum()
    return cmf


# ===================== PHAN TICH SONG (WAVE ANALYSIS) =====================

def detect_waves(df: pd.DataFrame, order: int = 5) -> pd.DataFrame:
    """Phát hiện sóng giá: tìm các đỉnh/đáy local."""
    prices = df["Close"].values
    highs_idx = argrelextrema(prices, np.greater_equal, order=order)[0]
    lows_idx = argrelextrema(prices, np.less_equal, order=order)[0]

    df["Wave_High"] = np.nan
    df["Wave_Low"] = np.nan

    for i in highs_idx:
        if i < len(df):
            df.iloc[i, df.columns.get_loc("Wave_High")] = df.iloc[i]["Close"]

    for i in lows_idx:
        if i < len(df):
            df.iloc[i, df.columns.get_loc("Wave_Low")] = df.iloc[i]["Close"]

    df["Wave_High"] = df["Wave_High"].ffill()
    df["Wave_Low"] = df["Wave_Low"].ffill()

    return df


def analyze_wave_trend(df: pd.DataFrame) -> dict:
    """Phân tích xu hướng sóng hiện tại."""
    recent = df.dropna(subset=["Wave_High", "Wave_Low"]).tail(50)

    if len(recent) < 10:
        return {"trend": "KHÔNG ĐỦ DỮ LIỆU", "wave_count": 0, "description": ""}

    highs = recent[recent["Wave_High"] == recent["Close"]]["Wave_High"].values
    lows = recent[recent["Wave_Low"] == recent["Close"]]["Wave_Low"].values

    if len(highs) < 2 or len(lows) < 2:
        return {"trend": "KHÔNG RÕ", "wave_count": 0, "description": ""}

    recent_highs = highs[-3:]
    recent_lows = lows[-3:]

    higher_highs = all(recent_highs[i] < recent_highs[i+1] for i in range(len(recent_highs)-1))
    higher_lows = all(recent_lows[i] < recent_lows[i+1] for i in range(len(recent_lows)-1))
    lower_highs = all(recent_highs[i] > recent_highs[i+1] for i in range(len(recent_highs)-1))
    lower_lows = all(recent_lows[i] > recent_lows[i+1] for i in range(len(recent_lows)-1))

    if higher_highs and higher_lows:
        trend = "TĂNG (Sóng tăng)"
        desc = "Các đỉnh và đáy đều cao dần → xu hướng tăng mạnh. Đây là sóng impulse."
    elif lower_highs and lower_lows:
        trend = "GIẢM (Sóng giảm)"
        desc = "Các đỉnh và đáy đều thấp dần → xu hướng giảm. Đây là sóng corrective."
    elif higher_highs and not higher_lows:
        trend = "TĂNG YẾU"
        desc = "Đỉnh cao dần nhưng đáy không rõ → đà tăng đang yếu dần."
    elif not higher_highs and higher_lows:
        trend = "TÍCH LƯU / SIDEWAY"
        desc = "Đỉnh không cao hơn, đáy không thấp hơn → thị trường đang tích lũy."
    else:
        trend = "BIẾN ĐỘNG"
        desc = "Không có pattern sóng rõ ràng."

    wave_count = len(recent_highs) + len(recent_lows)

    return {
        "trend": trend,
        "wave_count": wave_count,
        "description": desc,
        "last_high": float(recent_highs[-1]) if len(recent_highs) > 0 else None,
        "last_low": float(recent_lows[-1]) if len(recent_lows) > 0 else None,
    }


# ===================== DIEM MUA/BAN GOI Y =====================

def suggest_entry_points(df: pd.DataFrame, atr_multiplier: float = 1.5, market_status: dict = None) -> dict:
    """Gợi ý điểm mua/bán cụ thể với giá, có xét đến thị trường chung."""
    latest = df.iloc[-1]
    current_price = latest["Close"]
    atr = latest["ATR"] if "ATR" in df.columns else (latest["High"] - latest["Low"])

    buy_score = 0
    sell_score = 0

    reasons_buy = []
    reasons_sell = []

    # ---- ANH HUONG TU THI TRUONG CHUNG ----
    market_adjustment = 0
    if market_status and "strength" in market_status:
        mkt_strength = market_status["strength"]
        if mkt_strength >= 2:
            buy_score += 1
            market_adjustment = 1
            reasons_buy.append(f"Thị trường thuận lợi ({market_status['trend']})")
        elif mkt_strength <= -2:
            sell_score += 1
            market_adjustment = -1
            reasons_sell.append(f"Thị trường bất lợi ({market_status['trend']})")
        elif mkt_strength >= 0:
            reasons_buy.append(f"Thị trường trung tính ({market_status['trend']})")
        else:
            reasons_sell.append(f"Thị trường trung tính ({market_status['trend']})")

    if "RSI" in df.columns:
        if latest["RSI"] < 35:
            buy_score += 2
            reasons_buy.append(f"RSI={latest['RSI']:.1f} (quá bán)")
        elif latest["RSI"] < 45:
            buy_score += 1
            reasons_buy.append(f"RSI={latest['RSI']:.1f} (thấp)")
        elif latest["RSI"] > 70:
            sell_score += 2
            reasons_sell.append(f"RSI={latest['RSI']:.1f} (quá mua)")
        elif latest["RSI"] > 60:
            sell_score += 1
            reasons_sell.append(f"RSI={latest['RSI']:.1f} (cao)")

    if "MACD" in df.columns and "MACD_Signal" in df.columns:
        if latest["MACD"] > latest["MACD_Signal"] and latest["MACD_Histogram"] > 0:
            buy_score += 1
            reasons_buy.append("MACD > Signal (đà tăng)")
        elif latest["MACD"] < latest["MACD_Signal"] and latest["MACD_Histogram"] < 0:
            sell_score += 1
            reasons_sell.append("MACD < Signal (đà giảm)")

    if "MA20" in df.columns:
        if current_price > latest["MA20"]:
            buy_score += 1
            reasons_buy.append("Giá trên MA20")
        else:
            sell_score += 1
            reasons_sell.append("Giá dưới MA20")

    if "BB_Lower" in df.columns:
        if current_price <= latest["BB_Lower"] * 1.01:
            buy_score += 2
            reasons_buy.append("Giá chạm/under BB Lower")
        elif current_price >= latest["BB_Upper"] * 0.99:
            sell_score += 2
            reasons_sell.append("Giá chạm/over BB Upper")

    if "Ichimoku_Senkou_A" in df.columns and "Ichimoku_Senkou_B" in df.columns:
        cloud_top = max(latest["Ichimoku_Senkou_A"], latest["Ichimoku_Senkou_B"])
        cloud_bottom = min(latest["Ichimoku_Senkou_A"], latest["Ichimoku_Senkou_B"])
        if current_price > cloud_top:
            buy_score += 1
            reasons_buy.append("Giá trên đám mây Ichimoku")
        elif current_price < cloud_bottom:
            sell_score += 1
            reasons_sell.append("Giá dưới đám mây Ichimoku")

    if "MFI" in df.columns:
        if latest["MFI"] < 20:
            buy_score += 1
            reasons_buy.append(f"MFI={latest['MFI']:.1f} (dòng tiền quá bán)")
        elif latest["MFI"] > 80:
            sell_score += 1
            reasons_sell.append(f"MFI={latest['MFI']:.1f} (dòng tiền quá mua)")

    # ---- STOCHASTIC K/D CROSSOVER ----
    if "Stoch_K" in df.columns and "Stoch_D" in df.columns:
        if len(df) > 1:
            prev_k = df["Stoch_K"].iloc[-2]
            prev_d = df["Stoch_D"].iloc[-2]
            if prev_k <= prev_d and latest["Stoch_K"] > latest["Stoch_D"] and latest["Stoch_K"] < 30:
                buy_score += 2
                reasons_buy.append(f"Stochastic K cắt lên D ở vùng quá bán ({latest['Stoch_K']:.1f})")
            elif latest["Stoch_K"] < 20 and latest["Stoch_D"] < 20:
                buy_score += 1
                reasons_buy.append(f"Stochastic quá bán K={latest['Stoch_K']:.1f}")
            elif prev_k >= prev_d and latest["Stoch_K"] < latest["Stoch_D"] and latest["Stoch_K"] > 70:
                sell_score += 2
                reasons_sell.append(f"Stochastic K cắt xuống D ở vùng quá mua ({latest['Stoch_K']:.1f})")
            elif latest["Stoch_K"] > 80 and latest["Stoch_D"] > 80:
                sell_score += 1
                reasons_sell.append(f"Stochastic quá mua K={latest['Stoch_K']:.1f}")

    # ---- MA CROSSOVERS (GOLDEN/DEATH CROSS) ----
    if "MA20" in df.columns and "MA50" in df.columns and len(df) > 1:
        prev_ma20 = df["MA20"].iloc[-2]
        prev_ma50 = df["MA50"].iloc[-2]
        if not pd.isna(prev_ma20) and not pd.isna(prev_ma50):
            if prev_ma20 <= prev_ma50 and latest["MA20"] > latest["MA50"]:
                buy_score += 2
                reasons_buy.append("MA20 cắt lên MA50 (Golden Cross ngắn hạn)")
            elif prev_ma20 >= prev_ma50 and latest["MA20"] < latest["MA50"]:
                sell_score += 2
                reasons_sell.append("MA20 cắt xuống MA50 (Death Cross ngắn hạn)")

    if "MA50" in df.columns and "MA200" in df.columns and len(df) > 1:
        prev_ma50 = df["MA50"].iloc[-2]
        prev_ma200 = df["MA200"].iloc[-2]
        if not pd.isna(prev_ma50) and not pd.isna(prev_ma200):
            if prev_ma50 <= prev_ma200 and latest["MA50"] > latest["MA200"]:
                buy_score += 2
                reasons_buy.append("MA50 cắt lên MA200 (Golden Cross dài hạn)")
            elif prev_ma50 >= prev_ma200 and latest["MA50"] < latest["MA200"]:
                sell_score += 2
                reasons_sell.append("MA50 cắt xuống MA200 (Death Cross dài hạn)")

    # ---- ICHIMOKU TENKAN/KIJUN CROSSOVER ----
    if "Ichimoku_Tenkan" in df.columns and "Ichimoku_Kijun" in df.columns and len(df) > 1:
        prev_tenkan = df["Ichimoku_Tenkan"].iloc[-2]
        prev_kijun = df["Ichimoku_Kijun"].iloc[-2]
        if not pd.isna(prev_tenkan) and not pd.isna(prev_kijun):
            if prev_tenkan <= prev_kijun and latest["Ichimoku_Tenkan"] > latest["Ichimoku_Kijun"]:
                buy_score += 1
                reasons_buy.append("Tenkan cắt lên Kijun (tín hiệu mua Ichimoku)")
            elif prev_tenkan >= prev_kijun and latest["Ichimoku_Tenkan"] < latest["Ichimoku_Kijun"]:
                sell_score += 1
                reasons_sell.append("Tenkan cắt xuống Kijun (tín hiệu bán Ichimoku)")

    # ---- CMF (CHAIKIN MONEY FLOW) ----
    if "CMF" in df.columns:
        if latest["CMF"] > 0.1:
            buy_score += 1
            reasons_buy.append(f"CMF={latest['CMF']:.3f} (dòng tiền vào mạnh)")
        elif latest["CMF"] < -0.1:
            sell_score += 1
            reasons_sell.append(f"CMF={latest['CMF']:.3f} (dòng tiền ra mạnh)")

    # ---- OBV TREND CONFIRMATION ----
    if "OBV" in df.columns and "OBV_MA" in df.columns:
        if latest["OBV"] > latest["OBV_MA"]:
            buy_score += 1
            reasons_buy.append("OBV trên MA (xác nhận đà tăng)")
        elif latest["OBV"] < latest["OBV_MA"]:
            sell_score += 1
            reasons_sell.append("OBV dưới MA (xác nhận đà giảm)")

    # ---- FORCE INDEX ----
    if "Force_Index_EMA" in df.columns:
        if latest["Force_Index_EMA"] > 0:
            buy_score += 1
            reasons_buy.append("Force Index dương (lực mua)")
        elif latest["Force_Index_EMA"] < 0:
            sell_score += 1
            reasons_sell.append("Force Index âm (lực bán)")

    # ---- VOLUME-PRICE CORRELATION ----
    if "Volume_Price_Corr" in df.columns and not pd.isna(latest["Volume_Price_Corr"]):
        if latest["Volume_Price_Corr"] > 0.3:
            buy_score += 1
            reasons_buy.append(f"Volume-Price Corr={latest['Volume_Price_Corr']:.2f} (xác nhận trend)")
        elif latest["Volume_Price_Corr"] < -0.3:
            sell_score += 1
            reasons_sell.append(f"Volume-Price Corr={latest['Volume_Price_Corr']:.2f} (phân kỳ)")

    # ---- WAVE TREND ----
    if "Wave_High" in df.columns and "Wave_Low" in df.columns and len(df) > 10:
        recent_waves = df.dropna(subset=["Wave_High", "Wave_Low"]).tail(20)
        if len(recent_waves) >= 6:
            wave_highs = recent_waves[recent_waves["Wave_High"] == recent_waves["Close"]]["Wave_High"].values
            wave_lows = recent_waves[recent_waves["Wave_Low"] == recent_waves["Close"]]["Wave_Low"].values
            if len(wave_highs) >= 2 and len(wave_lows) >= 2:
                if wave_highs[-1] > wave_highs[-2] and wave_lows[-1] > wave_lows[-2]:
                    buy_score += 1
                    reasons_buy.append("Sóng: đỉnh và đáy đều cao hơn")
                elif wave_highs[-1] < wave_highs[-2] and wave_lows[-1] < wave_lows[-2]:
                    sell_score += 1
                    reasons_sell.append("Sóng: đỉnh và đáy đều thấp hơn")

    # ---- VOLUME SPIKE ----
    if "Volume_MA20" in df.columns and latest["Volume_MA20"] > 0:
        vol_ratio = latest["Volume"] / latest["Volume_MA20"]
        if vol_ratio > 2 and current_price > latest["Open"]:
            buy_score += 1
            reasons_buy.append(f"Volume spike {vol_ratio:.1f}x + giá tăng")
        elif vol_ratio > 2 and current_price < latest["Open"]:
            sell_score += 1
            reasons_sell.append(f"Volume spike {vol_ratio:.1f}x + giá giảm")

    net_score = buy_score - sell_score

    if net_score >= 3:
        signal = "MUA MẠNH"
        entry = current_price
        stop_loss = current_price - (atr * atr_multiplier)
        take_profit = current_price + (atr * atr_multiplier * 2)
    elif net_score >= 1:
        signal = "MUA NHẸ"
        entry = current_price * 0.99
        stop_loss = current_price - (atr * atr_multiplier)
        take_profit = current_price + (atr * atr_multiplier * 1.5)
    elif net_score <= -3:
        signal = "BÁN MẠNH"
        entry = current_price
        stop_loss = current_price + (atr * atr_multiplier)
        take_profit = current_price - (atr * atr_multiplier * 2)
    elif net_score <= -1:
        signal = "BÁN NHẸ"
        entry = current_price
        stop_loss = current_price + (atr * atr_multiplier)
        take_profit = current_price - (atr * atr_multiplier * 1.5)
    else:
        signal = "TRUNG TÍNH - CHỜ"
        entry = None
        stop_loss = None
        take_profit = None

    support_levels = _find_support_resistance(df, "support")
    resistance_levels = _find_support_resistance(df, "resistance")

    return {
        "signal": signal,
        "net_score": net_score,
        "buy_score": buy_score,
        "sell_score": sell_score,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "reasons_buy": reasons_buy,
        "reasons_sell": reasons_sell,
        "current_price": current_price,
        "atr": atr,
        "support": support_levels,
        "resistance": resistance_levels,
    }


def _find_support_resistance(df: pd.DataFrame, mode: str) -> list[float]:
    """Tìm các vùng hỗ trợ/kháng cự."""
    recent = df.tail(60)
    levels = []

    if mode == "support":
        lows = recent[recent["Low"] == recent["Low"].rolling(5, center=True).min()]
        levels = sorted(lows["Low"].unique())[-3:]
    else:
        highs = recent[recent["High"] == recent["High"].rolling(5, center=True).max()]
        levels = sorted(highs["High"].unique())[-3:]

    return [round(float(l), 0) for l in levels if not np.isnan(l)]


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Thêm tất cả indicators."""
    df = add_moving_averages(df)
    df = add_exponential_moving_averages(df)
    df = add_bollinger_bands(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_stochastic(df)
    df = add_ichimoku(df)
    df = add_atr(df)
    df = add_volume_indicators(df)
    df = add_money_flow(df)
    df = detect_waves(df)
    return df
