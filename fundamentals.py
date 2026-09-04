# -*- coding: utf-8 -*-
"""Phân tích cơ bản (fundamental) từ dữ liệu thật của vnstock.

Chỉ dùng dữ liệu mà vnstock cung cấp: thông tin doanh nghiệp, báo cáo kết quả
kinh doanh và bộ chỉ số tài chính (ratio). Mọi đánh giá đều dựa trên quy tắc
định lượng minh bạch — KHÔNG phải tin tức dư luận và KHÔNG phải khuyến nghị
đầu tư.
"""

import time

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _num(v):
    """Chuyển giá trị về số an toàn (không đổ NaN)."""
    try:
        if v is None:
            return None
        f = float(v)
        if pd.isna(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _fmt(v, digits=2, suffix="", as_str=True):
    """Định dạng số cho hiển thị."""
    if v is None:
        return "—"
    s = f"{v:,.{digits}f}{suffix}"
    return s if as_str else v


def _last_value_row(df, item_ids):
    """Lấy giá trị mới nhất (cột cuối có dữ liệu) cho danh sách item_id.

    df: bảng finance (dạng 'long' với cột item, item_id + các cột kỳ).
    Trả về dict {item_id: value} với value là float hoặc None.
    """
    if df is None or df.empty:
        return {}
    out = {}
    # Các cột kỳ = cột không phải item/item_en/item_id
    period_cols = [c for c in df.columns if c not in ("item", "item_en", "item_id")]
    for iid in item_ids:
        row = df[df["item_id"] == iid]
        if row.empty:
            out[iid] = None
            continue
        row = row.iloc[0]
        # duyệt từ cuối lên để lấy giá trị hợp lệ gần nhất
        val = None
        for c in reversed(period_cols):
            v = _num(row.get(c))
            if v is not None:
                val = v
                break
        out[iid] = val
    return out


def _history_vector(df, item_ids):
    """Lấy chuỗi giá trị qua các kỳ (theo thứ tự thời gian) cho một item_id.

    Trả về list [ (label_kỳ, value), ... ] với kỳ từ cũ đến mới.
    """
    if df is None or df.empty:
        return []
    period_cols = [c for c in df.columns if c not in ("item", "item_en", "item_id")]
    for iid in item_ids:
        row = df[df["item_id"] == iid]
        if row.empty:
            continue
        row = row.iloc[0]
        vec = []
        for c in period_cols:
            v = _num(row.get(c))
            vec.append((c, v))
        return vec
    return []


# ---------------------------------------------------------------------------
# Lấy dữ liệu thật từ vnstock
# ---------------------------------------------------------------------------
def _get_company(sym, source="KBS"):
    try:
        from vnstock import Company
        return Company(source, sym)
    except Exception:
        return None


def _get_finance(sym, source="VCI", period="quarter", get_all=True):
    try:
        from vnstock import Finance
        return Finance(source, sym, period=period, get_all=get_all)
    except Exception:
        return None


def _fetch_with_retry(fn, tries=3, wait=1.5):
    """Gọi fn() (trả DataFrame) nhiều lần cho tới khi có dữ liệu, kèm retry.
    Giảm tác động của lỗi mạng/DNS tạm thời ở phía nhà cung cấp dữ liệu."""
    for attempt in range(tries):
        try:
            df = fn()
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
        if attempt < tries - 1:
            time.sleep(wait)
    return None


def get_company_info(sym, source="KBS", tries=2):
    """Lấy thông tin doanh nghiệp, fallback nhiều nguồn + retry. Trả {} nếu lỗi."""
    import math

    def _clean(v):
        if v is None:
            return None
        try:
            if isinstance(v, float) and math.isnan(v):
                return None
        except (TypeError, ValueError):
            pass
        s = str(v)
        return None if s.strip() == "" or s.strip().lower() == "nan" else v

    # thử lần lượt nhiều nguồn, mỗi nguồn retry vài lần
    for _ in range(tries):
        for src in (source, "VCI", "KBS", "TCBS"):
            c = _get_company(sym, src)
            if c is None:
                continue
            try:
                info = c.info()
                if hasattr(info, "iloc") and not info.empty:
                    row = info.iloc[0]
                    d = {col: _clean(row.get(col)) for col in info.columns}
                    return d
            except Exception:
                continue
        time.sleep(0.8)
    return {}


def get_financials(sym, sources=("VCI", "KBS", "TCBS")):
    """Lấy income statement + ratio (quarter). Tách riêng từng phần + fallback nhiều
    nguồn + retry → 1 nguồn lỗi (VD: API ratio bị timeout/DNS) không làm mất dữ liệu
    income statement vốn đã lấy được. Trả (inc_df, ratio_df)."""
    inc = None
    ratio = None
    for src in sources:
        f = _get_finance(sym, src, period="quarter", get_all=True)
        if f is None:
            continue
        if inc is None:
            inc = _fetch_with_retry(f.income_statement)
        if ratio is None:
            ratio = _fetch_with_retry(f.ratio)
        if inc is not None and ratio is not None:
            break
    return inc, ratio


# ---------------------------------------------------------------------------
# Phân tích + đánh giá
# ---------------------------------------------------------------------------
def _safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def analyze_fundamental(sym, source="VCI"):
    """Phân tích toàn diện một mã CK (SỐ LIỆU THẬT vnstock).

    Trả về dict chứa mọi thông tin cần hiển thị + đánh giá.
    """
    sym = sym.upper().replace(".VN", "").strip()
    result = {
        "sym": sym,
        "ok": False,
        "info": {},
        "fin": {},
        "history": {},
        "verdicts": [],
        "score": 0,
        "summary": "Không đủ dữ liệu để phân tích.",
    }

    info = get_company_info(sym)
    inc, ratio = get_financials(sym)

    has_something = bool(info) or (inc is not None and not inc.empty)
    if not has_something:
        return result

    result["ok"] = True
    result["info"] = info

    # ---- Chỉ số hiện tại từ ratio ----
    fin = {}
    if ratio is not None and not ratio.empty:
        ratio_map = _last_value_row(
            ratio,
            [
                "pe_ratio",
                "pb_ratio",
                "ps_ratio",
                "ev_to_ebitda",
                "roe",
                "roa",
                "debt_to_equity",
                "current_ratio",
                "quick_ratio",
                "market_cap",
                "dividend_yield",
            ],
        )
        pf_map = {}
        for k, v in ratio_map.items():
            # ratio theo quarter: một số chỉ số biểu thị qua ROE/ROA có thể là tỷ lệ thập phân
            pf_map[k] = v
        fin.update(pf_map)
        # giá trị EPS ưu tiên từ ratio nếu có
    result["fin"] = fin

    # ---- Chuỗi hoạt động kinh doanh (doanh thu, lợi nhuận) ----
    hist = {}
    if inc is not None and not inc.empty:
        hist["net_sales"] = _history_vector(inc, ["net_sales"])
        hist["gross_profit"] = _history_vector(inc, ["gross_profit"])
        hist["net_profit"] = _history_vector(inc, ["net_profit_loss_after_tax", "attributable_to_parent_company"])
        hist["eps"] = _history_vector(inc, ["eps_basic_vnd"])
        cur = _last_value_row(
            inc, ["net_sales", "gross_profit", "net_profit_loss_after_tax", "attributable_to_parent_company",
                  "eps_basic_vnd"]
        )
        fin["net_sales"] = cur.get("net_sales")
        fin["gross_profit"] = cur.get("gross_profit")
        fin["net_profit"] = cur.get("net_profit_loss_after_tax") or cur.get("attributable_to_parent_company")
        fin["eps"] = cur.get("eps_basic_vnd")
        # Tăng trưởng so cùng kỳ năm trước (YoY) nếu có đủ 5 kỳ
        ns = hist["net_sales"]
        if len(ns) >= 5 and ns[-5][1] not in (None, 0):
            fin["revenue_yoy"] = _safe_div(ns[-1][1] - ns[-5][1], ns[-5][1])
        np_vec = hist["net_profit"]
        if len(np_vec) >= 5 and np_vec[-5][1] not in (None, 0):
            fin["netprofit_yoy"] = _safe_div(np_vec[-1][1] - np_vec[-5][1], np_vec[-5][1])
        # Biên lợi nhuận
        fin["gross_margin"] = _safe_div(cur.get("gross_profit"), cur.get("net_sales"))
        fin["net_margin"] = _safe_div(
            cur.get("net_profit_loss_after_tax") or cur.get("attributable_to_parent_company"),
            cur.get("net_sales"),
        )
    result["history"] = hist

    # ---- Đánh giá theo quy tắc ----
    verdicts = []

    # 1. Khả năng sinh lời (ROE / ROA)
    roe = _num(fin.get("roe"))
    if roe is not None:
        rv = roe * 100 if abs(roe) <= 1 else roe  # tài khoản thường trả 0.23 -> 23%
        if rv >= 15:
            verdicts.append(("pos", "Khả năng sinh lời tốt", f"ROE {rv:.1f}% (≥15%) — hiệu quả cao trên vốn chủ sở hữu."))
        elif rv >= 8:
            verdicts.append(("neu", "Sinh lời ở mức trung bình", f"ROE {rv:.1f}% (8–15%)."))
        else:
            verdicts.append(("neg", "Sinh lời thấp", f"ROE {rv:.1f}% (<8%) — hiệu quả sử dụng vốn thấp."))
    else:
        verdicts.append(("neu", "Không có ROE", "Thiếu dữ liệu ROE."))

    # 2. Tăng trưởng doanh thu (YoY)
    rv_yoy = _num(fin.get("revenue_yoy"))
    if rv_yoy is not None:
        p = rv_yoy * 100
        if p >= 10:
            verdicts.append(("pos", "Doanh thu tăng trưởng mạnh", f"Doanh thu +{p:.1f}% so cùng kỳ nǎm trước (YoY)."))
        elif p >= 0:
            verdicts.append(("neu", "Doanh thu tăng nhẹ", f"Doanh thu +{p:.1f}% YoY."))
        else:
            verdicts.append(("neg", "Doanh thu suy giảm", f"Doanh thu {p:.1f}% YoY."))
    else:
        verdicts.append(("neu", "Không có dữ liệu tăng trưởng doanh thu", "Thiếu đủ kỳ dữ liệu."))

    # 3. Tăng trưởng lợi nhuận (YoY)
    np_yoy = _num(fin.get("netprofit_yoy"))
    if np_yoy is not None:
        p = np_yoy * 100
        if p >= 10:
            verdicts.append(("pos", "Lợi nhuận tăng mạnh", f"Lợi nhuận +{p:.1f}% YoY."))
        elif p >= 0:
            verdicts.append(("neu", "Lợi nhuận tăng nhẹ", f"Lợi nhuận +{p:.1f}% YoY."))
        else:
            verdicts.append(("neg", "Lợi nhuận suy giảm", f"Lợi nhuận {p:.1f}% YoY."))
    else:
        verdicts.append(("neu", "Không có dữ liệu tăng trưởng lợi nhuận", "Thiếu đủ kỳ dữ liệu."))

    # 4. Biên lợi nhuận ròng
    nm = _num(fin.get("net_margin"))
    if nm is not None:
        p = nm * 100
        if p >= 15:
            verdicts.append(("pos", "Biên lợi nhuận ròng tốt", f"Biên ròng {p:.1f}% (≥15%)."))
        elif p >= 5:
            verdicts.append(("neu", "Biên lợi nhuận chấp nhận được", f"Biên ròng {p:.1f}%."))
        else:
            verdicts.append(("neg", "Biên lợi nhuận mỏng", f"Biên ròng {p:.1f}% (<5%)."))
    else:
        verdicts.append(("neu", "Không có biên lợi nhuận", "Thiếu dữ liệu."))

    # 5. Đòn bẩy nợ (Debt/Equity)
    de = _num(fin.get("debt_to_equity")) or _num(fin.get("debtPerEquity"))
    if de is not None:
        if de < 1.0:
            verdicts.append(("pos", "Đòn bẩy thấp", f"Nợ/VCSH {de:.2f} (<1) — rủi ro tài chính thấp."))
        elif de < 2.0:
            verdicts.append(("neu", "Đòn bẩy trung bình", f"Nợ/VCSH {de:.2f}."))
        else:
            verdicts.append(("neg", "Đòn bẩy cao", f"Nợ/VCSH {de:.2f} (≥2) — rủi ro tài chính cao."))
    else:
        verdicts.append(("neu", "Không có dữ liệu nợ", "Thiếu dữ liệu."))

    # 6. Thanh khoản ngắn hạn (Current ratio)
    cr = _num(fin.get("current_ratio"))
    if cr is not None:
        if cr >= 1.5:
            verdicts.append(("pos", "Thanh khoản tốt", f"Current ratio {cr:.2f} (≥1.5)."))
        elif cr >= 1.0:
            verdicts.append(("neu", "Thanh khoản chấp nhận được", f"Current ratio {cr:.2f}."))
        else:
            verdicts.append(("neg", "Thanh khoản thấp", f"Current ratio {cr:.2f} (<1)."))
    else:
        verdicts.append(("neu", "Không có dữ liệu thanh khoản", "Thiếu dữ liệu."))

    # 7. Định giá (P/E, P/B)
    pe = _num(fin.get("pe_ratio"))
    if pe is not None:
        if 0 < pe <= 15:
            verdicts.append(("pos", f"Định giá hợp lý (P/E {pe:.1f})", "P/E trong vùng thấp (0–15)."))
        elif pe > 25:
            verdicts.append(("neg", f"Định giá cao (P/E {pe:.1f})", "P/E cao (>25) — có thể đắt."))
        else:
            verdicts.append(("neu", f"Định giá trung bình (P/E {pe:.1f})", "P/E 15–25."))
    else:
        verdicts.append(("neu", "Không có P/E", "Thiếu dữ liệu."))

    pb = _num(fin.get("pb_ratio"))
    if pb is not None and pb > 0:
        if pb <= 1.5:
            verdicts.append(("pos", f"P/B thấp ({pb:.2f})", "Giá/bán khá hợp lý so với tài sản."))
        elif pb > 4:
            verdicts.append(("neg", f"P/B cao ({pb:.2f})", "Được định giá cao so với vốn chủ sở hữu."))
        else:
            verdicts.append(("neu", f"P/B trung bình ({pb:.2f})", "Mức trung bình."))

    result["verdicts"] = verdicts

    # ---- Quy về điểm 100 + nhận định tổng ----
    pos = sum(1 for k, _, _ in verdicts if k == "pos")
    neg = sum(1 for k, _, _ in verdicts if k == "neg")
    neu = sum(1 for k, _, _ in verdicts if k == "neu")
    score = round(100 * pos / len(verdicts)) if verdicts else 0
    result["score"] = score

    if score >= 60:
        summary = (f"Nhìn chung tích cực: {pos} yếu tố tốt, {neu} trung tính, {neg} tiêu cực. "
                   f"Doanh nghiệp có nền tảng tài chính khả quan theo số liệu hiện có.")
    elif score >= 40:
        summary = (f"Nhìn chung trung lập: {pos} tốt, {neu} trung tính, {neg} tiêu cực. "
                   f"Có điểm mạnh lẫn điểm yếu, cần cân nhắc thêm.")
    else:
        summary = (f"Nhìn chung tiêu cực: {neg} yếu tố rủi ro đáng chú ý, {neu} trung tính, {pos} tốt. "
                   f"Cần thận trọng.")

    result["summary"] = summary
    return result
