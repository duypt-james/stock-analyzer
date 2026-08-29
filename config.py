import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _get_secret(name: str) -> str:
    """Đọc giá trị bí mật theo thứ tự: Streamlit secrets -> biến môi trường."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, "")


def get_api_key() -> str:
    """API key vnstock, đọc từ secrets/env (VNSTOCK_API_KEY)."""
    return _get_secret("VNSTOCK_API_KEY").strip()


def get_app_password() -> str:
    """Mật khẩu đăng nhập app, đọc từ secrets/env (APP_PASSWORD)."""
    return _get_secret("APP_PASSWORD").strip()


def is_protected() -> bool:
    """App có được bảo vệ bằng mật khẩu hay không."""
    return bool(get_app_password())
