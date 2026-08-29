import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

from data import get_stock_data, normalize_ticker, get_market_status, get_vnindex, force_refresh
from indicators import add_all_indicators, suggest_entry_points, analyze_wave_trend, detect_waves
from screener import analyze_stock, build_alerts, classify_stock
import portfolio
import config

st.set_page_config(page_title="Xích Luyện Phố Wall", page_icon="📈", layout="wide")

# ---- Thiết lập API key vnstock (từ secrets/.env, không nhúng vào code) ----
# Chỉ cài đặt MỘT LẦN mỗi phiên để tránh spam log và tránh cạn giới hạn lượt gọi.
_key = config.get_api_key()
if _key:
    try:
        from vnstock.core import setup_api_key
        if "vn_api_ready" not in st.session_state:
            setup_api_key(_key)
            st.session_state.vn_api_ready = True
    except Exception:
        pass

# ---- Trang đăng nhập (bảo vệ bằng mật khẩu nếu đã cấu hình) ----
if config.is_protected():
    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False
    if not st.session_state.auth_ok:
        st.markdown("""
        <div style="display:flex;justify-content:center;align-items:center;min-height:60vh;text-align:center;">
            <div class="section-box" style="max-width:400px;width:100%;padding:30px 24px;">
                <div style="font-size:2.4em;">📈</div>
                <h3 style="margin:8px 0 4px;">Xích Luyện Phố Wall</h3>
                <div style="color:#6b87a8;font-size:0.85em;margin-bottom:18px;">Nhập mật khẩu để tiếp tục</div>
        """, unsafe_allow_html=True)
        pw = st.text_input("Mật khẩu", type="password", key="pw_input")
        if st.button("Đăng nhập", type="primary", use_container_width=True):
            if pw == config.get_app_password():
                st.session_state.auth_ok = True
                st.rerun()
            else:
                st.error("Sai mật khẩu!")
        st.stop()

# CSS Styling - Giao diện xanh lam nhẹ, nội dung sát mép trái
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .block-container { padding: 4.5rem 0.8rem 1rem 0.8rem !important; max-width: 100% !important; }

    /* Header logo + tên tool */
    .app-header { display:flex; align-items:center; gap:12px; margin:0 0 16px 0; padding:10px 14px; background:#ffffff; border:1px solid #cfe2f8; border-radius:10px; box-shadow:0 1px 3px rgba(37,99,235,0.08); overflow:visible; }
    .app-logo { font-size:1.8em; line-height:1; flex-shrink:0; }
    .app-title { font-size:1.3em; font-weight:700; color:#2563eb; line-height:1.3; white-space:normal; }
    .app-sub { font-size:0.74em; color:#6b87a8; line-height:1.4; white-space:normal; }

    /* Thanh chọn tab nằm ngang (segmented control) */
    div[data-testid="stSegmentedControl"] > div { gap: 6px !important; }
    div[data-testid="stSegmentedControl"] button { background:#ffffff; border:1px solid #cfe2f8 !important; border-radius:8px !important; padding:8px 22px !important; font-weight:600 !important; color:#4a6fa5 !important; }
    div[data-testid="stSegmentedControl"] button[aria-checked="true"], div[data-testid="stSegmentedControl"] button:has(div[data-testid="stMarkdownContainer"] > *[aria-checked="true"]) { background:#2563eb !important; color:#ffffff !important; border-color:#2563eb !important; }

    .price-main { font-size: 2.2em; font-weight: 700; color: #1e3a5f; line-height: 1; }
    .price-change { font-size: 1em; font-weight: 600; margin-left: 8px; }
    .price-up { color: #16a34a; }
    .price-down { color: #dc2626; }
    .price-flat { color: #64748b; }
    .section-box { background: #ffffff; border: 1px solid #cfe2f8; border-radius: 8px; padding: 14px; margin: 8px 0; box-shadow: 0 1px 3px rgba(37,99,235,0.08); }
    .section-title { font-size: 0.9em; font-weight: 600; color: #2563eb; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid #dbe7f6; }
    h3 { color: #2563eb !important; font-weight: 700 !important; }
    .signal-badge { display: inline-block; padding: 10px 16px; border-radius: 8px; font-size: 1.1em; font-weight: 700; text-align: center; width: 100%; }
    .badge-buy { background: #e7f7ee; color: #16a34a; border: 1px solid #86e3b3; }
    .badge-sell { background: #fdecec; color: #dc2626; border: 1px solid #f5b5b5; }
    .badge-neutral { background: #fdf6e3; color: #b45309; border: 1px solid #f3d488; }
    .entry-cell { background: #f4f9ff; border-radius: 6px; padding: 10px; text-align: center; border: 1px solid #dbe7f6; height: 100%; }
    .entry-label { color: #6b87a8; font-size: 0.72em; margin-bottom: 3px; }
    .entry-value { font-size: 1.1em; font-weight: 700; }
    .val-green { color: #16a34a; } .val-red { color: #dc2626; } .val-yellow { color: #b45309; } .val-blue { color: #2563eb; }

    /* ===== RESPONSIVE CHO ĐIỆN THOẠI / IPAD ===== */
    @media (max-width: 900px) {
        .block-container { padding: 5.2rem 0.7rem 1rem 0.7rem !important; }
        .app-header { padding: 8px 10px; gap: 8px; }
        .app-title { font-size: 1.05em; }
        .price-main { font-size: 1.6em; }
        .entry-value { font-size: 0.95em; }
        .section-box { padding: 10px; }
    }
    @media (max-width: 600px) {
        .block-container { padding: 6rem 0.6rem 1rem 0.6rem !important; }
        div[data-testid="stVerticalBlock"] > div { gap: 0.4rem !important; }
        div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
        .price-main { font-size: 1.4em; }
        .app-sub { font-size: 0.65em; }
        h3 { font-size: 1.05em !important; }
        .signal-badge { font-size: 0.95em; padding: 8px 10px; }
        .entry-cell { padding: 8px; }
    }
</style>
""", unsafe_allow_html=True)


def get_company_name(symbol: str) -> str:
    names = {
        "VCB": "Ngân hàng TMCP Ngoại thương VN", "FPT": "Tập đoàn FPT", "HPG": "Tập đoàn Hòa Phát",
        "VHM": "Công ty Cổ phần Vinhomes", "VIC": "Tập đoàn Vingroup", "TCB": "Ngân hàng Techcombank",
        "MBB": "Ngân hàng Quân đội (MB)", "MWG": "Công ty CP Đầu tư Thế giới Di động", "MSN": "Tập đoàn Masan",
        "VRE": "Công ty CP Vincom Retail", "GAS": "Tổng Công ty Khí Việt Nam (PV GAS)",
        "PLX": "Tập đoàn Xăng dầu Việt Nam", "CTG": "Ngân hàng VietinBank", "VPB": "Ngân hàng VPBank",
        "VNM": "Công ty CP Sữa Việt Nam (Vinamilk)", "SSI": "Công ty CP Chứng khoán SSI",
        "VND": "Công ty CP Chứng khoán VNDIRECT", "ACB": "Ngân hàng ACB", "STB": "Ngân hàng Sacombank",
        "SHB": "Ngân hàng SHB", "POW": "Tổng Công ty Điện lực Dầu khí VN",
    }
    return names.get(symbol, symbol)


@st.cache_data(ttl=120, show_spinner=False)
def get_cached_stock_data(ticker: str, period: str) -> pd.DataFrame:
    return get_stock_data(ticker, period=period, interval="1d")


@st.cache_data(ttl=600, show_spinner=False)
def load_all_market_data():
    """Tải dữ liệu toàn danh mục kèm chỉ báo chứng minh. Cache 10 phút để ít gọi API."""
    tickers = ["VCB", "FPT", "HPG", "VHM", "TCB", "VIC", "MBB", "MWG", "MSN", "VRE", "GAS", "PLX", "CTG", "VPB", "SHB", "SSI", "VND", "STB", "ACB", "POW"]
    stats_list = []

    for i, t in enumerate(tickers):
        df_t = get_stock_data(t + ".VN", period="3mo", interval="1d")
        if not df_t.empty and len(df_t) >= 15:
            lat = df_t.iloc[-1]
            prev_c = df_t.iloc[-2]["Close"] if len(df_t) > 1 else lat["Close"]
            pct_1d = (lat["Close"] - prev_c) / prev_c * 100 if prev_c > 0 else 0

            c_15d = df_t["Close"].iloc[-15] if len(df_t) >= 15 else df_t["Close"].iloc[0]
            pct_15d = (lat["Close"] - c_15d) / c_15d * 100 if c_15d > 0 else 0

            ind = add_all_indicators(df_t.copy())
            rsi = ind["RSI"].iloc[-1] if "RSI" in ind.columns else np.nan
            stoch = ind["Stoch_K"].iloc[-1] if "Stoch_K" in ind.columns else np.nan
            mfi = ind["MFI"].iloc[-1] if "MFI" in ind.columns else np.nan
            macd_h = ind["MACD_Histogram"].iloc[-1] if "MACD_Histogram" in ind.columns else np.nan
            vol_ma20 = ind["Volume_MA20"].iloc[-1] if "Volume_MA20" in ind.columns else lat["Volume"]
            vol_ratio = lat["Volume"] / vol_ma20 if vol_ma20 > 0 else 1
            ma20 = ind["MA20"].iloc[-1] if "MA20" in ind.columns else np.nan

            stats_list.append({
                "Mã": t,
                "Giá": lat["Close"],
                "1 ngày (%)": pct_1d,
                "15 ngày (%)": pct_15d,
                "RSI (14)": rsi,
                "MFI (14)": mfi,
                "Stoch K": stoch,
                "MACD Hist": macd_h,
                "Giá / MA20 (%)": (lat["Close"] - ma20) / ma20 * 100 if not pd.isna(ma20) and ma20 > 0 else 0,
                "KL / MA20 (lần)": vol_ratio,
            })
    return pd.DataFrame(stats_list)


def create_chart(df, show_indicators):
    has_vol = "Volume" in df.columns
    has_rsi = "RSI" in df.columns and "RSI" in show_indicators
    has_macd = "MACD" in df.columns and "MACD" in show_indicators
    has_stoch = "Stoch_K" in df.columns and "Stochastic" in show_indicators

    rows = 1
    titles = [""]
    heights = [0.60]
    if has_vol: rows += 1; titles.append(""); heights.append(0.16)
    if has_rsi: rows += 1; titles.append("RSI (14)"); heights.append(0.09)
    if has_stoch: rows += 1; titles.append("Stochastic"); heights.append(0.09)
    if has_macd: rows += 1; titles.append("MACD"); heights.append(0.09)

    total = sum(heights)
    heights[0] += (1.0 - total)
    heights = [h / sum(heights) for h in heights]

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        vertical_spacing=0.02, subplot_titles=titles, row_heights=heights)

    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="Giá",
        increasing_line_color="#16a34a", decreasing_line_color="#dc2626",
        increasing_fillcolor="rgba(22,163,74,0.25)", decreasing_fillcolor="rgba(220,38,38,0.25)"), row=1, col=1)

    if "Bollinger" in show_indicators and "BB_Upper" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], name="BB", line=dict(color="#64748b", width=1, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], name="BB", line=dict(color="#64748b", width=1, dash="dot"), fill="tonexty", fillcolor="rgba(100,116,139,0.10)"), row=1, col=1)

    if "MA10" in df.columns and "MA10" in show_indicators:
        fig.add_trace(go.Scatter(x=df.index, y=df["MA10"], name="MA10", line=dict(color="#eab308", width=1.2)), row=1, col=1)
    if "MA20" in df.columns and "MA20" in show_indicators:
        fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], name="MA20", line=dict(color="#2563eb", width=1.3)), row=1, col=1)
    if "MA50" in df.columns and "MA50" in show_indicators:
        fig.add_trace(go.Scatter(x=df.index, y=df["MA50"], name="MA50", line=dict(color="#f97316", width=1.5)), row=1, col=1)
    if "MA200" in df.columns and "MA200" in show_indicators:
        fig.add_trace(go.Scatter(x=df.index, y=df["MA200"], name="MA200", line=dict(color="#7c3aed", width=1.6)), row=1, col=1)

    r = 2
    if has_vol:
        c = ["#16a34a" if cl>=op else "#dc2626" for cl,op in zip(df["Close"],df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Vol", marker_color=c, opacity=0.4), row=r, col=1)
        r += 1
    if has_rsi:
        fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="#2563eb", width=1.2)), row=r, col=1)
        fig.add_hline(y=70,line_dash="dot",line_color="#dc2626",line_width=0.8,row=r,col=1)
        fig.add_hline(y=30,line_dash="dot",line_color="#16a34a",line_width=0.8,row=r,col=1)
        r += 1
    if has_stoch:
        fig.add_trace(go.Scatter(x=df.index, y=df["Stoch_K"], name="K", line=dict(color="#2563eb", width=1.1)), row=r, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["Stoch_D"], name="D", line=dict(color="#f97316", width=1.1)), row=r, col=1)
        fig.add_hline(y=80,line_dash="dot",line_color="#dc2626",line_width=0.8,row=r,col=1)
        fig.add_hline(y=20,line_dash="dot",line_color="#16a34a",line_width=0.8,row=r,col=1)
        r += 1
    if has_macd:
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(color="#2563eb", width=1.2)), row=r, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD_Signal"], name="Sig", line=dict(color="#f97316", width=1.1)), row=r, col=1)
        macd_colors = ["#16a34a" if v >= 0 else "#dc2626" for v in df["MACD_Histogram"].fillna(0)]
        fig.add_trace(go.Bar(x=df.index, y=df["MACD_Histogram"], name="Hist", marker_color=macd_colors, opacity=0.4), row=r, col=1)
        r += 1

    fig.update_layout(
        height=520, template="plotly_white", xaxis_rangeslider_visible=False,
        showlegend=False, margin=dict(l=40,r=15,t=10,b=10),
        plot_bgcolor="#f4f9ff", paper_bgcolor="#ffffff",
        font=dict(color="#4a6fa5", size=10),
    )
    fig.update_xaxes(gridcolor="#dbe7f6", zeroline=False)
    fig.update_yaxes(gridcolor="#dbe7f6", zeroline=False)
    return fig


@st.cache_data(ttl=600, show_spinner=False)
def screen_all() -> pd.DataFrame:
    """Rà quét cả rổ 20 cổ phiếu bằng chỉ số kỹ thuật, xếp hạng theo cơ hội mua."""
    tickers = ["VCB", "FPT", "HPG", "VHM", "TCB", "VIC", "MBB", "MWG", "MSN", "VRE",
               "GAS", "PLX", "CTG", "VPB", "SHB", "SSI", "VND", "STB", "ACB", "POW"]
    mkt = get_vnindex("1y")
    market_status = get_market_status(mkt) if not mkt.empty else None

    rows = []
    for t in tickers:
        df = get_stock_data(t + ".VN", period="1y", interval="1d")
        if df.empty:
            continue
        a = analyze_stock(df, market_status=market_status)
        if not a["ok"]:
            continue
        c = classify_stock(df, market_status=market_status)
        # Chỉ các mã có dữ liệu hợp lệ được tính classification
        rows.append({
            "Mã": t,
            "Giá": a["current_price"],
            "1 ngày (%)": a["pct_1d"],
            "5 ngày (%)": a["pct_5d"],
            "20 ngày (%)": a["pct_20d"],
            "Tín hiệu": a["signal"],
            "Điểm cơ hội": a["score_100"],
            "Phân loại": c["verdict"],
            "Độ tin cậy": c["confidence"],
            "Điểm mua": a["entry"],
            "Cắt lỗ": a["stop_loss"],
            "Chốt lời": a["take_profit"],
            "RSI": a["rsi"],
            "MACD H": a["macd_h"],
            "CMF": a["cmf"],
            "KL/MA20": a["vol_ratio"],
            "_reasons_buy": a["reasons_buy"],
            "_reasons_sell": a["reasons_sell"],
            "_wave": a["wave_trend"],
            "_net": a["net_score"],
            "_reason": c["reason"],
            "_trend_score": c["trend_score"],
            "_opp_score": c["opp_score"],
            "_confirms_up": c["confirms_up"],
            "_confirms_down": c["confirms_down"],
            "_opp_details": c["opp_details"],
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.sort_values(by="Điểm cơ hội", ascending=False).reset_index(drop=True)
    return df


def _predict_text(a) -> str:
    sig = a["signal"]
    if "MUA" in sig:
        target = a["take_profit"] or a["current_price"] * 1.05
        return f"Xu hướng tích cực: khả năng tăng hướng tới vùng {target:,.0f} trong ngắn hạn. Cân nhắc vào vị thế theo Điểm mua."
    if "BÁN" in sig:
        return f"Xu hướng tiêu cực: khả năng điều chỉnh/giảm còn tiếp diễn. Ưu tiên chốt lời hoặc đứng ngoài."
    return "Đi ngang/tích lũy: chưa có tín hiệu rõ ràng, nên chờ giá bứt phá hoặc xác nhận hướng."
st.markdown("""
<div class="app-header">
    <span class="app-logo">📈</span>
    <div>
        <div class="app-title">Xích Luyện Phố Wall</div>
        <div class="app-sub">Phân tích kỹ thuật chứng khoán & chỉ số VNINDEX Việt Nam</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---- Nút cập nhật dữ liệu mới nhất (xoá cache + tải lại) ----
c_ref, _c_spc = st.columns([1, 3])
with c_ref:
    if st.button("🔄 Cập nhật dữ liệu", use_container_width=True):
        force_refresh()
        st.rerun()


# ===================== CHỌN TAB - CHỈ TẢI DỮ LIỆU CỦA TAB ĐANG MỞ (GIẢM GỌI API) =====================
tab = st.segmented_control("Chọn mục", ["1. Thị trường", "2. Thống kê", "3. Chi tiết", "4. Cơ hội", "5. Của tôi"],
                           default="1. Thị trường", selection_mode="single", label_visibility="collapsed")
st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)


# ===================== TAB 1: THỊ TRƯỜNG (VNINDEX) =====================
if tab == "1. Thị trường":
    with st.spinner("Đang tải dữ liệu chỉ số VNINDEX..."):
        market_df = get_vnindex(period="1y")
    if market_df.empty:
        st.error("Không thể tải dữ liệu chỉ số VNINDEX. Vui lòng thử lại.")
    else:
        market_df = add_all_indicators(detect_waves(market_df.copy()))

        latest_idx = market_df.iloc[-1]
        prev_idx = market_df.iloc[-2]
        chg_idx = latest_idx["Close"] - prev_idx["Close"]
        chg_pct_idx = chg_idx / prev_idx["Close"] * 100
        chg_color = "price-up" if chg_idx > 0 else "price-down" if chg_idx < 0 else "price-flat"
        chg_sign = "+" if chg_idx >= 0 else ""

        market_info = get_market_status(market_df)
        wave_market = analyze_wave_trend(market_df)

        trend_map = {
            "TĂNG MẠNH": ("XU HƯỚNG TĂNG TRƯỞNG MẠNH", "#16a34a"),
            "TĂNG NHẸ": ("XU HƯỚNG TĂNG TRƯỞNG NHẸ", "#16a34a"),
            "GIẢM MẠNH": ("XU HƯỚNG GIẢM ĐIỂM SÂU", "#dc2626"),
            "GIẢM NHẸ": ("XU HƯỚNG ĐIỀU CHỈNH NHẸ", "#dc2626"),
            "ĐI NGANG": ("XU HƯỚNG TÍCH LŨY - ĐI NGANG", "#b45309"),
        }
        trend_text, trend_color = trend_map.get(market_info["trend"], ("XU HƯỚNG TRUNG TÍNH", "#b45309"))

        col_left_m, col_right_m = st.columns([3, 2])

        with col_left_m:
            st.markdown(f"""
            <div class="section-box" style="margin-top:0px;">
                <span style="font-size:1.15em; font-weight:600; color:#4a6fa5; margin-right:10px;">Chỉ số VNINDEX</span>
                <span style="font-size:1.8em; font-weight:700; color:#1e3a5f;">{latest_idx['Close']:,.2f}</span>
                <span class="price-change {chg_color}" style="font-size:1.15em;">{chg_sign}{chg_idx:,.2f} ({chg_sign}{chg_pct_idx:.2f}%)</span>
            </div>
            """, unsafe_allow_html=True)

            fig_idx = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                    vertical_spacing=0.03, row_heights=[0.75, 0.25])
            tail = market_df.iloc[-180:]
            fig_idx.add_trace(go.Candlestick(x=tail.index, open=tail["Open"], high=tail["High"],
                low=tail["Low"], close=tail["Close"], name="VNINDEX",
                increasing_line_color="#16a34a", decreasing_line_color="#dc2626",
                increasing_fillcolor="rgba(22,163,74,0.25)", decreasing_fillcolor="rgba(220,38,38,0.25)"), row=1, col=1)
            fig_idx.add_trace(go.Scatter(x=tail.index, y=tail["MA10"], name="MA10", line=dict(color="#eab308", width=1.2)), row=1, col=1)
            fig_idx.add_trace(go.Scatter(x=tail.index, y=tail["MA20"], name="MA20", line=dict(color="#2563eb", width=1.3)), row=1, col=1)
            fig_idx.add_trace(go.Scatter(x=tail.index, y=tail["MA50"], name="MA50", line=dict(color="#f97316", width=1.5)), row=1, col=1)
            vol_colors = ["#16a34a" if c >= o else "#dc2626" for c, o in zip(tail["Close"], tail["Open"])]
            fig_idx.add_trace(go.Bar(x=tail.index, y=tail["Volume"], name="Khối lượng", marker_color=vol_colors, opacity=0.4), row=2, col=1)
            fig_idx.update_layout(height=430, template="plotly_white", xaxis_rangeslider_visible=False,
                showlegend=False, margin=dict(l=40, r=15, t=10, b=10),
                plot_bgcolor="#f4f9ff", paper_bgcolor="#ffffff", font=dict(color="#4a6fa5", size=10))
            fig_idx.update_xaxes(gridcolor="#dbe7f6", zeroline=False)
            fig_idx.update_yaxes(gridcolor="#dbe7f6", zeroline=False)
            st.plotly_chart(fig_idx, use_container_width=True)

            mc1, mc2, mc3, mc4 = st.columns(4)
            with mc1:
                st.metric("MA20", f"{market_info['ma20']:,.2f}")
            with mc2:
                st.metric("MA50", f"{market_info['ma50']:,.2f}")
            with mc3:
                st.metric("Biến động 5 ngày", f"{market_info['pct_5d']:+.2f}%")
            with mc4:
                st.metric("Biến động 20 ngày", f"{market_info['pct_20d']:+.2f}%")

        with col_right_m:
            st.markdown(f"""
            <div class="section-box" style="margin-top:0px; border-left: 4px solid {trend_color};">
                <div style="font-size:0.75em; color:#6b87a8; font-weight:500;">XU HƯỚNG THỊ TRƯỜNG CHUNG</div>
                <div style="font-size:1.15em; font-weight:700; color:{trend_color}; margin-top:2px;">{trend_text}</div>
                <div style="font-size:0.8em; color:#1e3a5f; margin-top:6px; line-height:1.4;">{market_info['recommendation']}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown('<div class="section-box">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Phân tích Dòng - Sóng - Điểm</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div style="font-size:0.82em; line-height:1.55; color:#1e3a5f;">
                <strong style="color:#2563eb;">• DÒNG (Dòng tiền):</strong> Dòng tiền thông minh tập trung quanh nhóm cổ phiếu trụ vốn hóa lớn; khối lượng đang {("vào mạnh" if market_info['pct_5d'] > 1 else "co giãn")}.<br>
                <strong style="color:#b45309;">• SÓNG (Xu hướng sóng):</strong> Trạng thái sóng VNINDEX ở pha: <span style="color:#b45309; font-weight:600;">{wave_market['trend']}</span>.<br>
                <strong style="color:#16a34a;">• ĐIỂM (Vùng chỉ số):</strong> VNINDEX quanh mốc <span style="color:#16a34a; font-weight:600;">{latest_idx['Close']:,.0f} điểm</span>, hỗ trợ tại <span style="color:#16a34a; font-weight:600;">{latest_idx['Close']*0.98:,.0f}</span> và kháng cự tại <span style="color:#dc2626; font-weight:600;">{latest_idx['Close']*1.025:,.0f} điểm</span>.
            </div>
            """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)


# ===================== TAB 2: THỐNG KÊ (TOP 20 TĂNG/GIẢM) =====================
elif tab == "2. Thống kê":
    st.markdown("""
    <div style="margin-bottom: 10px;">
        <h3 style="margin:0;font-size:1.3em;">THỐNG KÊ BIẾN ĐỘNG THỊ TRƯỜNG</h3>
        <div style="color:#6b87a8;font-size:0.75em;">Dựa trên rổ 20 cổ phiếu theo dõi — mỗi mã chỉ nằm ở 1 danh sách (tăng nếu 15 ngày ≥ 0, giảm nếu < 0)</div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Đang tải dữ liệu toàn danh mục (có thể mất vài giây)..."):
        df_stats = load_all_market_data()

    if df_stats.empty:
        st.warning("Không thể truy xuất dữ liệu xếp hạng lúc này. Vui lòng thử lại sau vài phút (giới hạn API).")
    else:
        top_gainers = df_stats[df_stats["15 ngày (%)"] >= 0].sort_values(by="15 ngày (%)", ascending=False).reset_index(drop=True)
        top_losers = df_stats[df_stats["15 ngày (%)"] < 0].sort_values(by="15 ngày (%)", ascending=True).reset_index(drop=True)

        def _build_display(x):
            d = x.copy()
            d["Giá"] = d["Giá"].map(lambda v: f"{v:,.2f}" if pd.notna(v) else "-")
            for c in ["1 ngày (%)", "15 ngày (%)", "Giá / MA20 (%)"]:
                d[c] = d[c].map(lambda v: (f"{v:+.2f}%" if pd.notna(v) else "-"))
            d["RSI (14)"] = d["RSI (14)"].map(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
            d["MFI (14)"] = d["MFI (14)"].map(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
            d["Stoch K"] = d["Stoch K"].map(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
            d["MACD Hist"] = d["MACD Hist"].map(lambda v: f"{v:+.2f}" if pd.notna(v) else "-")
            d["KL / MA20 (lần)"] = d["KL / MA20 (lần)"].map(lambda v: f"{v:.2f}x" if pd.notna(v) else "-")
            return d[["Mã", "Giá", "1 ngày (%)", "15 ngày (%)", "RSI (14)", "MFI (14)", "Stoch K", "MACD Hist", "KL / MA20 (lần)"]]

        c_gain, c_loss = st.columns(2)

        with c_gain:
            st.markdown('<div class="section-box" style="margin-top:0px;">', unsafe_allow_html=True)
            st.markdown(f'<div class="section-title" style="color:#16a34a;">▲ CÁC MÃ TĂNG TRONG RỔ (15 ngày) — {len(top_gainers)} mã</div>', unsafe_allow_html=True)
            if top_gainers.empty:
                st.markdown('<div style="color:#6b87a8;font-size:0.85em;">Không có mã nào tăng trong 15 ngày qua.</div>', unsafe_allow_html=True)
            else:
                st.dataframe(_build_display(top_gainers), use_container_width=True, hide_index=True, height=min(800, 38 + len(top_gainers) * 35))
            st.markdown('</div>', unsafe_allow_html=True)

        with c_loss:
            st.markdown('<div class="section-box" style="margin-top:0px;">', unsafe_allow_html=True)
            st.markdown(f'<div class="section-title" style="color:#dc2626;">▼ CÁC MÃ GIẢM TRONG RỔ (15 ngày) — {len(top_losers)} mã</div>', unsafe_allow_html=True)
            if top_losers.empty:
                st.markdown('<div style="color:#6b87a8;font-size:0.85em;">Không có mã nào giảm trong 15 ngày qua.</div>', unsafe_allow_html=True)
            else:
                st.dataframe(_build_display(top_losers), use_container_width=True, hide_index=True, height=min(800, 38 + len(top_losers) * 35))
            st.markdown('</div>', unsafe_allow_html=True)


# ===================== TAB 3: CHI TIẾT (MÃ CỔ PHIẾU) =====================
elif tab == "3. Chi tiết":
    st.markdown("""
    <div style="margin-bottom: 10px;">
        <h3 style="margin:0;font-size:1.3em;">PHÂN TÍCH CHI TIẾT CỔ PHIẾU</h3>
        <div style="color:#6b87a8;font-size:0.75em;">Nhập mã bất kỳ trên sàn HOSE/HNX/UPCOM để xem phân tích</div>
    </div>
    """, unsafe_allow_html=True)

    # Hàng ngang trên cùng: chọn mã, thời gian, khung
    cfg1, cfg2, cfg3, cfg4 = st.columns([3, 1.3, 1.3, 1])
    with cfg1:
        if "pf_last_ticker" not in st.session_state:
            st.session_state.pf_last_ticker = portfolio.get_last_ticker()
        custom = st.text_input("Chọn mã cổ phiếu (VD: FPT, HPG, VCB)",
                               key="pf_last_ticker", placeholder="FPT, HPG, VCB...")
        if custom and custom.strip():
            portfolio.set_last_ticker(custom)
        ticker = normalize_ticker(custom) if custom and custom.strip() else f"{st.session_state.pf_last_ticker}.VN"
    with cfg2:
        period = st.selectbox("Khung thời gian", ["3 tháng", "6 tháng", "1 năm", "2 năm"], index=2)
    with cfg3:
        interval = st.selectbox("Khung nến", ["Ngày", "Tuần"], index=0)
    cfg4.markdown("")

    period_map = {"3 tháng": "3mo", "6 tháng": "6mo", "1 năm": "1y", "2 năm": "2y"}
    interval_map = {"Ngày": "1d", "Tuần": "1wk"}

    symbol = ticker.replace(".VN", "").replace(".vn", "").upper()
    company_name = get_company_name(symbol)

    with st.spinner("Đang tải và tính toán chỉ báo kỹ thuật..."):
        df = get_cached_stock_data(ticker, period=period_map[period])
    if df.empty:
        st.error(f"Không tìm thấy dữ liệu mã chứng khoán {symbol}. Có thể do giới hạn API (20 lượt/phút) — vui lòng thử lại sau 1 phút, hoặc kiểm tra lại mã.")
    else:
        df = add_all_indicators(df.copy())
        df = detect_waves(df)

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        chg = latest["Close"] - prev["Close"]
        chg_pct = chg / prev["Close"] * 100
        chg_color = "price-up" if chg > 0 else "price-down" if chg < 0 else "price-flat"
        chg_sign = "+" if chg >= 0 else ""

        mkt_df = get_vnindex(period="1y")
        market_status = get_market_status(mkt_df) if not mkt_df.empty else None
        entry_info = suggest_entry_points(df, market_status=market_status)
        wave_info = analyze_wave_trend(df)

        st.markdown(f"""
        <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:15px">
            <span style="font-size:1.15em;font-weight:600;color:#4a6fa5">{company_name}</span>
            <span style="font-size:0.9em;font-weight:600;color:#2563eb;background:#d6e7fb;padding:2px 6px;border-radius:4px">{symbol}.VN</span>
            <span class="price-main">{latest['Close']:,.2f}</span>
            <span class="price-change {chg_color}">{chg_sign}{chg:,.2f} ({chg_sign}{chg_pct:.2f}%)</span>
        </div>
        """, unsafe_allow_html=True)

        sig_text = entry_info["signal"]
        sig_badge = "badge-buy" if "MUA" in sig_text else "badge-sell" if "BÁN" in sig_text else "badge-neutral"

        def _px(v):
            return "-" if v is None or pd.isna(v) else f"{v:,.2f}"

        rec1, rec2, rec3, rec4 = st.columns(4)
        with rec1:
            st.markdown(f'<div class="section-box" style="margin-top:0;"><div class="section-title">Khuyến nghị</div><div class="signal-badge {sig_badge}">{sig_text}</div></div>', unsafe_allow_html=True)
        with rec2:
            st.markdown(f'<div class="section-box" style="margin-top:0;"><div class="section-title">Điểm mua</div><div class="entry-value" style="color:#16a34a;font-size:1.4em;">{_px(entry_info["entry"])}</div><div class="entry-label">Giá hiện tại {_px(entry_info["current_price"])}</div></div>', unsafe_allow_html=True)
        with rec3:
            st.markdown(f'<div class="section-box" style="margin-top:0;"><div class="section-title">Cắt lỗ</div><div class="entry-value" style="color:#dc2626;font-size:1.4em;">{_px(entry_info["stop_loss"])}</div><div class="entry-label">ATR: {_px(entry_info["atr"])}</div></div>', unsafe_allow_html=True)
        with rec4:
            st.markdown(f'<div class="section-box" style="margin-top:0;"><div class="section-title">Chốt lời</div><div class="entry-value" style="color:#16a34a;font-size:1.4em;">{_px(entry_info["take_profit"])}</div></div>', unsafe_allow_html=True)

        # Bảng thống kê toàn bộ chỉ số kỹ thuật
        st.markdown('<div class="section-box" style="margin-top:12px;">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Thống kê các chỉ số kỹ thuật</div>', unsafe_allow_html=True)

        def _num(v, nd=1):
            return "-" if v is None or pd.isna(v) else f"{v:,.{nd}f}"

        row1 = st.columns(6)
        row2 = st.columns(6)
        metrics = [
            ("RSI (14)", _num(latest['RSI']), "Quá mua >70 / Quá bán <30"),
            ("MFI (14)", _num(latest['MFI']), "Dòng tiền quá mua >80"),
            ("MACD", _num(latest['MACD'], 2), "Histogram: " + _num(latest['MACD_Histogram'], 2)),
            ("Stochastic K", _num(latest['Stoch_K']), "D: " + _num(latest['Stoch_D'])),
            ("ATR (14)", _num(latest['ATR'], 2), "Biến động giá"),
            ("CMF (20)", _num(latest['CMF'], 2), "Dòng tiền Chaikin"),
        ]
        for col, (name, val, hint) in zip(row1, metrics):
            with col:
                st.markdown(f'<div class="entry-cell"><div class="entry-label">{name}</div><div class="entry-value" style="color:#1e3a5f;">{val}</div><div class="entry-label">{hint}</div></div>', unsafe_allow_html=True)
        metrics2 = [
            ("Giá / MA20", _num(latest['Close'] - latest['MA20'], 2), "MA20: " + _num(latest['MA20'])),
            ("Giá / MA50", _num(latest['Close'] - latest['MA50'], 2), "MA50: " + _num(latest['MA50'])),
            ("BB Upper", _num(latest['BB_Upper']), "Bollinger trên"),
            ("BB Lower", _num(latest['BB_Lower']), "Bollinger dưới"),
            ("OBV", ("-" if pd.isna(latest['OBV']) else f"{latest['OBV']:,.0f}"), "Dòng tiền tích lũy"),
            ("Force Index", _num(latest['Force_Index_EMA'], 0), "Lực mua/bán"),
        ]
        for col, (name, val, hint) in zip(row2, metrics2):
            with col:
                st.markdown(f'<div class="entry-cell"><div class="entry-label">{name}</div><div class="entry-value" style="color:#1e3a5f;">{val}</div><div class="entry-label">{hint}</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Dòng - Sóng - Điểm
        st.markdown('<div class="section-box" style="margin-top:12px;">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Phân tích Dòng - Sóng - Điểm</div>', unsafe_allow_html=True)
        sup_text = ", ".join(f"{s:,.0f}" for s in (entry_info.get("support") or [])[-3:]) or "-"
        res_text = ", ".join(f"{r:,.0f}" for r in (entry_info.get("resistance") or [])[-3:]) or "-"
        st.markdown(f"""
        <div style="font-size:0.85em; line-height:1.6; color:#1e3a5f;">
            <strong style="color:#2563eb;">• DÒNG (Dòng tiền):</strong> MFI = {_num(latest['MFI'])}, CMF = {_num(latest['CMF'])} → dòng tiền {("vào" if latest['CMF'] > 0 else "ra")} chủ đạo của mã {symbol}.<br>
            <strong style="color:#b45309;">• SÓNG (Xu hướng sóng):</strong> {wave_info['trend']} — {wave_info['description']}<br>
            <strong style="color:#16a34a;">• ĐIỂM (Vùng giá):</strong> Hỗ trợ: {sup_text} | Kháng cự: {res_text}
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Giải thích lý do mua/bán
        st.markdown('<div class="section-box" style="margin-top:12px;">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Lý do khuyến nghị dựa trên các chỉ số kỹ thuật</div>', unsafe_allow_html=True)
        b_col, s_col = st.columns(2)
        with b_col:
            st.markdown('<div style="color:#16a34a;font-weight:700;margin-bottom:6px;">▲ Yếu tố ỦNG HỘ MUA</div>', unsafe_allow_html=True)
            if entry_info["reasons_buy"]:
                for r in entry_info["reasons_buy"]:
                    st.markdown(f'<div style="color:#1e3a5f;font-size:0.85em;padding:2px 0;">• {r}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:#6b87a8;font-size:0.85em;">Không có yếu tố mua nổi bật.</div>', unsafe_allow_html=True)
        with s_col:
            st.markdown('<div style="color:#dc2626;font-weight:700;margin-bottom:6px;">▼ Yếu tố ỦNG HỘ BÁN</div>', unsafe_allow_html=True)
            if entry_info["reasons_sell"]:
                for r in entry_info["reasons_sell"]:
                    st.markdown(f'<div style="color:#1e3a5f;font-size:0.85em;padding:2px 0;">• {r}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:#6b87a8;font-size:0.85em;">Không có yếu tố bán nổi bật.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Đồ thị kỹ thuật
        opts = st.multiselect("Bật tắt chỉ báo hiển thị trên đồ thị",
            ["MA10", "MA20", "MA50", "MA200", "Bollinger", "RSI", "MACD", "Stochastic"],
            default=["MA20", "MA50"], key="chart_opts_sel")
        fig = create_chart(df, opts)
        st.plotly_chart(fig, use_container_width=True, key="detail_chart")


# ===================== TAB 4: CƠ HỘI (LỌC MÃ CÓ DẤU HIỆU TĂNG) =====================
elif tab == "4. Cơ hội":
    st.markdown("""
    <div style="margin-bottom: 10px;">
        <h3 style="margin:0;font-size:1.3em;">CƠ HỘI — MÃ CÓ DẤU HIỆU TĂNG</h3>
        <div style="color:#6b87a8;font-size:0.75em;">Rà quét rổ 20 cổ phiếu bằng <strong>tất cả chỉ số kỹ thuật</strong> (MA, EMA, MACD, RSI, Stochastic, Ichimoku, Bollinger, CMF, OBV, Force, sóng...). Chỉ liệt kê mã có xu hướng tăng rõ ràng + điểm vào hợp lý, kèm điểm mua / cắt lỗ / chốt lời.</div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Đang rà quét các mã bằng toàn bộ chỉ số kỹ thuật..."):
        df_screen = screen_all()

    if df_screen.empty:
        st.warning("Không thể quét dữ liệu lúc này. Vui lòng thử lại sau vài phút (giới hạn API).")
    else:
        def _sig_badge(sig):
            cls = "badge-buy" if "MUA" in sig else "badge-sell" if "BÁN" in sig else "badge-neutral"
            color = "#16a34a" if "MUA" in sig else "#dc2626" if "BÁN" in sig else "#b45309"
            return f'<span class="signal-badge" style="padding:6px 10px;font-size:0.9em;border:0;">{sig}</span>'

        def _verdict_badge(v):
            if v == "CƠ HỘI MẠNH":
                color, bg = "#16a34a", "#e7f7ee"
            elif v == "CƠ HỘI":
                color, bg = "#2563eb", "#d6e7fb"
            elif v == "THEO DÕI":
                color, bg = "#b45309", "#fdf6e3"
            else:
                color, bg = "#dc2626", "#fdecec"
            return f'<span style="color:{color};background:{bg};border:1px solid {color};border-radius:5px;padding:2px 8px;font-weight:600;font-size:0.78em;">{v}</span>'

        cand = df_screen[df_screen["Phân loại"].isin(["CƠ HỘI MẠNH", "CƠ HỘI"])].copy()
        cand = cand.sort_values(by="Điểm cơ hội", ascending=False).reset_index(drop=True)

        # ---------- MÃ CƠ HỘI ĐƯỢC CHỌN LỌC ----------
        if cand.empty:
            st.info("Hiện không có mã nào đủ điều kiện (xu hướng tăng rõ ràng + điểm vào tốt) dựa trên toàn bộ chỉ số kỹ thuật. Các mã khác đang theo dõi: xem bảng bên dưới.")
        else:
            st.markdown('<div class="section-box" style="margin-top:0;">', unsafe_allow_html=True)
            st.markdown(f'<div class="section-title">✅ MÃ ĐƯỢC CHỌN LỌC — CƠ HỘI TĂNG ({len(cand)} mã) · có điểm mua / cắt lỗ / chốt lời</div>', unsafe_allow_html=True)
            for _, r in cand.iterrows():
                _px = lambda v: "-" if v is None or pd.isna(v) else f"{v:,.0f}"
                st.markdown(f"""
                <div style="display:flex;align-items:baseline;gap:10px;padding:4px 0;flex-wrap:wrap;">
                    <span style="font-weight:700;color:#2563eb;font-size:1.1em;">{r['Mã']}</span>
                    <span style="font-weight:700;color:#1e3a5f;">{r['Giá']:,.2f}</span>
                    <span class="price-change {'price-up' if r['1 ngày (%)']>=0 else 'price-down'}">{'+' if r['1 ngày (%)']>=0 else ''}{r['1 ngày (%)']:.2f}%</span>
                    {_verdict_badge(r['Phân loại'])}
                    <span style="color:#6b87a8;font-size:0.8em;">Cơ hội <strong>{int(r['Điểm cơ hội'])}/100</strong> · Độ tin cậy <strong>{int(r['Độ tin cậy'])}%</strong></span>
                    {_sig_badge(r['Tín hiệu'])}
                </div>
                """, unsafe_allow_html=True)

                # Điểm mua / cắt lỗ / chốt lời
                d1, d2, d3 = st.columns(3)
                with d1:
                    st.markdown(f'<div class="entry-cell"><div class="entry-label">ĐIỂM MUA</div><div class="entry-value" style="color:#16a34a;">{_px(r["Điểm mua"])}</div></div>', unsafe_allow_html=True)
                with d2:
                    st.markdown(f'<div class="entry-cell"><div class="entry-label">CẮT LỖ</div><div class="entry-value" style="color:#dc2626;">{_px(r["Cắt lỗ"])}</div></div>', unsafe_allow_html=True)
                with d3:
                    st.markdown(f'<div class="entry-cell"><div class="entry-label">CHỐT LỜI</div><div class="entry-value" style="color:#16a34a;">{_px(r["Chốt lời"])}</div></div>', unsafe_allow_html=True)

                st.markdown(f'<div style="margin-top:8px;color:#1e3a5f;font-size:0.88em;"><strong style="color:#2563eb;">Kết luận:</strong> {r["_reason"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="color:#6b87a8;font-size:0.8em;">Xu hướng: {r["_wave"]} · Điểm xu hướng {int(r["_trend_score"])}/100 · Điểm cơ hội mua {int(r["_opp_score"])}/100 · Xác nhận tăng {int(r["_confirms_up"])} / giảm {int(r["_confirms_down"])}</div>', unsafe_allow_html=True)

                mb = r["_reasons_buy"] or []
                ms = r["_reasons_sell"] or []
                od = r["_opp_details"] or []
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown('<div style="color:#2563eb;font-weight:700;margin-top:6px;">CƠ HỘI MUA</div>', unsafe_allow_html=True)
                    for x in od:
                        st.markdown(f'<div style="color:#16a34a;font-size:0.83em;padding:1px 0;">• {x}</div>', unsafe_allow_html=True)
                    if not od:
                        st.markdown('<div style="color:#6b87a8;font-size:0.8em;">Không có yếu tố đặc biệt.</div>', unsafe_allow_html=True)
                with c2:
                    st.markdown('<div style="color:#16a34a;font-weight:700;margin-top:6px;">ỦNG HỘ TĂNG</div>', unsafe_allow_html=True)
                    for x in mb:
                        st.markdown(f'<div style="color:#1e3a5f;font-size:0.83em;padding:1px 0;">▲ {x}</div>', unsafe_allow_html=True)
                    if not mb:
                        st.markdown('<div style="color:#6b87a8;font-size:0.8em;">—</div>', unsafe_allow_html=True)
                with c3:
                    st.markdown('<div style="color:#dc2626;font-weight:700;margin-top:6px;">RỦI RO GIẢM</div>', unsafe_allow_html=True)
                    for x in ms:
                        st.markdown(f'<div style="color:#1e3a5f;font-size:0.83em;padding:1px 0;">▼ {x}</div>', unsafe_allow_html=True)
                    if not ms:
                        st.markdown('<div style="color:#6b87a8;font-size:0.8em;">—</div>', unsafe_allow_html=True)
                st.markdown('<hr style="border-color:#eef4fb;margin:10px 0;">', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # ---------- BẢNG TỔNG QUAN TOÀN RỔ ----------
        show_df = df_screen.drop(columns=["_reasons_buy", "_reasons_sell", "_wave", "_net", "_reason",
                                          "_trend_score", "_opp_score", "_confirms_up", "_confirms_down", "_opp_details"])
        disp = show_df.copy()
        disp["Giá"] = disp["Giá"].map(lambda v: f"{v:,.2f}")
        for c in ["1 ngày (%)", "5 ngày (%)"]:
            disp[c] = disp[c].map(lambda v: f"{v:+.2f}%")
        for c in ["Điểm mua", "Cắt lỗ", "Chốt lời"]:
            disp[c] = disp[c].map(lambda v: "-" if pd.isna(v) else f"{v:,.2f}")
        disp["RSI"] = disp["RSI"].map(lambda v: "-" if pd.isna(v) else f"{v:.1f}")
        disp["MACD H"] = disp["MACD H"].map(lambda v: "-" if pd.isna(v) else f"{v:+.2f}")
        disp["CMF"] = disp["CMF"].map(lambda v: "-" if pd.isna(v) else f"{v:.2f}")
        disp["KL/MA20"] = disp["KL/MA20"].map(lambda v: "-" if pd.isna(v) else f"{v:.1f}x")
        disp["Điểm cơ hội"] = disp["Điểm cơ hội"].astype(int)
        disp["Độ tin cậy"] = disp["Độ tin cậy"].astype(int)
        disp = disp[["Mã", "Giá", "1 ngày (%)", "5 ngày (%)", "Tín hiệu", "Phân loại", "Điểm cơ hội", "Độ tin cậy",
                     "Điểm mua", "Cắt lỗ", "Chốt lời", "RSI", "MACD H", "CMF"]]
        st.markdown('<div class="section-box" style="margin-top:12px;">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📊 Toàn rổ 20 mã — Phân loại theo chỉ số kỹ thuật</div>', unsafe_allow_html=True)
        st.dataframe(disp, use_container_width=True, hide_index=True,
                     height=min(720, 40 + len(disp) * 34),
                     column_config={"Tín hiệu": st.column_config.TextColumn("Tín hiệu"),
                                    "Phân loại": st.column_config.TextColumn("Phân loại")})
        st.markdown('</div>', unsafe_allow_html=True)


# ===================== TAB 5: CỦA TÔI (DANH MỤC THEO DÕI + CẢNH BÁO) =====================
else:
    st.markdown("""
    <div style="margin-bottom: 10px;">
        <h3 style="margin:0;font-size:1.3em;">CỦA TÔI — MÃ ĐANG NẮM GIỮ / QUAN TÂM</h3>
        <div style="color:#6b87a8;font-size:0.75em;">Lưu các mã bạn quan tâm (tự động nhớ qua mỗi lần mở app), xem đánh giá, dự đoán và cảnh báo tăng/giảm.</div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Đang tải dữ liệu danh mục của bạn..."):
        mkt_pf = get_vnindex("1y")
        market_status_pf = get_market_status(mkt_pf) if not mkt_pf.empty else None

    watch = portfolio.get_watchlist()

    # ---- Thêm mã mới ----
    st.markdown('<div class="section-box" style="margin-top:0;">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">➕ Thêm mã theo dõi</div>', unsafe_allow_html=True)
    a1, a2, a3, a4 = st.columns([2, 1.2, 1.2, 1])
    with a1:
        new_ticker = st.text_input("Mã chứng khoán (VD: FPT, HPG, VCB)", value="", key="pf_new")
    with a2:
        new_sl = st.text_input("Cắt lỗ (giá)", value="", key="pf_sl")
    with a3:
        new_tp = st.text_input("Chốt lời (giá)", value="", key="pf_tp")
    with a4:
        add_clicked = st.button("➕ Thêm", use_container_width=True)
    if add_clicked and new_ticker.strip():
        sym = normalize_ticker(new_ticker).replace(".VN", "")
        try:
            sl = float(new_sl) if new_sl.strip() else None
        except ValueError:
            sl = None
        try:
            tp = float(new_tp) if new_tp.strip() else None
        except ValueError:
            tp = None
        if sym:
            portfolio.add_to_watchlist(sym, stop_loss=sl, take_profit=tp)
            watch = portfolio.get_watchlist()
            st.success(f"Đã thêm {sym} vào danh mục theo dõi.")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if not watch:
        st.info("Chưa có mã nào trong danh mục. Thêm mã bạn đang nắm giữ hoặc quan tâm ở trên.")
    else:
        # ---- Tính toán đánh giá cho từng mã ----
        pf_rows = []
        for sym, meta in watch.items():
            df = get_stock_data(sym + ".VN", period="1y", interval="1d")
            if df.empty:
                pf_rows.append({"Mã": sym, "ok": False, "meta": meta})
                continue
            a = analyze_stock(df, market_status=market_status_pf)
            alerts = build_alerts(df, market_status=market_status_pf,
                                  stop_loss=meta.get("stop_loss"), take_profit=meta.get("take_profit"))
            a["ok"] = True
            pf_rows.append({"Mã": sym, "ok": True, "a": a, "alerts": alerts, "meta": meta})

        # ---- Bảng tóm tắt ----
        table = []
        for row in pf_rows:
            if not row["ok"]:
                table.append({"Mã": row["Mã"], "Giá": None, "Tín hiệu": "—", "Dự đoán": "Không có dữ liệu",
                              "Điểm": 0, "Cảnh báo": "—"})
                continue
            a = row["a"]
            n_buy = sum(1 for x in row["alerts"] if x[0] == "up")
            n_sell = sum(1 for x in row["alerts"] if x[0] == "down")
            if n_buy > n_sell:
                alert_sum = f"▲ {n_buy} tăng / ▼ {n_sell} giảm"
            elif n_sell > n_buy:
                alert_sum = f"▼ {n_sell} giảm / ▲ {n_buy} tăng"
            else:
                alert_sum = f"{len(row['alerts'])} cảnh báo trung tính"
            pred = _predict_text(a)
            table.append({"Mã": row["Mã"], "Giá": a["current_price"], "Tín hiệu": a["signal"],
                          "Dự đoán": pred, "Điểm": a["score_100"], "Cảnh báo": alert_sum})
        tdf = pd.DataFrame(table)
        tdisp = tdf.copy()
        tdisp["Giá"] = tdisp["Giá"].map(lambda v: "-" if pd.isna(v) else f"{v:,.2f}")
        tdisp["Điểm"] = tdisp["Điểm"].astype(int)
        st.dataframe(tdisp, use_container_width=True, hide_index=True,
                     column_config={"Tín hiệu": st.column_config.TextColumn("Tín hiệu")})

        st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

        # ---- Chi tiết + cảnh báo từng mã ----
        for row in pf_rows:
            sym = row["Mã"]
            meta = row["meta"]
            sl_user = meta.get("stop_loss")
            tp_user = meta.get("take_profit")
            _px_fmt = lambda v: "-" if v is None or pd.isna(v) else f"{v:,.2f}"

            if not row["ok"]:
                h1, h2 = st.columns([7, 1])
                with h1:
                    st.markdown(f"**❌ {sym}** — không có dữ liệu (mã sai hoặc giới hạn API)")
                with h2:
                    if st.button("🗑️ Xóa", key=f"rm_{sym}", use_container_width=True):
                        portfolio.remove_from_watchlist(sym)
                        st.rerun()
                continue

            a = row["a"]
            alerts = row["alerts"]
            entry = a["entry"]
            sl = sl_user or a["stop_loss"]
            tp = tp_user or a["take_profit"]
            sig_badge = "badge-buy" if "MUA" in a["signal"] else "badge-sell" if "BÁN" in a["signal"] else "badge-neutral"
            sub = (f"Cắt lỗ {_px_fmt(sl)}" if sl_user else "") + (" · " if sl_user and tp_user else "") + \
                  (f"Chốt lời {_px_fmt(tp)}" if tp_user else "")

            h1, h2 = st.columns([7, 1])
            with h1:
                st.markdown(f"""
                <div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:8px 0 2px 0;">
                    <span style="font-weight:700;color:#2563eb;font-size:1.05em;">{sym}</span>
                    <span style="color:#1e3a5f;font-weight:700;font-size:1.05em;">{a['current_price']:,.2f}</span>
                    <span class="price-change {'price-up' if a['pct_1d']>=0 else 'price-down'}">{'+' if a['pct_1d']>=0 else ''}{a['pct_1d']:.2f}%</span>
                    <span class="signal-badge {sig_badge}" style="padding:3px 8px;font-size:0.78em;border:0;width:auto;">{a['signal']}</span>
                    <span style="color:#b45309;font-size:0.78em;">Điểm {a['score_100']}</span>
                    {f'<span style="color:#6b87a8;font-size:0.78em;">{sub}</span>' if sub else ''}
                </div>
                """, unsafe_allow_html=True)
            with h2:
                if st.button("🗑️ Xóa", key=f"rm_{sym}", use_container_width=True):
                    portfolio.remove_from_watchlist(sym)
                    st.rerun()

            with st.expander(f"Xem chi tiết & cảnh báo — {sym}"):
                st.markdown(f"""
                <div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;">
                    <span style="font-size:1.2em;font-weight:700;color:#1e3a5f;">{a['current_price']:,.2f}</span>
                    <span class="price-change {'price-up' if a['pct_1d']>=0 else 'price-down'}">{'+' if a['pct_1d']>=0 else ''}{a['pct_1d']:.2f}%</span>
                    <span style="color:#6b87a8;font-size:0.85em;">1 ngày · {a['pct_5d']:+.2f}% 5 ngày · {a['pct_20d']:+.2f}% 20 ngày</span>
                </div>
                """, unsafe_allow_html=True)
                r1, r2, r3, r4 = st.columns(4)
                with r1:
                    st.markdown(f'<div class="entry-cell"><div class="entry-label">Điểm mua</div><div class="entry-value" style="color:#16a34a;">{_px_fmt(entry)}</div></div>', unsafe_allow_html=True)
                with r2:
                    st.markdown(f'<div class="entry-cell"><div class="entry-label">Cắt lỗ</div><div class="entry-value" style="color:#dc2626;">{_px_fmt(sl)}</div></div>', unsafe_allow_html=True)
                with r3:
                    st.markdown(f'<div class="entry-cell"><div class="entry-label">Chốt lời</div><div class="entry-value" style="color:#16a34a;">{_px_fmt(tp)}</div></div>', unsafe_allow_html=True)
                with r4:
                    st.markdown(f'<div class="entry-cell"><div class="entry-label">ATR</div><div class="entry-value" style="color:#1e3a5f;">{_px_fmt(a["atr"])}</div></div>', unsafe_allow_html=True)

                st.markdown(f'<div style="margin-top:10px;"><strong style="color:#2563eb;">Dự đoán:</strong> <span style="color:#1e3a5f;">{_predict_text(a)}</span></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="margin-top:6px;"><strong style="color:#2563eb;">Xu hướng sóng:</strong> <span style="color:#b45309;">{a["wave_trend"]}</span> — {a["wave_desc"]}</div>', unsafe_allow_html=True)

                if alerts:
                    st.markdown('<div style="margin-top:12px;font-weight:700;color:#b45309;">🚨 Cảnh báo</div>', unsafe_allow_html=True)
                    for kind, text in alerts:
                        color = "#16a34a" if kind == "up" else "#dc2626" if kind == "down" else "#b45309"
                        mark = "▲" if kind == "up" else "▼" if kind == "down" else "●"
                        st.markdown(f'<div style="color:{color};font-size:0.88em;padding:1px 0;">{mark} {text}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="margin-top:10px;color:#6b87a8;font-size:0.85em;">Không có cảnh báo bất thường ở phiên hiện tại.</div>', unsafe_allow_html=True)

                if a["reasons_buy"] or a["reasons_sell"]:
                    b1, b2 = st.columns(2)
                    with b1:
                        st.markdown('<div style="color:#16a34a;font-weight:700;margin-top:8px;">▲ Yếu tố MUA</div>', unsafe_allow_html=True)
                        for x in a["reasons_buy"]:
                            st.markdown(f'<div style="color:#1e3a5f;font-size:0.85em;padding:1px 0;">• {x}</div>', unsafe_allow_html=True)
                    with b2:
                        st.markdown('<div style="color:#dc2626;font-weight:700;margin-top:8px;">▼ Yếu tố BÁN</div>', unsafe_allow_html=True)
                        for x in a["reasons_sell"]:
                            st.markdown(f'<div style="color:#1e3a5f;font-size:0.85em;padding:1px 0;">• {x}</div>', unsafe_allow_html=True)
