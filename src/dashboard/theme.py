"""Visual system for the Reverse Logistics Control Tower."""
import streamlit as st


def inject_theme() -> None:
    """Apply a consistent, responsive enterprise dashboard theme."""
    st.markdown(
        """<style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
        :root { --ink:#172B4D; --muted:#66758B; --line:#E5EAF2; --blue:#2855D9; --blue-soft:#EEF3FF; --surface:#FFFFFF; --canvas:#F5F7FB; }
        html, body, [class*="css"] { font-family:'DM Sans',sans-serif; color:var(--ink); }
        .stApp { background:var(--canvas); }
        #MainMenu, footer { visibility:hidden; }
        [data-testid="stHeader"] { background:rgba(245,247,251,.88); }
        .block-container { max-width:1480px; padding-top:2rem; padding-bottom:3rem; }
        h1,h2,h3 { font-family:'Manrope','DM Sans',sans-serif; color:var(--ink); letter-spacing:-.035em; }
        h1 { font-size:2rem !important; font-weight:800 !important; margin-bottom:.25rem !important; }
        h2 { font-size:1.28rem !important; font-weight:700 !important; margin-top:1.35rem !important; }
        h3 { font-size:1.02rem !important; font-weight:700 !important; }
        [data-testid="stCaptionContainer"] { color:var(--muted); }
        [data-testid="stSidebar"] { background:#FFFFFF; border-right:1px solid var(--line); }
        [data-testid="stSidebar"] > div:first-child { padding-top:1.5rem; }
        [data-testid="stSidebar"] h1 { font-size:1.15rem !important; letter-spacing:-.02em; }
        [data-testid="stSidebar"] [data-testid="stRadio"] label { font-weight:600; color:#43536B; }
        [data-testid="stMetric"] { background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:1rem 1.1rem; box-shadow:0 2px 8px rgba(22,43,77,.035); }
        [data-testid="stMetricLabel"] p { color:var(--muted); font-size:.76rem; font-weight:700; text-transform:uppercase; letter-spacing:.055em; }
        [data-testid="stMetricValue"] { color:var(--ink); font-family:'Manrope',sans-serif; font-size:1.65rem; font-weight:800; }
        [data-testid="stMetricDelta"] { font-size:.78rem; }
        [data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--line); border-radius:14px; }
        [data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:12px; overflow:hidden; }
        [data-testid="stPlotlyChart"] { background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:.45rem; }
        .stButton > button { border-radius:9px; font-weight:600; border:1px solid #D7DFEA; transition:all .15s ease; }
        .stButton > button[kind="primary"] { background:var(--blue); border-color:var(--blue); }
        .stButton > button:hover { border-color:var(--blue); color:var(--blue); }
        .stTextInput input, .stSelectbox div[data-baseweb="select"], .stMultiSelect div[data-baseweb="select"] { border-radius:9px; }
        [data-testid="stAlert"] { border-radius:11px; }
        [data-testid="stExpander"] { background:#FFFFFF; border:1px solid var(--line); border-radius:12px; }
        hr { border-color:var(--line); }
        @media (max-width: 800px) { .block-container { padding:1.1rem 1rem 2rem; } h1 {font-size:1.55rem !important;} [data-testid="stMetricValue"] {font-size:1.3rem;} }
        </style>""",
        unsafe_allow_html=True,
    )
