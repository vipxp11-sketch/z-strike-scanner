import streamlit as st
import pandas as pd
import requests

st.set_page_config(layout="wide")
st.title("🔥 Z-Sweep Scanner V4 (Live Data)")

# =========================
# 🔑 API KEY
# =========================
api_key = st.sidebar.text_input("Twelve Data API Key", type="password")

# =========================
# ⏱️ Refresh
# =========================
refresh = st.sidebar.selectbox("Auto Refresh (sec)", [15,30,60], index=1)

symbols = st.text_input("Symbols", "SPY,QQQ,NVDA,TSLA,AMD").split(",")

# =========================
# 📊 Fetch Data
# =========================
def get_data(symbol, interval):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize=10&apikey={api_key}"
    r = requests.get(url).json()

    # أخطاء API
    if "message" in r:
        st.error(f"{symbol}: {r['message']}")
        return None

    if "status" in r and r["status"] == "error":
        st.error(f"{symbol}: {r}")
        return None

    if "values" not in r:
        return None

    df = pd.DataFrame(r["values"])
    df = df.iloc[::-1]

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna()

    return df

# =========================
# 🔍 Logic
# =========================
def analyze(df):
    if df is None or len(df) < 3:
        return None

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    sweep = "❌"
    direction = "NONE"

    if curr["low"] < prev["low"] and curr["close"] > prev["low"]:
        sweep = "أدنى"
        direction = "CALL"

    elif curr["high"] > prev["high"] and curr["close"] < prev["high"]:
        sweep = "أعلى"
        direction = "PUT"

    rng = prev["high"] - prev["low"]
    close_pct = ((curr["close"] - prev["low"]) / rng * 100) if rng != 0 else 0

    vol = "⬆️" if curr["volume"] > prev["volume"] else "⬇️"
    prev_color = "🟢" if prev["close"] > prev["open"] else "🔴"

    grade = "Fake"
    entry = "❌"

    if direction == "CALL":
        if prev_color == "🔴" and close_pct >= 80 and vol == "⬆️":
            grade = "A+"
            entry = "🟢 CALL قوي"
        elif close_pct >= 60:
            grade = "B"

    elif direction == "PUT":
        if prev_color == "🟢" and close_pct <= 20 and vol == "⬆️":
            grade = "A+"
            entry = "🔴 PUT قوي"
        elif close_pct <= 40:
            grade = "B"

    return {
        "Sweep": sweep,
        "Direction": direction,
        "Close%": round(close_pct,1),
        "Vol": vol,
        "Grade": grade,
        "Entry": entry
    }

# =========================
# 🚀 Scan
# =========================
rows = []

if api_key:
    for sym in symbols:
        sym = sym.strip().upper()

        df = get_data(sym, "5min")
        res = analyze(df)

        if res:
            rows.append({
                "Symbol": sym,
                **res
            })

# =========================
# 📊 Output
# =========================
if rows:
    df_out = pd.DataFrame(rows)

    st.subheader("📊 Scanner Results")
    st.dataframe(df_out, use_container_width=True)

    # فلترة A+
    a_plus = df_out[df_out["Grade"] == "A+"]
    if not a_plus.empty:
        st.success("🔥 A+ Setups")
        st.dataframe(a_plus, use_container_width=True)
else:
    st.warning("⚠️ No data. Check API key or symbols.")
