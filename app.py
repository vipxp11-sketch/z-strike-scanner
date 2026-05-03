import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Z-Sweep Market Scanner V3", layout="wide")

st.title("🔥 Z-Sweep Market Scanner V3")
st.caption("Liquidity Sweep + Close% + Volume + Impulse + Wave + Bias")

# =========================
# Settings
# =========================
DEFAULT_SYMBOLS = "SPY,QQQ,NVDA,TSLA,AMD,META,AAPL,MSFT,AMZN,GOOGL,AVGO,PLTR,SMCI,COIN,MSTR"

with st.sidebar:
    st.header("⚙️ الإعدادات")
    symbols_input = st.text_area("الرموز", DEFAULT_SYMBOLS, height=120)
    exec_timeframes = st.multiselect(
        "فريمات التنفيذ",
        ["5m", "15m", "30m", "1h", "4h"],
        default=["5m", "15m"]
    )
    show_grades = st.multiselect(
        "إظهار التصنيفات",
        ["A+", "A", "B"],
        default=["A+", "A", "B"]
    )
    only_allowed = st.checkbox("إظهار الصفقات المسموحة فقط حسب Bias", value=False)
    hide_fake = st.checkbox("إخفاء Fake", value=True)
    scan_button = st.button("🚀 ابدأ الفحص", use_container_width=True)

symbols = [s.strip().upper() for s in symbols_input.replace("\n", ",").split(",") if s.strip()]

# =========================
# Data
# =========================
@st.cache_data(ttl=60)
def download_data(symbol: str, interval: str, period: str):
    try:
        df = yf.download(
            symbol,
            interval=interval,
            period=period,
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        needed = ["Open", "High", "Low", "Close", "Volume"]
        df = df[[c for c in needed if c in df.columns]].dropna()
        if len(df) == 0:
            return None
        return df
    except Exception:
        return None


def candle_color(row):
    if float(row["Close"]) > float(row["Open"]):
        return "🟢"
    if float(row["Close"]) < float(row["Open"]):
        return "🔴"
    return "⚪"


def sweep_type(curr, prev):
    """Trap Sweep: break previous high/low then close back inside previous candle range."""
    prev_high = float(prev["High"])
    prev_low = float(prev["Low"])
    curr_high = float(curr["High"])
    curr_low = float(curr["Low"])
    curr_close = float(curr["Close"])

    swept_low = curr_low < prev_low and curr_close > prev_low
    swept_high = curr_high > prev_high and curr_close < prev_high

    if swept_low and swept_high:
        return "⚠️ أعلى+أدنى", "BOTH"
    if swept_low:
        return "✅ أدنى", "CALL"
    if swept_high:
        return "✅ أعلى", "PUT"
    return "❌", "NONE"


def close_percent(curr, prev):
    prev_high = float(prev["High"])
    prev_low = float(prev["Low"])
    curr_close = float(curr["Close"])
    rng = prev_high - prev_low
    if rng == 0:
        return 0.0
    return ((curr_close - prev_low) / rng) * 100


def detect_big_tf_status(symbol):
    df = download_data(symbol, "1d", "18mo")
    if df is None or len(df) < 40:
        return {
            "Month": "⚪", "Month Sweep": "غير كافي",
            "Week": "⚪", "Week Sweep": "غير كافي",
            "Day": "⚪", "Day Sweep": "غير كافي",
            "Bias": "⚪ حيادي"
        }

    # Daily previous completed candle
    prev_day = df.iloc[-2]
    prev_prev_day = df.iloc[-3]
    day_color = candle_color(prev_day)
    day_sweep, _ = sweep_type(prev_day, prev_prev_day)

    # Weekly completed candle
    weekly = df.resample("W").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
    }).dropna()
    if len(weekly) >= 3:
        prev_week = weekly.iloc[-2]
        prev_prev_week = weekly.iloc[-3]
        week_color = candle_color(prev_week)
        week_sweep, _ = sweep_type(prev_week, prev_prev_week)
    else:
        week_color, week_sweep = "⚪", "غير كافي"

    # Monthly completed candle
    monthly = df.resample("ME").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
    }).dropna()
    if len(monthly) >= 3:
        prev_month = monthly.iloc[-2]
        prev_prev_month = monthly.iloc[-3]
        month_color = candle_color(prev_month)
        month_sweep, _ = sweep_type(prev_month, prev_prev_month)
    else:
        month_color, month_sweep = "⚪", "غير كافي"

    green = [month_color, week_color, day_color].count("🟢")
    red = [month_color, week_color, day_color].count("🔴")

    if green >= 2:
        bias = "🟢 CALL"
    elif red >= 2:
        bias = "🔴 PUT"
    else:
        bias = "⚪ حيادي"

    # If major liquidity sweep exists, it can tilt bias when general status is neutral.
    if bias == "⚪ حيادي":
        if day_sweep == "✅ أدنى" or week_sweep == "✅ أدنى":
            bias = "🟢 CALL"
        elif day_sweep == "✅ أعلى" or week_sweep == "✅ أعلى":
            bias = "🔴 PUT"

    return {
        "Month": month_color, "Month Sweep": month_sweep,
        "Week": week_color, "Week Sweep": week_sweep,
        "Day": day_color, "Day Sweep": day_sweep,
        "Bias": bias
    }


def detect_wave(df):
    """
    Practical wave phase:
    ① بداية بعد ضعف
    ② استمرار مبكر
    ③ امتداد قوي
    ④ ضعف
    ⑤ متأخر
    """
    if df is None or len(df) < 8:
        return "—"

    recent = df.iloc[-6:].copy()
    bodies = (recent["Close"] - recent["Open"]).abs()
    ranges = (recent["High"] - recent["Low"]).replace(0, np.nan)
    body_ratio = (bodies / ranges).fillna(0)
    closes = recent["Close"]
    volumes = recent["Volume"]

    curr_body_ratio = float(body_ratio.iloc[-1])
    avg_body_ratio = float(body_ratio.iloc[:-1].mean())
    curr_vol = float(volumes.iloc[-1])
    avg_vol = float(volumes.iloc[:-1].mean()) if float(volumes.iloc[:-1].mean()) != 0 else 1

    last3_up = closes.iloc[-1] > closes.iloc[-2] > closes.iloc[-3]
    last3_down = closes.iloc[-1] < closes.iloc[-2] < closes.iloc[-3]
    impulse_now = curr_body_ratio > avg_body_ratio and curr_vol > avg_vol
    prior_weak = float(body_ratio.iloc[-4:-1].mean()) < 0.45

    if impulse_now and prior_weak:
        return "①"
    if impulse_now and curr_vol > avg_vol * 1.4:
        return "③"
    if impulse_now and (last3_up or last3_down):
        return "②"
    if curr_body_ratio < 0.35:
        return "④"
    if (last3_up or last3_down) and curr_vol < avg_vol:
        return "⑤"
    return "②"


def analyze_tf(symbol, tf):
    period_map = {
        "5m": "5d",
        "15m": "10d",
        "30m": "30d",
        "1h": "60d",
        "4h": "6mo",
    }
    yf_interval = "1h" if tf == "4h" else tf
    df = download_data(symbol, yf_interval, period_map.get(tf, "5d"))
    if df is None or len(df) < 8:
        return None

    # Build 4H from 1H if needed
    if tf == "4h":
        df = df.resample("4h").agg({
            "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
        }).dropna()
        if len(df) < 8:
            return None

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    sweep, direction = sweep_type(curr, prev)
    prev_color = candle_color(prev)
    cpct = close_percent(curr, prev)

    prev_open = float(prev["Open"])
    prev_close = float(prev["Close"])
    curr_open = float(curr["Open"])
    curr_close = float(curr["Close"])
    curr_volume = float(curr["Volume"])
    prev_volume = float(prev["Volume"])

    vol_state = "⬆️" if curr_volume > prev_volume else "⬇️"
    curr_body = abs(curr_close - curr_open)
    prev_body = abs(prev_close - prev_open)
    impulse = "⚡" if curr_body > prev_body and vol_state == "⬆️" else "❄️"
    wave = detect_wave(df)
    valid_wave = wave in ["①", "②"]

    grade = "Fake"
    entry = "❌"
    preview = "—"

    if direction == "CALL":
        if cpct >= 70 and vol_state == "⬆️":
            preview = "جاهز عند الإغلاق" if valid_wave else "متأخر/مراقبة"
        if prev_color == "🔴" and cpct >= 80 and vol_state == "⬆️" and impulse == "⚡" and valid_wave:
            grade = "A+"
            entry = "🟢 CALL قوي"
        elif prev_color == "🔴" and cpct >= 70 and vol_state == "⬆️" and valid_wave:
            grade = "A"
            entry = "🟢 CALL"
        elif cpct >= 60 and wave in ["①", "②", "③"]:
            grade = "B"
            entry = "مراقبة CALL"

    elif direction == "PUT":
        if cpct <= 30 and vol_state == "⬆️":
            preview = "جاهز عند الإغلاق" if valid_wave else "متأخر/مراقبة"
        if prev_color == "🟢" and cpct <= 20 and vol_state == "⬆️" and impulse == "⚡" and valid_wave:
            grade = "A+"
            entry = "🔴 PUT قوي"
        elif prev_color == "🟢" and cpct <= 30 and vol_state == "⬆️" and valid_wave:
            grade = "A"
            entry = "🔴 PUT"
        elif cpct <= 40 and wave in ["①", "②", "③"]:
            grade = "B"
            entry = "مراقبة PUT"

    price_change_pct = ((curr_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0

    return {
        "TF": tf,
        "Sweep": sweep,
        "Direction": direction,
        "Prev": prev_color,
        "Prev O": round(prev_open, 2),
        "Prev C": round(prev_close, 2),
        "Price": round(curr_close, 2),
        "Δ%": round(price_change_pct, 2),
        "Close%": round(cpct, 1),
        "Vol": vol_state,
        "Impulse": impulse,
        "Wave": wave,
        "Grade": grade,
        "Entry": entry,
        "Preview": preview,
    }


def allowed_status(bias, direction, grade):
    if grade == "Fake" or direction in ["NONE", "BOTH"]:
        return "❌ Blocked"
    if bias == "🟢 CALL" and direction == "CALL":
        return "✅ Allowed"
    if bias == "🔴 PUT" and direction == "PUT":
        return "✅ Allowed"
    if bias == "⚪ حيادي":
        return "⚪ Neutral"
    return "❌ Blocked"

# =========================
# UI
# =========================
if not scan_button:
    st.info("ضع الرموز من الشريط الجانبي ثم اضغط ابدأ الفحص.")
    st.markdown("""
### قواعد V3 المختصرة
- **CALL**: Bias CALL + Sweep أدنى + Prev 🔴 + Close% ≥ 70 + Vol ⬆️ + Wave ①/②
- **PUT**: Bias PUT + Sweep أعلى + Prev 🟢 + Close% ≤ 30 + Vol ⬆️ + Wave ①/②
- **A+**: أقوى فرصة، **B**: مراقبة، **Fake**: مخفي غالبًا
""")
else:
    rows = []
    headers = []
    progress = st.progress(0)
    total = max(len(symbols), 1)

    with st.spinner("جاري الفحص..."):
        for i, symbol in enumerate(symbols, start=1):
            big = detect_big_tf_status(symbol)
            headers.append({"Symbol": symbol, **big})

            for tf in exec_timeframes:
                data = analyze_tf(symbol, tf)
                if not data:
                    continue

                if hide_fake and data["Grade"] == "Fake":
                    continue
                if data["Grade"] not in show_grades:
                    continue

                status = allowed_status(big["Bias"], data["Direction"], data["Grade"])
                if only_allowed and status != "✅ Allowed":
                    continue

                rows.append({
                    "Symbol": symbol,
                    "Bias": big["Bias"],
                    "Month": big["Month"],
                    "Month Sweep": big["Month Sweep"],
                    "Week": big["Week"],
                    "Week Sweep": big["Week Sweep"],
                    "Day": big["Day"],
                    "Day Sweep": big["Day Sweep"],
                    "TF": data["TF"],
                    "Sweep": data["Sweep"],
                    "Prev": data["Prev"],
                    "Prev O": data["Prev O"],
                    "Prev C": data["Prev C"],
                    "Price": data["Price"],
                    "Δ%": data["Δ%"],
                    "Close%": data["Close%"],
                    "Vol": data["Vol"],
                    "Impulse": data["Impulse"],
                    "Wave": data["Wave"],
                    "Grade": data["Grade"],
                    "Entry": data["Entry"],
                    "Preview": data["Preview"],
                    "Status": status,
                })

            progress.progress(i / total)

    st.subheader("🧠 Market Status")
    if headers:
        st.dataframe(pd.DataFrame(headers), use_container_width=True)

    st.subheader("📊 Scanner Results")
    if rows:
        result = pd.DataFrame(rows)
        grade_order = {"A+": 1, "A": 2, "B": 3}
        status_order = {"✅ Allowed": 1, "⚪ Neutral": 2, "❌ Blocked": 3}
        result["grade_sort"] = result["Grade"].map(grade_order).fillna(99)
        result["status_sort"] = result["Status"].map(status_order).fillna(99)
        result = result.sort_values(["status_sort", "grade_sort", "Symbol", "TF"]).drop(columns=["grade_sort", "status_sort"])
        st.dataframe(result, use_container_width=True)
        csv = result.to_csv(index=False).encode("utf-8-sig")
        st.download_button("تحميل النتائج CSV", csv, "z_sweep_results.csv", "text/csv")
    else:
        st.warning("لا توجد فرص مطابقة الآن.")

    st.caption(f"آخر فحص: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
