"""
ReLoop 360 Visual System & Enterprise SaaS Theme.
Applies the professional navy-blue, white, and teal color palette.
"""
import streamlit as st


def inject_theme() -> None:
    """Apply a modern enterprise SaaS theme with navy-blue, white, and teal accents."""
    st.markdown(
        """<style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
        
        :root {
            --navy: #0F172A;
            --navy-surface: #1E293B;
            --ink: #0F172A;
            --muted: #64748B;
            --line: #E2E8F0;
            --blue: #2563EB;
            --teal: #0D9488;
            --teal-light: #F0FDFA;
            --teal-border: #99F6E4;
            --teal-accent: #0EA5E9;
            --surface: #FFFFFF;
            --canvas: #F8FAFC;
        }

        html, body, [class*="css"] {
            font-family: 'DM Sans', sans-serif;
            color: var(--ink);
        }

        .stApp {
            background: var(--canvas);
        }

        #MainMenu, footer {
            visibility: hidden;
        }

        [data-testid="stHeader"] {
            background: rgba(248, 250, 252, 0.92);
        }

        .block-container {
            max-width: 1480px;
            padding-top: 1.8rem;
            padding-bottom: 3.5rem;
        }

        h1, h2, h3, h4 {
            font-family: 'Manrope', 'DM Sans', sans-serif;
            color: var(--navy);
            letter-spacing: -0.035em;
        }

        h1 {
            font-size: 2.1rem !important;
            font-weight: 800 !important;
            margin-bottom: 0.2rem !important;
        }

        h2 {
            font-size: 1.35rem !important;
            font-weight: 700 !important;
            margin-top: 1.3rem !important;
        }

        h3 {
            font-size: 1.08rem !important;
            font-weight: 700 !important;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background: #FFFFFF;
            border-right: 1px solid var(--line);
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1.5rem;
        }

        [data-testid="stSidebar"] h1 {
            font-size: 1.3rem !important;
            letter-spacing: -0.02em;
            color: var(--navy);
        }

        /* Metric Cards */
        [data-testid="stMetric"] {
            background: var(--surface);
            border: 1px solid var(--line);
            border-top: 3px solid var(--teal);
            border-radius: 12px;
            padding: 0.95rem 1.1rem;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }

        [data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
        }

        [data-testid="stMetricLabel"] p {
            color: var(--muted);
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.055em;
        }

        [data-testid="stMetricValue"] {
            color: var(--navy);
            font-family: 'Manrope', sans-serif;
            font-size: 1.65rem;
            font-weight: 800;
        }

        /* Buttons & Badges */
        .stButton > button {
            border-radius: 9px;
            font-weight: 600;
            border: 1px solid #CBD5E1;
            transition: all 0.15s ease;
        }

        .stButton > button[kind="primary"] {
            background: var(--teal);
            border-color: var(--teal);
            color: #FFFFFF;
        }

        .stButton > button:hover {
            border-color: var(--teal);
            color: var(--teal);
        }

        /* DataFrames & Tables */
        [data-testid="stDataFrame"] {
            border: 1px solid var(--line);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 1px 4px rgba(15, 23, 42, 0.03);
        }

        [data-testid="stExpander"] {
            background: #FFFFFF;
            border: 1px solid var(--line);
            border-radius: 12px;
        }

        hr {
            border-color: var(--line);
        }
        </style>""",
        unsafe_allow_html=True,
    )
