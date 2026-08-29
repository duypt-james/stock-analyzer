import requests
import json
import os
import pandas as pd
from datetime import datetime, timedelta

FIREANT_API = "https://api.fireant.vn"
TOKEN_FILE = "fireant_token.json"


def login(email: str, password: str) -> dict:
    """Dang nhap FireAnt va lay token."""
    url = f"{FIREANT_API}/authentication/login"
    payload = {
        "email": email,
        "password": password,
        "rememberMe": True
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get("succeeded"):
                token = data.get("accessToken")
                refresh = data.get("refreshToken")
                if token:
                    save_token(token, refresh)
                    return {"success": True, "token": token, "message": "Dang nhap thanh cong!"}
                else:
                    return {"success": False, "message": "Khong co token trong phan hoi!"}
            else:
                error_msg = data.get("errorMessage") or "Sai email hoac mat khau!"
                return {"success": False, "message": error_msg}
        elif r.status_code == 401:
            return {"success": False, "message": "Sai email hoac mat khau!"}
        else:
            return {"success": False, "message": f"Loi {r.status_code}: {r.text[:200]}"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Khong ket noi duoc voi FireAnt!"}
    except requests.exceptions.Timeout:
        return {"success": False, "message": "Het thoi gian ket noi!"}
    except Exception as e:
        return {"success": False, "message": f"Loi: {str(e)}"}


def save_token(token: str, refresh_token: str = None):
    """Luu token vao file."""
    data = {
        "token": token,
        "refresh_token": refresh_token,
        "saved_at": datetime.now().isoformat()
    }
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)


def load_token() -> str:
    """Tai token tu file."""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
            return data.get("token")
        except Exception:
            return None
    return None


def logout():
    """Xoa token."""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def refresh_access_token(refresh_token: str) -> dict:
    """Lam moi token."""
    url = f"{FIREANT_API}/authentication/refresh-token"
    payload = {"refreshToken": refresh_token}
    headers = {"Content-Type": "application/json"}
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            token = data.get("token") or data.get("accessToken")
            if token:
                new_refresh = data.get("refreshToken") or data.get("refresh_token") or refresh_token
                save_token(token, new_refresh)
                return {"success": True, "token": token}
        return {"success": False}
    except Exception:
        return {"success": False}


# ===================== FIREALNT DATA =====================

def get_fireant_historical(symbol: str, days: int = 365) -> pd.DataFrame:
    """Lay lich su gia tu FireAnt."""
    token = load_token()
    if not token:
        return pd.DataFrame()
    
    headers = {"Authorization": f"Bearer {token}"}
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    url = f"{FIREANT_API}/symbols/{symbol}/historical-quotes?startDate={start_date}&endDate={end_date}"
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data:
                df = pd.DataFrame(data)
                df["date"] = pd.to_datetime(df["date"])
                df = df.rename(columns={
                    "priceOpen": "Open",
                    "priceHigh": "High",
                    "priceLow": "Low",
                    "priceClose": "Close",
                    "totalVolume": "Volume",
                    "priceBasic": "PrevClose",
                    "priceAverage": "AvgPrice",
                    "buyForeignValue": "BuyForeign",
                    "sellForeignValue": "SellForeign",
                    "currentForeignRoom": "ForeignRoom"
                })
                df = df.set_index("date")
                return df[["Open", "High", "Low", "Close", "Volume", "PrevClose", "AvgPrice", "BuyForeign", "SellForeign", "ForeignRoom"]]
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def get_fireant_realtime(symbol: str) -> dict:
    """Lay gia real-time (lay gia dong cua ngay hom nay tu historical)."""
    token = load_token()
    if not token:
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{FIREANT_API}/symbols/{symbol}/historical-quotes?startDate={today}&endDate={today}"
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data:
                latest = data[-1]
                return {
                    "price": latest.get("priceClose"),
                    "open": latest.get("priceOpen"),
                    "high": latest.get("priceHigh"),
                    "low": latest.get("priceLow"),
                    "volume": latest.get("totalVolume"),
                    "prev_close": latest.get("priceBasic"),
                    "avg": latest.get("priceAverage"),
                    "buy_foreign": latest.get("buyForeignValue"),
                    "sell_foreign": latest.get("sellForeignValue"),
                    "foreign_room": latest.get("currentForeignRoom"),
                }
    except Exception:
        pass
    return None
