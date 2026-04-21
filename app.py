import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import requests

st.set_page_config(layout="wide")

st.title("📊 Gold Flow Dashboard (GLD / SHNY Timing)")

# --- DATA FETCH ---
@st.cache_data
def load_data():
    try:
        gld = yf.download("GLD", period="2y", progress=False)
        shny = yf.download("SHNY", period="2y", progress=False)
        return gld, shny
    except Exception as e:
        st.error(f"Data load failed: {e}")
        return pd.DataFrame(), pd.DataFrame()

@st.cache_data
def load_imf_gold_data():
    url = "https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/IFS/M.GOLDMON_..?startPeriod=2015"
    
    try:
        r = requests.get(url)
        data = r.json()

        series = data['CompactData']['DataSet']['Series']

        records = []

        for country in series:
            country_name = country.get('@REF_AREA', 'Unknown')
            obs = country.get('Obs', [])

            for o in obs:
                records.append({
                    'Country': country_name,
                    'Date': o['@TIME_PERIOD'],
                    'Gold Holdings (Tonnes)': float(o['@OBS_VALUE'])
                })

        df = pd.DataFrame(records)
        df['Date'] = pd.to_datetime(df['Date'])

        return df

    except Exception as e:
        st.error(f"IMF data load failed: {e}")
        return pd.DataFrame()

def process_cb_purchases(df):
    if df.empty:
        return pd.DataFrame()

    df = df.sort_values(['Country', 'Date'])

    df['Change'] = df.groupby('Country')['Gold Holdings (Tonnes)'].diff()

    monthly = df.groupby('Date')['Change'].sum().reset_index()

    monthly = monthly.rename(columns={'Change': 'Net Purchases (Tonnes)'})
    monthly = monthly.set_index('Date')

    return monthly


gld, shny = load_data()
# Fix yfinance column structure
if isinstance(gld.columns, pd.MultiIndex):
    gld.columns = gld.columns.get_level_values(0)

if isinstance(shny.columns, pd.MultiIndex):
    shny.columns = shny.columns.get_level_values(0)

# --- CALCULATIONS ---

gld['MA50'] = gld['Close'].rolling(50).mean()
gld['MA200'] = gld['Close'].rolling(200).mean()

gld['Returns'] = gld['Close'].pct_change()
volatility = gld['Returns'].rolling(30).std() * np.sqrt(252)

# --- TOP BAR ---
col1, col2, col3 = st.columns(3)

gld_price = gld['Close'].dropna().iloc[-1]
col1.metric("GLD Price", f"${gld_price:.2f}")
shny_price = shny['Close'].dropna().iloc[-1]
col2.metric("SHNY Price", f"${shny_price:.2f}")
col3.metric("30D Volatility", f"{volatility.iloc[-1]:.2%}")

# --- TREND SIGNAL ---
if gld['Close'].iloc[-1] > gld['MA50'].iloc[-1] > gld['MA200'].iloc[-1]:
    regime = "🟢 TRENDING (SHNY OK)"
elif gld['Close'].iloc[-1] < gld['MA50'].iloc[-1]:
    regime = "🔴 WEAK / CHOPPY"
else:
    regime = "🟡 NEUTRAL"

st.subheader(f"Market Regime: {regime}")

# --- CHART ---
st.subheader("GLD Trend")
st.line_chart(gld[['Close', 'MA50', 'MA200']])

# --- VOLATILITY ---
st.subheader("Volatility")
st.line_chart(volatility)


imf_raw = load_imf_gold_data()
cb_data = process_cb_purchases(imf_raw)
cb_data = cb_data.tail(24)

st.subheader("Central Bank Buying Trend (IMF Data)")
st.bar_chart(cb_data)

# --- SCORECARD ---
score = 0

# Trend
if regime.startswith("🟢"):
    score += 1

# Volatility
if volatility.iloc[-1] < 0.15:
    score += 1

# Momentum
if gld['Close'].iloc[-1] > gld['MA50'].iloc[-1]:
    score += 1

st.subheader("Decision Score")
st.write(f"Score: {score} / 3")

if score >= 3:
    st.success("GO SHNY")
elif score == 2:
    st.warning("HOLD GLD")
else:
    st.error("RISK OFF")

# --- FOOTER ---
st.caption("Note: Replace simulated central bank data with IMF/WGC sources for production use.")
