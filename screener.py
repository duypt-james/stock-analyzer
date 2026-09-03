import pandas as pd
import numpy as np

from indicators import add_all_indicators, suggest_entry_points, analyze_wave_trend


def analyze_stock(df: pd.DataFrame, market_status: dict = None) -> dict:
    """Trả về phân tích kỹ thuật đầy đủ của một cổ phiếu để dùng cho màn lọc & theo dõi."""
    if df is None or df.empty or len(df) < 30:
        return {"ok": False, "reason": "Không đủ dữ liệu"}

    ind = add_all_indicators(df.copy())
    if len(ind) < 20 or pd.isna(ind["Close"].iloc[-1]):
        return {"ok": False, "reason": "Dữ liệu không hợp lệ"}

    entry_info = suggest_entry_points(ind, market_status=market_status)
    wave = analyze_wave_trend(ind)
    latest = ind.iloc[-1]

    current_price = float(latest["Close"])
    ma20 = float(latest["MA20"]) if not pd.isna(latest["MA20"]) else None
    ma50 = float(latest["MA50"]) if not pd.isna(latest["MA50"]) else None
    ma200 = float(latest["MA200"]) if "MA200" in ind.columns and not pd.isna(latest["MA200"]) else None
    rsi = float(latest["RSI"]) if not pd.isna(latest["RSI"]) else None
    mfi = float(latest["MFI"]) if "MFI" in ind.columns and not pd.isna(latest["MFI"]) else None
    stoch_k = float(latest["Stoch_K"]) if not pd.isna(latest["Stoch_K"]) else None
    macd = float(latest["MACD"]) if not pd.isna(latest["MACD"]) else None
    macd_h = float(latest["MACD_Histogram"]) if not pd.isna(latest["MACD_Histogram"]) else None
    cmf = float(latest["CMF"]) if not pd.isna(latest["CMF"]) else None
    atr = float(latest["ATR"]) if not pd.isna(latest["ATR"]) else None
    vol_ma20 = float(latest["Volume_MA20"]) if not pd.isna(latest["Volume_MA20"]) else None
    vol_ratio = float(latest["Volume"] / vol_ma20) if vol_ma20 and vol_ma20 > 0 else None

    pct_1d = (current_price - float(df["Close"].iloc[-2])) / float(df["Close"].iloc[-2]) * 100 if len(df) > 1 else 0.0
    pct_5d = (current_price - float(df["Close"].iloc[-6])) / float(df["Close"].iloc[-6]) * 100 if len(df) > 5 else 0.0
    pct_20d = (current_price - float(df["Close"].iloc[-21])) / float(df["Close"].iloc[-21]) * 100 if len(df) > 20 else 0.0

    # Điểm cơ hội (0-100) để xếp hạng
    net = entry_info["net_score"]
    buy = entry_info["buy_score"]
    sell = entry_info["sell_score"]
    score_100 = int(round(50 + (net * 10)))

    near_low = float(latest["BB_Lower"]) if not pd.isna(latest["BB_Lower"]) else None
    near_high = float(latest["BB_Upper"]) if not pd.isna(latest["BB_Upper"]) else None

    return {
        "ok": True,
        "signal": entry_info["signal"],
        "net_score": net,
        "buy_score": buy,
        "sell_score": sell,
        "score_100": max(0, min(100, score_100)),
        "current_price": current_price,
        "entry": entry_info["entry"],
        "stop_loss": entry_info["stop_loss"],
        "take_profit": entry_info["take_profit"],
        "reasons_buy": entry_info["reasons_buy"],
        "reasons_sell": entry_info["reasons_sell"],
        "support": entry_info["support"],
        "resistance": entry_info["resistance"],
        "atr": atr,
        "rsi": rsi, "mfi": mfi, "stoch_k": stoch_k,
        "macd": macd, "macd_h": macd_h, "cmf": cmf,
        "ma20": ma20, "ma50": ma50, "ma200": ma200,
        "vol_ratio": vol_ratio,
        "pct_1d": pct_1d, "pct_5d": pct_5d, "pct_20d": pct_20d,
        "wave_trend": wave["trend"],
        "wave_desc": wave["description"],
        "bb_lower": near_low, "bb_upper": near_high,
        "hist": predict_history(df),
    }


def predict_history(df: pd.DataFrame, horizons=(5, 10, 20)) -> dict:
    """Thống kê lịch sử thực tế: sau N phiên, giá thường tăng hay giảm bao nhiêu %.

    Dựa trên DỮ LIỆU QUÁ KHỨ của chính mã (1 năm gần nhất). Đây là MÔ TẢ THỐNG KÊ,
    không phải dự đoán chắc chắn. Trả về dict {n_phiên: {prob_up, avg_return,
    median_return, p10, p90}} (đơn vị % lợi nhuận).
    """
    if df is None or df.empty or len(df) < 40:
        return {}
    closes = df["Close"].astype(float).reset_index(drop=True)
    n = len(closes)
    out = {}
    for h in horizons:
        if n <= h + 20:  # cần đủ số lần quan sát
            continue
        # Với mỗi vị trí i, xem giá sau h phiên tăng/giảm bao nhiêu %
        returns = []
        max_i = n - h
        for i in range(0, max_i):
            a = closes.iloc[i]
            b = closes.iloc[i + h]
            if a and a > 0:
                returns.append((b - a) / a * 100.0)
        if len(returns) < 10:
            continue
        r = np.array(returns)
        prob_up = float(np.mean(r > 0)) * 100.0
        avg_return = float(np.mean(r))
        median_return = float(np.median(r))
        p10 = float(np.percentile(r, 10))
        p90 = float(np.percentile(r, 90))
        out[h] = {
            "prob_up": prob_up,
            "avg_return": avg_return,
            "median_return": median_return,
            "p10": p10,
            "p90": p90,
            "samples": int(len(r)),
        }
    return out


def build_alerts(df: pd.DataFrame, market_status: dict = None, stop_loss: float = None, take_profit: float = None) -> list:
    """Sinh các cảnh báo tăng/giảm dựa trên chỉ số kỹ thuật (so sánh phiên hiện tại với phiên trước)."""
    if df is None or df.empty or len(df) < 2:
        return []

    ind = add_all_indicators(df.copy())
    if len(ind) < 2:
        return []

    latest = ind.iloc[-1]
    prev = ind.iloc[-2]
    price = float(latest["Close"])
    alerts = []

    def has(col):
        return col in ind.columns and not pd.isna(latest[col])

    # 1. Cắt MA20
    if has("MA20") and not pd.isna(prev["MA20"]):
        if latest["MA20"] > prev["MA20"] and price > latest["MA20"] and prev["Close"] <= prev["MA20"]:
            alerts.append(("up", f"Giá vừa cắt LÊN trên MA20 ({latest['MA20']:,.0f}) — tín hiệu mua ngắn hạn."))
        elif latest["MA20"] < prev["MA20"] and price < latest["MA20"] and prev["Close"] >= prev["MA20"]:
            alerts.append(("down", f"Giá vừa cắt XUỐNG dưới MA20 ({latest['MA20']:,.0f}) — tín hiệu bán ngắn hạn."))

    # 2. Cắt MA50
    if has("MA50") and not pd.isna(prev["MA50"]):
        if latest["MA50"] > prev["MA50"] and price > latest["MA50"] and prev["Close"] <= prev["MA50"]:
            alerts.append(("up", f"Giá vừa cắt LÊN trên MA50 ({latest['MA50']:,.0f}) — xu hướng trung hạn chuyển tăng."))
        elif latest["MA50"] < prev["MA50"] and price < latest["MA50"] and prev["Close"] >= prev["MA50"]:
            alerts.append(("down", f"Giá vừa cắt XUỐNG dưới MA50 ({latest['MA50']:,.0f}) — xu hướng trung hạn chuyển giảm."))

    # 3. MACD golden/death cross
    if has("MACD") and has("MACD_Signal"):
        if prev["MACD"] <= prev["MACD_Signal"] and latest["MACD"] > latest["MACD_Signal"]:
            alerts.append(("up", "MACD vừa cắt lên đường Signal (MACD Golden Cross) — đà tăng."))
        elif prev["MACD"] >= prev["MACD_Signal"] and latest["MACD"] < latest["MACD_Signal"]:
            alerts.append(("down", "MACD vừa cắt xuống đường Signal (MACD Death Cross) — đà giảm."))

    # 4. RSI vào vùng quá mua/quá bán
    if has("RSI"):
        if prev["RSI"] <= 30 and latest["RSI"] > 30:
            alerts.append(("up", f"RSI thoát khỏi vùng quá bán ({latest['RSI']:.0f}) — áp lực bán giảm."))
        elif prev["RSI"] >= 30 and latest["RSI"] < 30:
            alerts.append(("down", f"RSI vào vùng quá bán ({latest['RSI']:.0f}) — giá có thể còn giảm nhẹ."))
        if latest["RSI"] >= 70 and prev["RSI"] < 70:
            alerts.append(("down", f"RSI vào vùng quá mua ({latest['RSI']:.0f}) — nguy cơ điều chỉnh."))
        elif latest["RSI"] <= 45 and prev["RSI"] > 45:
            alerts.append(("neutral", f"RSI giảm xuống {latest['RSI']:.0f} — đà tăng đang yếu đi."))

    # 5. Stochastic K/D cross
    if has("Stoch_K") and has("Stoch_D"):
        if prev["Stoch_K"] <= prev["Stoch_D"] and latest["Stoch_K"] > latest["Stoch_D"] and latest["Stoch_K"] < 40:
            alerts.append(("up", f"Stochastic K cắt lên D ({latest['Stoch_K']:.0f}) — tín hiệu mua."))
        elif prev["Stoch_K"] >= prev["Stoch_D"] and latest["Stoch_K"] < latest["Stoch_D"] and latest["Stoch_K"] > 60:
            alerts.append(("down", f"Stochastic K cắt xuống D ({latest['Stoch_K']:.0f}) — tín hiệu bán."))

    # 6. Bollinger
    if has("BB_Lower") and price <= latest["BB_Lower"] and prev["Close"] > prev["BB_Lower"]:
        alerts.append(("up", f"Giá chạm dải dưới Bollinger ({latest['BB_Lower']:,.0f}) — vùng mua tiềm năng."))
    if has("BB_Upper") and price >= latest["BB_Upper"] and prev["Close"] < prev["BB_Upper"]:
        alerts.append(("down", f"Giá chạm dải trên Bollinger ({latest['BB_Upper']:,.0f}) — vùng chốt lời/điều chỉnh."))

    # 7. Khối lượng bất thường
    if has("Volume_MA20") and latest["Volume_MA20"] > 0:
        vr = latest["Volume"] / latest["Volume_MA20"]
        if vr >= 2.0:
            direction = "tăng" if price >= latest["Open"] else "giảm"
            color = "up" if price >= latest["Open"] else "down"
            alerts.append((color, f"Khối lượng đột biến {vr:.1f}x so với trung bình 20 phiên, giá {direction}."))

    # 8. Cắt lỗ / chốt lời
    if stop_loss is not None and price <= stop_loss:
        alerts.append(("down", f"Giá {price:,.0f} chạm/vi phạm mức CẮT LỖ {stop_loss:,.0f} — cân nhắc thoát lệnh."))
    if take_profit is not None and price >= take_profit:
        alerts.append(("up", f"Giá {price:,.0f} đạt mục tiêu CHỐT LỜI {take_profit:,.0f} — cân nhắc chốt lời."))

    # 9. Xu hướng sóng
    if "wave_trend" in str(type(ind)):
        pass
    rec = analyze_wave_trend(ind)
    if rec["trend"] == "GIẢM (Sóng giảm)":
        alerts.append(("down", f"Xu hướng sóng: {rec['trend'].lower()} — khuyến nghị hạn chế mua."))
    elif rec["trend"] == "TĂNG (Sóng tăng)":
        alerts.append(("up", "Xu hướng sóng: tăng (sóng impulse) — khuyến nghị nắm giữ."))

    if market_status and "trend" in market_status:
        if market_status["trend"] in ("TĂNG MẠNH",):
            alerts.append(("neutral", "Thị trường chung đang tăng mạnh — hỗ trợ cho xu hướng mã này."))
        elif market_status["trend"] in ("GIẢM MẠNH",):
            alerts.append(("neutral", "Thị trường chung đang giảm mạnh — áp lực lên mã này."))

    return alerts


def classify_stock(df: pd.DataFrame, market_status: dict = None) -> dict:
    """Đánh giá toàn diện bằng TẤT CẢ các chỉ số kỹ thuật (đơn giản → phức tạp).

    Trả về phân loại xu hướng + mức độ cơ hội mua để lọc chính xác các mã có khả năng tăng.
    """
    if df is None or df.empty or len(df) < 50:
        return {"verdict": "KHÔNG ĐỦ DỮ LIỆU", "trend_score": 0, "opp_score": 0, "confidence": 0, "details": [], "confirms_up": 0, "confirms_down": 0}

    ind = add_all_indicators(df.copy())
    if len(ind) < 50:
        return {"verdict": "KHÔNG ĐỦ DỮ LIỆU", "trend_score": 0, "opp_score": 0, "confidence": 0, "details": [], "confirms_up": 0, "confirms_down": 0}

    latest = ind.iloc[-1]
    price = float(latest["Close"])

    def val(col):
        return float(latest[col]) if col in ind.columns and not pd.isna(latest[col]) else None

    # ---------- CÁC YẾU TỐ XU HƯỚNG (TREND) ----------
    trend_factors = []
    details = []

    def add_t(cond, label, weight, side="up"):
        if cond:
            trend_factors.append((side, weight, label))

    ma20, ma50, ma200 = val("MA20"), val("MA50"), val("MA200")
    ema12, ema26 = val("EMA12"), val("EMA26")
    macd, macd_s, macd_h = val("MACD"), val("MACD_Signal"), val("MACD_Histogram")
    rsi = val("RSI")
    tenkan, kijun = val("Ichimoku_Tenkan"), val("Ichimoku_Kijun")
    senkou_a, senkou_b = val("Ichimoku_Senkou_A"), val("Ichimoku_Senkou_B")
    cmf, obv, obv_ma = val("CMF"), val("OBV"), val("OBV_MA")
    force = val("Force_Index_EMA")
    c1, c2 = val("BB_Upper"), val("BB_Lower")
    vma = val("Volume_MA20")
    vpc = val("Volume_Price_Corr")
    chikou = val("Ichimoku_Chikou")
    stoch_k = val("Stoch_K")
    stoch_d = val("Stoch_D")

    # Cấu trúc giá so với MA
    if ma20: add_t(price > ma20, f"Giá trên MA20 ({ma20:,.0f})", 1)
    if ma50: add_t(price > ma50, f"Giá trên MA50 ({ma50:,.0f})", 1)
    if ma200: add_t(price > ma200, f"Giá trên MA200 ({ma200:,.0f})", 1)
    if ma20 and ma50:
        add_t(ma20 > ma50, f"MA20 ({ma20:,.0f}) nằm trên MA50 ({ma50:,.0f}) — xu hướng ngắn hạn tăng", 1)
        add_t(ma50 > ma20, f"MA20 dưới MA50 — xu hướng ngắn hạn giảm", 1, side="down")
    if ma50 and ma200:
        add_t(ma50 > ma200, f"MA50 trên MA200 — xu hướng dài hạn tăng", 1)
        add_t(ma200 > ma50, f"MA50 dưới MA200 — xu hướng dài hạn giảm", 1, side="down")

    # EMA / MACD
    if ema12 and ema26:
        add_t(ema12 > ema26, f"EMA12 trên EMA26 — đà tăng", 1)
    if macd is not None and macd_s is not None:
        add_t(macd > macd_s, f"MACD trên Signal — đà tăng", 1)
        add_t(macd < macd_s, "MACD dưới Signal — đà giảm", 1, side="down")
        if macd_h is not None:
            add_t(macd_h > 0, f"MACD Histogram dương ({macd_h:.2f})", 0.5)
            add_t(macd_h < 0, "MACD Histogram âm", 0.5, side="down")

    # RSI xu hướng
    if rsi is not None:
        add_t(rsi > 50, f"RSI trên 50 ({rsi:.0f}) — động lượng tăng", 0.75)
        add_t(rsi < 50, f"RSI dưới 50 ({rsi:.0f}) — động lượng giảm", 0.75, side="down")

    # Ichimoku
    cloud_top = max(senkou_a, senkou_b) if (senkou_a is not None and senkou_b is not None) else None
    if cloud_top:
        add_t(price > cloud_top, f"Giá trên đám mây Ichimoku ({cloud_top:,.0f})", 1)
    if tenkan and kijun:
        add_t(tenkan > kijun, f"Tenkan ({tenkan:,.0f}) trên Kijun ({kijun:,.0f}) — xu hướng tăng", 0.75)
        add_t(kijun > tenkan, "Tenkan dưới Kijun — xu hướng giảm", 0.75, side="down")

    # Xu hướng sóng
    wave = analyze_wave_trend(ind)
    if wave["trend"] == "TĂNG (Sóng tăng)":
        add_t(True, "Sóng tăng (impulse) — đỉnh/đáy đều cao hơn", 1)
    elif wave["trend"] == "GIẢM (Sóng giảm)":
        add_t(True, "Sóng giảm (corrective) — đỉnh/đáy đều thấp hơn", 1, side="down")

    # ---------- TÍNH ĐIỂM XU HƯỚNG ----------
    bull_w = sum(w for side, w, _ in trend_factors if side == "up")
    bear_w = sum(w for side, w, _ in trend_factors if side == "down")
    trend_score = 100 * bull_w / (bull_w + bear_w) if (bull_w + bear_w) > 0 else 50
    confirms_up = sum(1 for side, w, _ in trend_factors if side == "up")
    confirms_down = sum(1 for side, w, _ in trend_factors if side == "down")
    in_uptrend = bull_w > bear_w

    # ---------- CƠ HỘI MUA (MOMENTUM + ĐIỂM VÀO) ----------
    opp = 0.0
    opp_details = []

    if rsi is not None:
        if 40 <= rsi <= 65:
            opp += 20; opp_details.append(f"RSI={rsi:.0f} (vùng lý tưởng cho điểm vào, chưa quá mua)")
        elif 30 <= rsi < 45 and in_uptrend:
            opp += 15; opp_details.append(f"RSI={rsi:.0f} (hiếm: nhịp chỉnh trong uptrend)")
    if macd_h is not None and in_uptrend and macd_h > 0:
        opp += 12; opp_details.append(f"MACD Histogram dương ({macd_h:.2f}) — xác nhận đà tăng")
    if cmf is not None:
        if cmf > 0.05: opp += 12; opp_details.append(f"CMF={cmf:.2f} (dòng tiền vào)")
        elif cmf < -0.05: opp -= 8; opp_details.append(f"CMF={cmf:.2f} (dòng tiền ra)")
    if stoch_k is not None and stoch_d is not None:
        if latest["Stoch_K"] > latest["Stoch_D"] and latest["Stoch_K"] < 70:
            opp += 10; opp_details.append(f"Stochastic K>{latest['Stoch_D']:.0f} (trên D, chưa quá mua)")
    if obv is not None and obv_ma is not None:
        if obv > obv_ma: opp += 8; opp_details.append("OBV trên MA — khối lượng xác nhận đà tăng")
    if force is not None and force > 0:
        opp += 6; opp_details.append("Force Index dương (lực mua áp đảo)")
    if vma and latest["Volume"] > 0:
        vr = latest["Volume"] / vma
        if vr >= 1.2 and price >= latest["Open"]:
            opp += 8; opp_details.append(f"Khối lượng {vr:.1f}x trung bình kèm giá tăng")
    if vpc is not None and vpc > 0.2:
        opp += 6; opp_details.append(f"Tương quan giá-khối lượng {vpc:.2f} (xác nhận xu hướng)")
    if c2 is not None and price <= c2 * 1.04 and in_uptrend:
        opp += 10; opp_details.append(f"Giá gần dải dưới Bollinger ({c2:,.0f}) — điểm vào trong uptrend")
    if rsi is not None:
        if rsi > 78: opp -= 25; opp_details.append(f"CẢNH BÁO: RSI={rsi:.0f} quá mua — tránh mua đuổi")
        elif rsi > 70: opp -= 10; opp_details.append(f"RSI={rsi:.0f} vùng quá mua — chờ điều chỉnh")
    if ma20 and price > ma20 * 1.18:
        opp -= 15; opp_details.append(f"Giá cao hơn MA20 {((price/ma20-1)*100):.0f}% — đã giãn quá xa, rủi ro điều chỉnh")

    opp_score = max(0, min(100, opp))

    # ---------- PHÂN LOẠI CUỐI CÙNG ----------
    confidence = int(round(0.6 * trend_score + 0.4 * opp_score))
    should_avoid = (not in_uptrend) or confirms_down > confirms_up
    overbought = (rsi is not None and rsi > 78) or (price > ma20 * 1.18) if ma20 else False

    if should_avoid:
        verdict = "TRÁNH"
        reason = "Xu hướng chưa xác lập / đang giảm — cổ phiếu chưa đủ điều kiện tăng."
    elif confidence >= 72 and not overbought:
        verdict = "CƠ HỘI MẠNH"
        reason = "Xu hướng tăng rõ ràng + điểm vào hợp lý + dòng tiền ủng hộ."
    elif confidence >= 55 and not overbought:
        verdict = "CƠ HỘI"
        reason = "Xu hướng tích cực nhưng chưa mạnh — chọn điểm vào cẩn thận."
    elif in_uptrend:
        verdict = "THEO DÕI"
        reason = "Có xu hướng tăng nhưng điểm vào chưa thuận lợi (chờ nhịp điều chỉnh)."
    else:
        verdict = "TRÁNH"
        reason = "Xu hướng giảm / chưa xác lập — chưa nên mua."

    return {
        "verdict": verdict,
        "reason": reason,
        "trend_score": int(round(trend_score)),
        "opp_score": opp_score,
        "confidence": confidence,
        "in_uptrend": in_uptrend,
        "confirms_up": confirms_up,
        "confirms_down": confirms_down,
        "details": details,
        "opp_details": opp_details,
    }
