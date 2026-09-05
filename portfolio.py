import json
import os
from datetime import datetime

import requests
import streamlit as st

_PORTFOLIO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "my_watchlist.json")
_STATE_KEY = "portfolio_data"
_RT_KEY = "portfolio_last_remote_fetch"

# Cấu hình GitHub Gist (lưu vĩnh viễn trên cloud — vì đĩa Streamlit Cloud là tạm thời).
_GIST_DESC = "vnstock-watchlist"
_GIST_FILE = "watchlist.json"
_GIST_TTL = 60  # giây giữa các lần đọc Gist (tránh vượt rate-limit 5000/h)


# ---------------------------------------------------------------------------
# Gist (GitHub) backend - best effort
# ---------------------------------------------------------------------------
def _github_token() -> str:
    try:
        from config import get_github_token
        return get_github_token().strip()
    except Exception:
        return ""


def _gist_headers():
    tok = _github_token()
    if not tok:
        return None
    return {
        "Authorization": f"token {tok}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _find_gist_id(login: str, headers: dict):
    """Tìm gist của user có description = _GIST_DESC. Trả id hoặc None."""
    try:
        r = requests.get(f"https://api.github.com/users/{login}/gists?per_page=100",
                         headers=headers, timeout=8)
        if r.status_code != 200:
            return None
        for g in r.json():
            if (g or {}).get("description") == _GIST_DESC and _GIST_FILE in ((g.get("files") or {})):
                return g["id"]
    except Exception:
        pass
    return None


def _fetch_remote() -> dict:
    """Đọc toàn bộ dữ liệu (watchlist + settings) từ Gist. {} nếu lỗi/không có."""
    h = _gist_headers()
    if not h:
        return {}
    try:
        me = requests.get("https://api.github.com/user", headers=h, timeout=8)
        if me.status_code != 200:
            return {}
        login = me.json().get("login", "")
        if not login:
            return {}
        gid = _find_gist_id(login, h)
        if not gid:
            return {}
        g = requests.get(f"https://api.github.com/gists/{gid}", headers=h, timeout=8)
        if g.status_code != 200:
            return {}
        raw = (g.json().get("files") or {}).get(_GIST_FILE, {}).get("content", "")
        if not raw:
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _push_remote(data: dict) -> bool:
    """Tạo hoặc cập nhật gist chứa toàn bộ dữ liệu. True nếu thành công."""
    h = _gist_headers()
    if not h:
        return False
    payload = {_GIST_FILE: {"content": json.dumps(data, ensure_ascii=False, indent=2)}}
    try:
        me = requests.get("https://api.github.com/user", headers=h, timeout=8)
        if me.status_code != 200:
            return False
        login = me.json().get("login", "")
        if not login:
            return False
        gid = _find_gist_id(login, h)
        if gid:
            r = requests.patch(f"https://api.github.com/gists/{gid}", headers=h,
                               json={"files": payload}, timeout=10)
        else:
            r = requests.post("https://api.github.com/gists", headers=h,
                              json={"description": _GIST_DESC, "public": False, "files": payload},
                              timeout=10)
        return r.status_code in (200, 201)
    except Exception:
        return False


def _remote_due() -> bool:
    """Chỉ đọc Gist nếu lần đọc gần nhất đã cách > _GIST_TTL giây."""
    last = st.session_state.get(_RT_KEY, 0)
    return (datetime.now().timestamp() - last) > _GIST_TTL


# ---------------------------------------------------------------------------
# Lưu trữ chính: file local (cache) + Gist (bền vững trên cloud)
# ---------------------------------------------------------------------------
def _get_state() -> dict:
    if _STATE_KEY not in st.session_state:
        st.session_state[_STATE_KEY] = _load_file()
    return st.session_state[_STATE_KEY]


def _load_file() -> dict:
    """Ưu tiên dữ liệu Gist (bền vững) khi có token; nếu không có thì dùng file local."""
    data = {}
    if os.path.exists(_PORTFOLIO_FILE):
        try:
            with open(_PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        except Exception:
            pass

    if _github_token() and _remote_due():
        st.session_state[_RT_KEY] = datetime.now().timestamp()
        remote = _fetch_remote()
        if remote:
            data = remote
            _write_local(data)

    return data


def _write_local(data: dict):
    try:
        with open(_PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _save(data: dict):
    st.session_state[_STATE_KEY] = data
    _write_local(data)
    # Đồng bộ lên Gist nếu có token (best effort, không gây lỗi nếu thất bại).
    if _github_token():
        _push_remote(data)


# ---------------------------------------------------------------------------
# API cho các tab
# ---------------------------------------------------------------------------
def is_persistent_remote() -> bool:
    """Có lưu trữ bền vững (Gist) hay không."""
    return bool(_github_token())


def get_watchlist() -> dict:
    """Trả về dict ticker -> thông tin theo dõi."""
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
    """Mã cổ phiếu đang xem gần nhất."""
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