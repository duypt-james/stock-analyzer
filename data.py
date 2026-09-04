import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from vnstock.api.quote import Quote
from vnstock.explorer.kbs.trading import Trading as _KBS_Trading
import streamlit as st
import time


_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".data_cache")
_CACHE_OK = True

_last_call = 0.0


def _throttle(min_interval: float = 1.0):
    """Giới hạn tốc độ gọi API: chờ ít nhất min_interval giây giữa các lần gọi."""
    global _last_call
    now = time.time()
    wait = min_interval - (now - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()


def _cache_path(key: str) -> str:
    global _CACHE_OK
    if not _CACHE_OK:
        return ""
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        return os.path.join(_CACHE_DIR, key + ".parquet")
    except Exception:
        _CACHE_OK = False
        return ""


def _read_cache(key: str, ttl: int):
    path = _cache_path(key)
    if path:
        try:
            if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < ttl:
                df = pd.read_parquet(path)
                if not df.empty:
                    return df
        except Exception:
            pass
    return None


def _write_cache(key: str, df: pd.DataFrame):
    path = _cache_path(key)
    if path:
        try:
            if not df.empty:
                df.to_parquet(path)
        except Exception:
            pass


def _clear_cache():
    global _CACHE_OK
    _CACHE_OK = True
    try:
        if os.path.isdir(_CACHE_DIR):
            for f in os.listdir(_CACHE_DIR):
                os.remove(os.path.join(_CACHE_DIR, f))
    except Exception:
        pass


def force_refresh():
    """Xoá toàn bộ cache (disk + streamlit) để lần truy cập kế lấy dữ liệu mới nhất."""
    global _CACHE_OK
    _CACHE_OK = True
    _clear_cache()
    try:
        st.cache_data.clear()
    except Exception:
        pass


@st.cache_data(ttl=4, show_spinner=False)
def get_realtime_board(symbols: tuple) -> dict:
    """Bảng giá REAL-TIME cho cả rổ mã (1 request duy nhất qua KBS price_board).

    Trả về dict {SYMBOL: {price, change, pct, open, high, low, vol, time, ref, bid1, ask1}}.
    Giá là giá khớp lệnh hiện tại (close_price) từ bảng giá realtime, cập nhật mỗi ~4-5s.
    Trong/ngoài giờ giao dịch đều trả về phiên gần nhất.
    """
    try:
        _throttle(0.8)
        board_df = _KBS_Trading().price_board(list(symbols), get_all=False)
        if board_df is None or board_df.empty:
            return {}
        out = {}
        for _, r in board_df.iterrows():
            sym = str(r.get("symbol", "")).upper()
            if not sym:
                continue

            def num(key):
                v = r.get(key)
                try:
                    return float(v) if v is not None and not pd.isna(v) else None
                except (TypeError, ValueError):
                    return None

            out[sym] = {
                "price": num("close_price"),
                "ref": num("reference_price"),
                "change": num("price_change"),
                "pct": num("percent_change"),
                "open": num("open_price"),
                "high": num("high_price"),
                "low": num("low_price"),
                "vol": num("volume_accumulated"),
                "bid1": num("bid_price_1"),
                "ask1": num("ask_price_1"),
                "time": r.get("time", None),
                "update": time.time(),
            }
        return out
    except Exception:
        return {}


VNINDEX_STOCKS = {
    "VCB": 0.18, "FPT": 0.14, "HPG": 0.10, "VHM": 0.09, "TCB": 0.08,
    "VIC": 0.07, "MBB": 0.05, "MWG": 0.05, "MSN": 0.05, "VRE": 0.04,
    "GAS": 0.04, "PLX": 0.03, "CTG": 0.03, "VPB": 0.03, "SHB": 0.02,
    "SSI": 0.02, "VND": 0.02, "STB": 0.02, "ACB": 0.02, "POW": 0.02,
}

PERIOD_DAYS = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}


def _to_vnstock_symbol(ticker: str) -> str:
    return ticker.replace(".VN", "").replace(".vn", "")


@st.cache_data(ttl=21600, show_spinner=False)
def get_stock_data(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    cache_key = f"stock_{_to_vnstock_symbol(ticker)}_{period}"
    cached = _read_cache(cache_key, ttl=21600)  # cache 6 phút
    if cached is not None:
        return cached

    days = PERIOD_DAYS.get(period, 365)
    symbol = _to_vnstock_symbol(ticker)
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")

    for attempt in range(3):
        try:
            _throttle()
            q = Quote(symbol=symbol, source="KBS")
            df = q.history(start=start, end=end)
            if not df.empty:
                df["time"] = pd.to_datetime(df["time"])
                df = df.set_index("time")
                df.columns = [c.capitalize() for c in df.columns]
                result = df[["Open", "High", "Low", "Close", "Volume"]]
                _write_cache(cache_key, result)
                return result
        except Exception:
            pass
        time.sleep(1)
    return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def get_realtime_price(ticker: str) -> dict:
    symbol = _to_vnstock_symbol(ticker)
    today = datetime.now().strftime("%Y-%m-%d")
    prev = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    try:
        q = Quote(symbol=symbol, source="KBS")
        df = q.history(start=prev, end=today)
        if not df.empty and len(df) >= 2:
            latest = df.iloc[-1]
            prev_close = df.iloc[-2]["close"]
            return {
                "price": float(latest["close"]),
                "open": float(latest["open"]),
                "high": float(latest["high"]),
                "low": float(latest["low"]),
                "volume": int(latest["volume"]),
                "prev_close": float(prev_close),
                "avg": float((latest["high"] + latest["low"] + latest["close"]) / 3),
            }
    except Exception:
        pass
    return None


def search_vietnam_stocks() -> list[str]:
    return [
        "FPT.VN", "VNM.VN", "VHM.VN", "VIC.VN", "VRE.VN",
        "HPG.VN", "MSN.VN", "MWG.VN", "VCB.VN", "CTG.VN",
        "TCB.VN", "MBB.VN", "VPB.VN", "SHB.VN", "STB.VN",
        "GAS.VN", "PLX.VN", "POW.VN", "NT2.VN", "VSH.VN",
        "SSI.VN", "HCM.VN", "VND.VN", "BSI.VN", "PAN.VN",
        "BCM.VN", "BWE.VN", "DIG.VN", "NVL.VN", "DPR.VN",
        "DPM.VN", "DXG.VN", "DBC.VN", "GMD.VN", "GVR.VN",
        "HDG.VN", "KBC.VN", "KDH.VN", "PNJ.VN", "REE.VN",
        "SBT.VN", "TPB.VN", "VJC.VN", "VTP.VN", "ACB.VN",
        "EIB.VN", "LPB.VN", "VGC.VN",
    ]


def normalize_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if ticker.endswith(".VN"):
        return ticker
    if "." in ticker:
        return ticker
    return ticker + ".VN"


@st.cache_data(ttl=21600, show_spinner=False)
def get_vnindex(period: str = "1y") -> pd.DataFrame:
    """Lấy dữ liệu chỉ số VNINDEX thực, lần lượt thử qua nhiều nguồn dữ liệu."""
    cache_key = f"vnindex_{period}"
    cached = _read_cache(cache_key, ttl=21600)  # cache 6 giờ
    if cached is not None:
        return cached

    days = PERIOD_DAYS.get(period, 365)
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")

    for source in ("VCI", "KBS", "DnSE"):
        for attempt in range(2):
            try:
                _throttle()
                q = Quote(symbol="VNINDEX", source=source)
                df = q.history(start=start, end=end)
                if not df.empty:
                    df["time"] = pd.to_datetime(df["time"])
                    df = df.set_index("time")
                    df.columns = [c.capitalize() for c in df.columns]
                    result = df[["Open", "High", "Low", "Close", "Volume"]]
                    _write_cache(cache_key, result)
                    return result
            except Exception:
                pass
            time.sleep(1)
    return pd.DataFrame()


def get_market_index(period: str = "1y") -> pd.DataFrame:
    days = PERIOD_DAYS.get(period, 365)
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    all_data = {}

    for symbol, weight in VNINDEX_STOCKS.items():
        try:
            q = Quote(symbol=symbol, source="KBS")
            df = q.history(start=start, end=end)
            if not df.empty:
                df["time"] = pd.to_datetime(df["time"])
                df = df.set_index("time")
                all_data[symbol] = {"close": df["close"], "weight": weight}
        except Exception:
            continue

    if not all_data:
        return pd.DataFrame()

    normalized = {}
    for symbol, data in all_data.items():
        close = data["close"]
        first_valid = close.first_valid_index()
        if first_valid is not None:
            base = close.loc[first_valid]
            if base > 0:
                normalized[symbol] = (close / base) * 1000 * data["weight"]

    if not normalized:
        return pd.DataFrame()

    prices = pd.DataFrame(normalized).dropna(how="all")
    total_weight = sum(VNINDEX_STOCKS[t] for t in prices.columns)

    index_df = pd.DataFrame(index=prices.index)
    index_df["Close"] = prices.sum(axis=1) / total_weight * 1000
    index_df["Open"] = index_df["Close"].shift(1).fillna(index_df["Close"])
    index_df["High"] = index_df[["Open", "Close"]].max(axis=1) * 1.002
    index_df["Low"] = index_df[["Open", "Close"]].min(axis=1) * 0.998
    index_df["Volume"] = 0
    return index_df


def get_market_status(index_df: pd.DataFrame) -> dict:
    if index_df.empty or len(index_df) < 50:
        return {
            "trend": "KHÔNG RÕ", "strength": 0,
            "description": "Không đủ dữ liệu thị trường.",
            "recommendation": "TRUNG TÍNH",
            "pct_5d": 0, "pct_20d": 0,
            "current": 0, "ma20": 0, "ma50": 0,
        }

    close = index_df["Close"]
    ma5 = close.rolling(5).mean().iloc[-1]
    ma20 = close.rolling(20).mean().iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1]
    current = close.iloc[-1]

    pct_5d = (current - close.iloc[-6]) / close.iloc[-6] * 100 if len(close) > 5 else 0
    pct_20d = (current - close.iloc[-21]) / close.iloc[-21] * 100 if len(close) > 20 else 0

    score = 0
    if current > ma5: score += 1
    else: score -= 1
    if current > ma20: score += 1
    else: score -= 1
    if current > ma50: score += 1
    else: score -= 1
    if ma5 > ma20: score += 1
    else: score -= 1
    if ma20 > ma50: score += 1
    else: score -= 1
    if pct_5d > 2: score += 1
    elif pct_5d < -2: score -= 1

    if score >= 3:
        trend, recommendation = "TĂNG MẠNH", "THUẬN LỢI - Nên mua cổ phiếu cơ bản tốt"
    elif score >= 1:
        trend, recommendation = "TĂNG NHẸ", "CÓ THỂ MUA - Chọn lọc kỹ"
    elif score <= -3:
        trend, recommendation = "GIẢM MẠNH", "CẢNH TRỌNG - Nên đứng ngoài hoặc bán"
    elif score <= -1:
        trend, recommendation = "GIẢM NHẸ", "THẬN TRỌNG - Giảm vị thế"
    else:
        trend, recommendation = "ĐI NGANG", "TRUNG TÍNH - Chờ tín hiệu rõ hơn"

    return {
        "trend": trend, "strength": score, "max_strength": 6,
        "recommendation": recommendation,
        "pct_5d": pct_5d, "pct_20d": pct_20d,
        "current": current, "ma20": ma20, "ma50": ma50,
    }
