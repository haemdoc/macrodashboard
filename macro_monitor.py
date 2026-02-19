"""
╔══════════════════════════════════════════════════════════════════╗
║                     MACRO MONITOR DASHBOARD                      ║
║              Live Data · No Bloomberg Required                   ║
╚══════════════════════════════════════════════════════════════════╝

SETUP:
    pip install streamlit yfinance fredapi pandas plotly requests numpy

    # Get a free FRED API key at: https://fred.stlouisfed.org/docs/api/api_key.html
    # Then either:
    #   1. Set environment variable: export FRED_API_KEY=your_key_here
    #   2. Or paste it directly into the FRED_API_KEY variable below

RUN:
    streamlit run macro_monitor.py

"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import os
FRED_API_KEY = os.environ.get("FRED_API_KEY", "YOUR_FRED_API_KEY_HERE")

# Chart theme
CHART_TEMPLATE = "plotly_dark"
BG_COLOR = "#0a0e17"
CARD_BG = "#111827"
GRID_COLOR = "#1e293b"
ACCENT_CYAN = "#00e5ff"
ACCENT_PURPLE = "#7c4dff"
ACCENT_ORANGE = "#ff6e40"
ACCENT_GREEN = "#69f0ae"
ACCENT_YELLOW = "#ffd740"
ACCENT_RED = "#ef4444"

PLOTLY_LAYOUT = dict(
    template=CHART_TEMPLATE,
    paper_bgcolor=CARD_BG,
    plot_bgcolor=CARD_BG,
    font=dict(family="JetBrains Mono, SF Mono, monospace", color="#e2e8f0", size=11),
    margin=dict(l=40, r=20, t=40, b=30),
    xaxis=dict(gridcolor=GRID_COLOR, showgrid=True),
    yaxis=dict(gridcolor=GRID_COLOR, showgrid=True),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
    height=380,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA FETCHING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@st.cache_data(ttl=900)  # Cache for 15 minutes
def fetch_yfinance_data(ticker, period="2y", interval="1d"):
    """Fetch data from Yahoo Finance."""
    import yfinance as yf
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        return data
    except Exception as e:
        st.warning(f"Could not fetch {ticker}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=900)
def fetch_fred_series(series_id, start_date=None):
    """Fetch data from FRED API."""
    from fredapi import Fred
    try:
        fred = Fred(api_key=FRED_API_KEY)
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
        data = fred.get_series(series_id, observation_start=start_date)
        return data.dropna()
    except Exception as e:
        st.warning(f"Could not fetch FRED series {series_id}: {e}")
        return pd.Series(dtype=float)


@st.cache_data(ttl=900)
def fetch_yield_curve():
    """Fetch current US Treasury yield curve from FRED."""
    tenors = {
        "1M": "DGS1MO", "3M": "DGS3MO", "6M": "DGS6MO",
        "1Y": "DGS1", "2Y": "DGS2", "3Y": "DGS3",
        "5Y": "DGS5", "7Y": "DGS7", "10Y": "DGS10",
        "20Y": "DGS20", "30Y": "DGS30",
    }
    from fredapi import Fred
    fred = Fred(api_key=FRED_API_KEY)
    
    results = {}
    for label, series_id in tenors.items():
        try:
            s = fred.get_series(series_id, observation_start=(datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"))
            s = s.dropna()
            if len(s) > 0:
                results[label] = {
                    "current": s.iloc[-1],
                    "1w_ago": s.iloc[-6] if len(s) > 5 else s.iloc[0],
                    "1m_ago": s.iloc[0],
                }
        except:
            pass
    return results


@st.cache_data(ttl=900)
def fetch_market_indices():
    """Fetch major global market indices for direction signals."""
    import yfinance as yf
    indices = {
        # US
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "Russell 2000": "^RUT",
        # Europe
        "STOXX 600": "^STOXX",
        "DAX": "^GDAXI",
        "FTSE 100": "^FTSE",
        "CAC 40": "^FCHI",
        # Asia
        "Nikkei 225": "^N225",
        "Hang Seng": "^HSI",
        "Shanghai Comp": "000001.SS",
        "KOSPI": "^KS11",
        "ASX 200": "^AXJO",
    }
    
    results = {}
    for name, ticker in indices.items():
        try:
            data = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if len(data) > 0:
                current = data["Close"].iloc[-1]
                sma_50 = data["Close"].rolling(50).mean().iloc[-1]
                sma_20 = data["Close"].rolling(20).mean().iloc[-1]
                ret_1w = (data["Close"].iloc[-1] / data["Close"].iloc[-6] - 1) * 100 if len(data) > 5 else 0
                ret_1m = (data["Close"].iloc[-1] / data["Close"].iloc[-22] - 1) * 100 if len(data) > 22 else 0
                ret_3m = (data["Close"].iloc[-1] / data["Close"].iloc[-66] - 1) * 100 if len(data) > 66 else 0
                
                # Handle potential numpy arrays (from multi-column DataFrames)
                def to_float(val):
                    if hasattr(val, 'item'):
                        return float(val.item())
                    return float(val)
                
                current = to_float(current)
                sma_50 = to_float(sma_50)
                sma_20 = to_float(sma_20)
                ret_1w = to_float(ret_1w)
                ret_1m = to_float(ret_1m)
                ret_3m = to_float(ret_3m)
                
                # Bull/Bear signal logic
                score = 0
                if current > sma_50: score += 1
                if current > sma_20: score += 1
                if ret_1m > 0: score += 1
                if ret_3m > 0: score += 1
                
                if score >= 3:
                    signal = "🟢 BULL"
                elif score >= 2:
                    signal = "🟡 NEUTRAL"
                else:
                    signal = "🔴 BEAR"
                
                results[name] = {
                    "price": current,
                    "1w": ret_1w,
                    "1m": ret_1m,
                    "3m": ret_3m,
                    "vs_sma50": ((current / sma_50) - 1) * 100,
                    "signal": signal,
                    "data": data,
                }
        except Exception as e:
            pass
    
    return results


@st.cache_data(ttl=900)
def fetch_fx_data():
    """Fetch FX pairs for analysis and recommendations."""
    import yfinance as yf
    pairs = {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "USDJPY=X",
        "USD/CHF": "USDCHF=X",
        "AUD/USD": "AUDUSD=X",
        "USD/CAD": "USDCAD=X",
        "NZD/USD": "NZDUSD=X",
        "EUR/GBP": "EURGBP=X",
        "EUR/JPY": "EURJPY=X",
        "GBP/JPY": "GBPJPY=X",
    }
    
    results = {}
    for name, ticker in pairs.items():
        try:
            data = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if len(data) > 0:
                current = data["Close"].iloc[-1]
                sma_50 = data["Close"].rolling(50).mean().iloc[-1]
                sma_20 = data["Close"].rolling(20).mean().iloc[-1]
                ret_1w = (data["Close"].iloc[-1] / data["Close"].iloc[-6] - 1) * 100 if len(data) > 5 else 0
                ret_1m = (data["Close"].iloc[-1] / data["Close"].iloc[-22] - 1) * 100 if len(data) > 22 else 0
                ret_3m = (data["Close"].iloc[-1] / data["Close"].iloc[-66] - 1) * 100 if len(data) > 66 else 0
                
                # Volatility (20-day realized)
                returns = data["Close"].pct_change().dropna()
                vol_20d = returns.tail(20).std() * np.sqrt(252) * 100
                
                def to_float(val):
                    if hasattr(val, 'item'):
                        return float(val.item())
                    return float(val)
                
                current = to_float(current)
                sma_50 = to_float(sma_50)
                sma_20 = to_float(sma_20)
                ret_1w = to_float(ret_1w)
                ret_1m = to_float(ret_1m)
                ret_3m = to_float(ret_3m)
                vol_20d = to_float(vol_20d)
                
                # Trend / momentum scoring
                score = 0
                if current > sma_50: score += 1
                if current > sma_20: score += 1
                if ret_1m > 0: score += 1
                if ret_3m > 0: score += 1
                
                if score >= 3:
                    trend = "⬆ Bullish"
                elif score >= 2:
                    trend = "➡ Neutral"
                else:
                    trend = "⬇ Bearish"
                
                results[name] = {
                    "price": current,
                    "1w": ret_1w,
                    "1m": ret_1m,
                    "3m": ret_3m,
                    "vol": vol_20d,
                    "vs_sma50": ((current / sma_50) - 1) * 100,
                    "trend": trend,
                    "data": data,
                }
        except:
            pass
    
    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FX RECOMMENDATION ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_fx_recommendations(fx_data):
    """
    Generate FX trade ideas based on trend, momentum, and mean-reversion signals.
    DISCLAIMER: These are quantitative signals only, NOT financial advice.
    """
    recommendations = []
    
    for pair, info in fx_data.items():
        score = 0
        reasons = []
        
        # Trend following: price above/below 50 SMA
        if info["vs_sma50"] > 1.0:
            score += 2
            reasons.append(f"Trading {info['vs_sma50']:.1f}% above 50-day SMA")
        elif info["vs_sma50"] < -1.0:
            score -= 2
            reasons.append(f"Trading {abs(info['vs_sma50']):.1f}% below 50-day SMA")
        
        # Momentum: 1-month return
        if info["1m"] > 1.5:
            score += 1
            reasons.append(f"Strong 1M momentum (+{info['1m']:.1f}%)")
        elif info["1m"] < -1.5:
            score -= 1
            reasons.append(f"Weak 1M momentum ({info['1m']:.1f}%)")
        
        # Mean reversion: if 3M move is extreme but 1W reversing
        if info["3m"] > 3.0 and info["1w"] < -0.5:
            score -= 1
            reasons.append("Possible mean-reversion after extended rally")
        elif info["3m"] < -3.0 and info["1w"] > 0.5:
            score += 1
            reasons.append("Possible mean-reversion after extended sell-off")
        
        # Volatility context
        if info["vol"] > 12:
            reasons.append(f"⚠ Elevated volatility ({info['vol']:.1f}% annualized)")
        
        if abs(score) >= 2:
            direction = "LONG" if score > 0 else "SHORT"
            confidence = "High" if abs(score) >= 3 else "Medium"
            recommendations.append({
                "pair": pair,
                "direction": direction,
                "confidence": confidence,
                "score": score,
                "reasons": reasons,
                "current": info["price"],
                "vol": info["vol"],
            })
    
    # Sort by absolute score
    recommendations.sort(key=lambda x: abs(x["score"]), reverse=True)
    return recommendations


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CHART HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def make_area_chart(df, y_col, title, color=ACCENT_CYAN, height=380):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df[y_col],
        fill="tozeroy",
        line=dict(color=color, width=2),
        fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.15)",
        name=y_col,
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title=dict(text=title, font=dict(size=13)), height=height)
    return fig


def make_line_chart(series_dict, title, height=380):
    """series_dict: {name: (df, col, color)}"""
    fig = go.Figure()
    for name, (df, col, color) in series_dict.items():
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col],
            line=dict(color=color, width=2),
            name=name,
        ))
    fig.update_layout(**PLOTLY_LAYOUT, title=dict(text=title, font=dict(size=13)), height=height)
    return fig


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STREAMLIT APP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.set_page_config(
    page_title="Macro Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for dark terminal aesthetic
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=DM+Sans:wght@400;500;700&display=swap');
    
    .stApp {
        background-color: #0a0e17;
        color: #e2e8f0;
    }
    
    [data-testid="stHeader"] {
        background-color: #0a0e17;
    }
    
    [data-testid="stSidebar"] {
        background-color: #111827;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #111827;
        padding: 8px 12px;
        border-radius: 10px;
        border: 1px solid #1e293b;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: #94a3b8;
        background-color: transparent;
        border-radius: 6px;
        padding: 8px 16px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: rgba(0, 229, 255, 0.1) !important;
        color: #00e5ff !important;
        border: 1px solid rgba(0, 229, 255, 0.3);
    }
    
    .metric-card {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
    }
    
    .metric-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin-bottom: 6px;
    }
    
    .metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 22px;
        font-weight: 700;
        color: #e2e8f0;
    }
    
    .metric-change-up { color: #22c55e; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
    .metric-change-down { color: #ef4444; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
    
    .section-header {
        font-family: 'DM Sans', sans-serif;
        font-size: 20px;
        font-weight: 700;
        color: #e2e8f0;
        padding: 8px 0;
        margin-top: 16px;
        border-left: 3px solid;
        border-image: linear-gradient(180deg, #00e5ff, #7c4dff) 1;
        padding-left: 12px;
    }
    
    .section-sub {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        color: #64748b;
        padding-left: 15px;
    }
    
    .signal-bull { 
        background: rgba(34, 197, 94, 0.12); 
        border: 1px solid rgba(34, 197, 94, 0.3); 
        border-radius: 6px; 
        padding: 4px 10px; 
        color: #22c55e;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
    }
    .signal-bear { 
        background: rgba(239, 68, 68, 0.12); 
        border: 1px solid rgba(239, 68, 68, 0.3); 
        border-radius: 6px; 
        padding: 4px 10px; 
        color: #ef4444;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
    }
    .signal-neutral { 
        background: rgba(255, 215, 64, 0.12); 
        border: 1px solid rgba(255, 215, 64, 0.3); 
        border-radius: 6px; 
        padding: 4px 10px; 
        color: #ffd740;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
    }
    
    .rec-card {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 18px;
        margin-bottom: 12px;
    }
    
    .rec-long {
        border-left: 3px solid #22c55e;
    }
    
    .rec-short {
        border-left: 3px solid #ef4444;
    }
    
    .data-source-box {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 16px 20px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        color: #94a3b8;
        margin-top: 32px;
    }
    
    div[data-testid="stMetric"] {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 12px 16px;
    }
    
    div[data-testid="stMetric"] label {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 11px !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    .stDataFrame {
        font-family: 'JetBrains Mono', monospace;
    }
    
    h1, h2, h3 {
        font-family: 'DM Sans', sans-serif !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ──
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 4px;">
        <div style="width:38px;height:38px;background:linear-gradient(135deg,#00e5ff,#7c4dff);
                    border-radius:10px;display:flex;align-items:center;justify-content:center;
                    font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:800;color:#000;">M</div>
        <div>
            <div style="font-family:'DM Sans',sans-serif;font-size:22px;font-weight:700;letter-spacing:-0.5px;color:#e2e8f0;">
                MACRO MONITOR</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#64748b;letter-spacing:1.5px;">
                LIVE DATA · FRED + YAHOO FINANCE · NO BLOOMBERG REQUIRED</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
with col_h2:
    st.markdown(f"""
    <div style="text-align:right;font-family:'JetBrains Mono',monospace;font-size:12px;color:#64748b;padding-top:10px;">
        {datetime.now().strftime("%a, %b %d %Y")}<br>
        <span style="color:#00e5ff;font-size:14px;">{datetime.now().strftime("%H:%M:%S")}</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ── Tabs ──
tab_overview, tab_rates, tab_credit, tab_markets, tab_fx, tab_vol = st.tabs([
    "📊 Overview", "📈 Rates & Yields", "💳 Credit", "🌍 Market Direction", "💱 FX & Recommendations", "📉 Volatility"
])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: OVERVIEW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_overview:
    st.markdown('<div class="section-header">Key Macro Metrics</div>', unsafe_allow_html=True)
    
    with st.spinner("Fetching live data..."):
        # Fetch key tickers
        tnx = fetch_yfinance_data("^TNX", period="6mo")    # 10Y yield
        vix = fetch_yfinance_data("^VIX", period="6mo")     # VIX
        dxy = fetch_yfinance_data("DX-Y.NYB", period="6mo") # Dollar index
        spx = fetch_yfinance_data("^GSPC", period="6mo")    # S&P 500
        gold = fetch_yfinance_data("GC=F", period="6mo")    # Gold
        oil = fetch_yfinance_data("CL=F", period="6mo")     # Crude Oil
    
    # Metric row
    mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
    
    def safe_metric(col, label, data, fmt=".2f", suffix=""):
        with col:
            if len(data) > 1:
                current = float(data["Close"].iloc[-1])
                prev = float(data["Close"].iloc[-2])
                delta = current - prev
                st.metric(label, f"{current:{fmt}}{suffix}", f"{delta:+.2f}")
            else:
                st.metric(label, "N/A")
    
    safe_metric(mc1, "S&P 500", spx, fmt=",.0f")
    safe_metric(mc2, "UST 10Y", tnx, suffix="%")
    safe_metric(mc3, "VIX", vix)
    safe_metric(mc4, "DXY", dxy)
    safe_metric(mc5, "GOLD", gold, fmt=",.0f")
    safe_metric(mc6, "WTI CRUDE", oil)
    
    st.markdown("")
    
    # Mini charts row
    c1, c2 = st.columns(2)
    with c1:
        if len(spx) > 0:
            fig = make_area_chart(spx, "Close", "S&P 500", ACCENT_GREEN, height=300)
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        if len(tnx) > 0:
            fig = make_area_chart(tnx, "Close", "US 10Y Yield (%)", ACCENT_CYAN, height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    c3, c4 = st.columns(2)
    with c3:
        if len(vix) > 0:
            fig = make_area_chart(vix, "Close", "VIX", ACCENT_RED, height=300)
            fig.add_hline(y=20, line_dash="dash", line_color=ACCENT_ORANGE, annotation_text="Elevated",
                         annotation_font_color=ACCENT_ORANGE, annotation_font_size=10)
            st.plotly_chart(fig, use_container_width=True)
    with c4:
        if len(dxy) > 0:
            fig = make_area_chart(dxy, "Close", "DXY — Dollar Index", ACCENT_YELLOW, height=300)
            st.plotly_chart(fig, use_container_width=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: RATES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_rates:
    st.markdown('<div class="section-header">Rates & Yields</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">U.S. Treasury curves, spreads & real rates from FRED</div>', unsafe_allow_html=True)
    
    with st.spinner("Fetching yield curve from FRED..."):
        try:
            yc = fetch_yield_curve()
            if yc:
                tenors = list(yc.keys())
                current_yields = [yc[t]["current"] for t in tenors]
                week_ago = [yc[t]["1w_ago"] for t in tenors]
                month_ago = [yc[t]["1m_ago"] for t in tenors]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=tenors, y=current_yields, mode="lines+markers",
                                        line=dict(color=ACCENT_CYAN, width=3), marker=dict(size=6),
                                        name="Current"))
                fig.add_trace(go.Scatter(x=tenors, y=week_ago, mode="lines",
                                        line=dict(color=ACCENT_PURPLE, width=1.5, dash="dash"),
                                        name="1 Week Ago"))
                fig.add_trace(go.Scatter(x=tenors, y=month_ago, mode="lines",
                                        line=dict(color=ACCENT_ORANGE, width=1.5, dash="dot"),
                                        name="1 Month Ago"))
                fig.update_layout(**PLOTLY_LAYOUT, title="UST Yield Curve — Current vs Prior")
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.info("⚠ Set your FRED API key to see the live yield curve. Get a free key at fred.stlouisfed.org")
    
    # 2s10s Spread & Real Yields
    c1, c2 = st.columns(2)
    with c1:
        try:
            spread_2s10s = fetch_fred_series("T10Y2Y")
            if len(spread_2s10s) > 0:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=spread_2s10s.index, y=spread_2s10s.values,
                    fill="tozeroy", line=dict(color=ACCENT_CYAN, width=2),
                    fillcolor="rgba(0,229,255,0.1)", name="2s10s"
                ))
                fig.add_hline(y=0, line_dash="dash", line_color="#64748b")
                fig.update_layout(**PLOTLY_LAYOUT, title="2s10s Spread (%)", height=340)
                st.plotly_chart(fig, use_container_width=True)
        except:
            st.info("Set FRED API key for 2s10s spread data")
    
    with c2:
        try:
            real_yield = fetch_fred_series("DFII10")   # 10Y TIPS
            breakeven = fetch_fred_series("T10YIE")    # 10Y breakeven
            if len(real_yield) > 0 and len(breakeven) > 0:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=real_yield.index, y=real_yield.values,
                                        line=dict(color=ACCENT_GREEN, width=2), name="10Y Real Yield"))
                fig.add_trace(go.Scatter(x=breakeven.index, y=breakeven.values,
                                        line=dict(color=ACCENT_ORANGE, width=2), name="10Y Breakeven"))
                fig.update_layout(**PLOTLY_LAYOUT, title="Real Yields & Breakevens (%)", height=340)
                st.plotly_chart(fig, use_container_width=True)
        except:
            st.info("Set FRED API key for real yields data")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: CREDIT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_credit:
    st.markdown('<div class="section-header">Credit Markets</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Investment grade & high yield spreads from FRED (ICE BofA)</div>', unsafe_allow_html=True)
    
    try:
        ig_oas = fetch_fred_series("BAMLC0A0CM")    # ICE BofA IG OAS
        hy_oas = fetch_fred_series("BAMLH0A0HYM2")  # ICE BofA HY OAS
        
        if len(ig_oas) > 0 and len(hy_oas) > 0:
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("IG OAS", f"{ig_oas.iloc[-1]:.0f} bp",
                          f"{ig_oas.iloc[-1] - ig_oas.iloc[-6]:.0f} bp (1W)")
            with m2:
                st.metric("HY OAS", f"{hy_oas.iloc[-1]:.0f} bp",
                          f"{hy_oas.iloc[-1] - hy_oas.iloc[-6]:.0f} bp (1W)")
            with m3:
                ratio = ig_oas.iloc[-1] / hy_oas.iloc[-1]
                st.metric("IG/HY Ratio", f"{ratio:.2f}")
            
            st.markdown("")
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(x=ig_oas.index, y=ig_oas.values,
                                    line=dict(color=ACCENT_CYAN, width=2), name="IG OAS (L)"), secondary_y=False)
            fig.add_trace(go.Scatter(x=hy_oas.index, y=hy_oas.values,
                                    line=dict(color=ACCENT_ORANGE, width=2), name="HY OAS (R)"), secondary_y=True)
            fig.update_layout(**PLOTLY_LAYOUT, title="Credit Spreads — IG vs HY OAS (bp)")
            fig.update_yaxes(gridcolor=GRID_COLOR, secondary_y=True)
            st.plotly_chart(fig, use_container_width=True)
    except:
        st.info("⚠ Set your FRED API key to see live credit spread data")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: MARKET DIRECTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_markets:
    st.markdown('<div class="section-header">Global Market Direction</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Bull/Bear signals based on price vs 20/50-day SMA, 1M & 3M momentum</div>', unsafe_allow_html=True)
    st.markdown("")
    
    with st.spinner("Fetching global indices..."):
        market_data = fetch_market_indices()
    
    if market_data:
        # Group by region
        us_indices = {k: v for k, v in market_data.items() if k in ["S&P 500", "NASDAQ", "Russell 2000"]}
        eu_indices = {k: v for k, v in market_data.items() if k in ["STOXX 600", "DAX", "FTSE 100", "CAC 40"]}
        asia_indices = {k: v for k, v in market_data.items() if k in ["Nikkei 225", "Hang Seng", "Shanghai Comp", "KOSPI", "ASX 200"]}
        
        def render_region(region_name, indices, emoji):
            st.markdown(f"### {emoji} {region_name}")
            
            if not indices:
                st.info(f"No data available for {region_name}")
                return
            
            # Regional aggregate signal
            signals = [v["signal"] for v in indices.values()]
            bull_count = sum(1 for s in signals if "BULL" in s)
            bear_count = sum(1 for s in signals if "BEAR" in s)
            
            if bull_count > len(signals) / 2:
                agg = "🟢 BULLISH"
                css_class = "signal-bull"
            elif bear_count > len(signals) / 2:
                agg = "🔴 BEARISH"
                css_class = "signal-bear"
            else:
                agg = "🟡 MIXED"
                css_class = "signal-neutral"
            
            st.markdown(f'<span class="{css_class}">Region Signal: {agg}</span>', unsafe_allow_html=True)
            st.markdown("")
            
            # Table
            rows = []
            for name, info in indices.items():
                rows.append({
                    "Index": name,
                    "Price": f"{info['price']:,.1f}",
                    "1W %": f"{info['1w']:+.2f}%",
                    "1M %": f"{info['1m']:+.2f}%",
                    "3M %": f"{info['3m']:+.2f}%",
                    "vs SMA50": f"{info['vs_sma50']:+.1f}%",
                    "Signal": info["signal"],
                })
            
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.markdown("")
        
        render_region("United States", us_indices, "🇺🇸")
        render_region("Europe", eu_indices, "🇪🇺")
        render_region("Asia Pacific", asia_indices, "🌏")
        
        # Methodology note
        st.markdown("""
        <div class="data-source-box">
            <strong>Signal Methodology:</strong> Composite score based on: (1) Price above/below 20-day SMA, 
            (2) Price above/below 50-day SMA, (3) Positive/negative 1-month return, 
            (4) Positive/negative 3-month return. Score ≥3 → Bull, Score ≤1 → Bear, else Neutral.
            <br><br>⚠ <em>These are quantitative signals only and do not constitute investment advice.</em>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("Could not fetch market data. Check your internet connection.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: FX & RECOMMENDATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_fx:
    st.markdown('<div class="section-header">Foreign Exchange</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Major pairs, trends & algorithmic trade signals</div>', unsafe_allow_html=True)
    st.markdown("")
    
    with st.spinner("Fetching FX data..."):
        fx_data = fetch_fx_data()
    
    if fx_data:
        # DXY chart
        dxy_data = fetch_yfinance_data("DX-Y.NYB", period="6mo")
        if len(dxy_data) > 0:
            fig = make_area_chart(dxy_data, "Close", "DXY — Dollar Index", ACCENT_YELLOW, height=320)
            st.plotly_chart(fig, use_container_width=True)
        
        # FX Table
        st.markdown("### 📊 FX Pair Monitor")
        fx_rows = []
        for pair, info in fx_data.items():
            fx_rows.append({
                "Pair": pair,
                "Price": f"{info['price']:.4f}" if info['price'] < 10 else f"{info['price']:.2f}",
                "1W %": f"{info['1w']:+.2f}%",
                "1M %": f"{info['1m']:+.2f}%",
                "3M %": f"{info['3m']:+.2f}%",
                "20D Vol": f"{info['vol']:.1f}%",
                "Trend": info["trend"],
            })
        
        fx_df = pd.DataFrame(fx_rows)
        st.dataframe(fx_df, use_container_width=True, hide_index=True)
        
        # FX Charts
        st.markdown("### 📈 Major Pairs")
        majors = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"]
        major_colors = [ACCENT_CYAN, ACCENT_GREEN, ACCENT_PURPLE, ACCENT_ORANGE]
        
        mc1, mc2 = st.columns(2)
        for i, pair in enumerate(majors):
            if pair in fx_data:
                col = mc1 if i % 2 == 0 else mc2
                with col:
                    data = fx_data[pair]["data"]
                    fig = make_area_chart(data, "Close", pair, major_colors[i], height=280)
                    st.plotly_chart(fig, use_container_width=True)
        
        # Recommendations
        st.markdown("---")
        st.markdown('<div class="section-header">FX Trade Signals</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Algorithmic signals based on trend, momentum & mean-reversion</div>', unsafe_allow_html=True)
        
        st.warning("⚠ **DISCLAIMER:** These are quantitative signals generated by simple algorithms (SMA crossovers, momentum scoring). They are NOT financial advice. Always do your own research and consult a qualified advisor before trading.")
        st.markdown("")
        
        recs = generate_fx_recommendations(fx_data)
        
        if recs:
            for rec in recs[:5]:  # Top 5 signals
                direction_class = "rec-long" if rec["direction"] == "LONG" else "rec-short"
                direction_color = "#22c55e" if rec["direction"] == "LONG" else "#ef4444"
                direction_emoji = "🟢" if rec["direction"] == "LONG" else "🔴"
                
                reasons_html = "<br>".join([f"• {r}" for r in rec["reasons"]])
                
                st.markdown(f"""
                <div class="rec-card {direction_class}">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <span style="font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;color:#e2e8f0;">
                            {direction_emoji} {rec['pair']}</span>
                        <span style="font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:{direction_color};">
                            {rec['direction']}</span>
                    </div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#94a3b8;margin-bottom:6px;">
                        Confidence: {rec['confidence']} · Spot: {rec['current']:.4f} · 20D Vol: {rec['vol']:.1f}%
                    </div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#64748b;line-height:1.8;">
                        {reasons_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No strong signals currently. All pairs are near-neutral.")
    else:
        st.warning("Could not fetch FX data. Check your internet connection.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: VOLATILITY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_vol:
    st.markdown('<div class="section-header">Volatility Monitor</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Equity & rates volatility gauges</div>', unsafe_allow_html=True)
    
    vix_data = fetch_yfinance_data("^VIX", period="1y")
    # MOVE index - try Yahoo Finance ticker
    move_data = fetch_yfinance_data("^MOVE", period="1y")
    
    vm1, vm2, vm3 = st.columns(3)
    with vm1:
        if len(vix_data) > 0:
            v = float(vix_data["Close"].iloc[-1])
            st.metric("VIX", f"{v:.2f}", f"{float(vix_data['Close'].iloc[-1] - vix_data['Close'].iloc[-2]):+.2f}")
    with vm2:
        if len(move_data) > 0:
            m = float(move_data["Close"].iloc[-1])
            st.metric("MOVE", f"{m:.1f}", f"{float(move_data['Close'].iloc[-1] - move_data['Close'].iloc[-2]):+.1f}")
    with vm3:
        if len(vix_data) > 0 and len(move_data) > 0:
            ratio = float(vix_data["Close"].iloc[-1]) / float(move_data["Close"].iloc[-1])
            st.metric("VIX/MOVE Ratio", f"{ratio:.3f}")
    
    st.markdown("")
    
    v1, v2 = st.columns(2)
    with v1:
        if len(vix_data) > 0:
            fig = make_area_chart(vix_data, "Close", "VIX — Equity Volatility", ACCENT_RED, height=350)
            fig.add_hline(y=20, line_dash="dash", line_color=ACCENT_ORANGE,
                         annotation_text="Elevated (20)", annotation_font_color=ACCENT_ORANGE)
            fig.add_hline(y=30, line_dash="dash", line_color=ACCENT_RED,
                         annotation_text="High (30)", annotation_font_color=ACCENT_RED)
            st.plotly_chart(fig, use_container_width=True)
    with v2:
        if len(move_data) > 0:
            fig = make_area_chart(move_data, "Close", "MOVE — Rates Volatility", ACCENT_PURPLE, height=350)
            fig.add_hline(y=120, line_dash="dash", line_color=ACCENT_ORANGE,
                         annotation_text="Elevated (120)", annotation_font_color=ACCENT_ORANGE)
            st.plotly_chart(fig, use_container_width=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FOOTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.markdown("---")
st.markdown("""
<div class="data-source-box">
    <strong style="color:#e2e8f0;">📡 Data Sources (All Free)</strong><br><br>
    <span style="color:#00e5ff;">FRED API</span> — Treasury yields, credit spreads (ICE BofA IG/HY OAS), 
    breakevens, real rates, 2s10s spread<br>
    <span style="color:#69f0ae;">Yahoo Finance</span> — DXY, FX pairs, VIX, MOVE, global indices, 
    commodities, S&P 500<br>
    <span style="color:#ffd740;">CME FedWatch</span> — Fed Funds futures (manual reference)<br><br>
    <em>Dashboard auto-refreshes data every 15 minutes. For real-time quotes, 
    reduce the cache TTL in the code.</em><br><br>
    ⚠ <strong>This dashboard is for informational purposes only and does not constitute 
    investment advice. All trading signals are algorithmic and should not be relied upon 
    for investment decisions.</strong>
</div>
""", unsafe_allow_html=True)
