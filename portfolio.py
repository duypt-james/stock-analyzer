import json
import os
from datetime import datetime

import streamlit as st

_PORTFOLIO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "my_watchlist.json")
_STATE_KEY = "portfolio_data"


def _get_state() -> dict:
    if _STATE_KEY not in st.session_state:
        st.session_state[_STATE_KEY] = _load_file()
    return st.session_state[_STATE_KEY]


def _load_file() -> dict:
    if os.path.exists(_PORTFOLIO_FILE):
        try:
            with open(_PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    st.session_state[_STATE_KEY] = data
    try:
        with open(_PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_watchlist() -> dict:
    """Trả về dict ticker -> thông tin theo dõi (lưu trong phiên, best-effort ra file)."""
    return _get_state().get("watchlist", {})


def add_to_watchlist(ticker: str, stop_loss: float = None, take_profit: float = None, note: str = "") -> dict:
    data = _get_state()
    watch = data.get("watchlist", {})
    ticker = ticker.strip().upper().replace(".VN", "").replace(".vn", "")
    watch[ticker] = {
        "added": datetime.now().isoformat(),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "note": note,
    }
    data["watchlist"] = watch
    _save(data)
    return watch


def remove_from_watchlist(ticker: str) -> dict:
    data = _get_state()
    watch = data.get("watchlist", {})
    ticker = ticker.strip().upper().replace(".VN", "").replace(".vn", "")
    watch.pop(ticker, None)
    data["watchlist"] = watch
    _save(data)
    return watch


def update_watchlist(ticker: str, stop_loss: float = None, take_profit: float = None, note: str = "") -> dict:
    data = _get_state()
    watch = data.get("watchlist", {})
    ticker = ticker.strip().upper().replace(".VN", "").replace(".vn", "")
    if ticker in watch:
        watch[ticker]["stop_loss"] = stop_loss
        watch[ticker]["take_profit"] = take_profit
        watch[ticker]["note"] = note
        data["watchlist"] = watch
        _save(data)
    return watch


def get_last_ticker() -> str:
    """Mã cổ phiếu đang xem gần nhất (lưu trong phiên, best-effort ra file)."""
    data = _get_state()
    return data.get("settings", {}).get("last_ticker", "FPT")


def set_last_ticker(ticker: str) -> str:
    """Lưu mã cổ phiếu đang xem gần nhất."""
    data = _get_state()
    settings = data.get("settings", {})
    t = ticker.strip().upper().replace(".VN", "").replace(".vn", "")
    if t:
        settings["last_ticker"] = t
    data["settings"] = settings
    _save(data)
    return t
