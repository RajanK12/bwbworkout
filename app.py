import os
import io
import re
import json
import math
import uuid
import time
import hashlib
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import pandas as pd
import streamlit as st

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    PDF_EXPORT_AVAILABLE = True
except ModuleNotFoundError:
    PDF_EXPORT_AVAILABLE = False


# =========================================================
# CONFIG
# =========================================================

APP_TITLE = "Boxing With Bakr | Coach Platform"
DB_PATH = os.getenv("BWB_DB_PATH", "bwb_day_to_day.db")
UPLOAD_DIR = os.getenv("BWB_UPLOAD_DIR", "uploads")
DEFAULT_ADMIN_USERNAME = os.getenv("BWB_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("BWB_ADMIN_PASSWORD", "admin123")

os.makedirs(UPLOAD_DIR, exist_ok=True)

st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# THEME / STYLING
# =========================================================

def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bwb-bg: #0d0f10;
            --bwb-panel: #171a1c;
            --bwb-panel-2: #202427;
            --bwb-text: #f4f7f8;
            --bwb-muted: #a9b3b8;
            --bwb-teal: #16c2c8;
            --bwb-teal-dark: #0e8f95;
            --bwb-border: #2a3236;
            --bwb-danger: #ff6b6b;
        }

        .stApp {
            background-color: var(--bwb-bg);
            color: var(--bwb-text);
        }

        h1, h2, h3, h4, h5, h6, p, div, label, span {
            color: var(--bwb-text);
        }

        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }

        .bwb-card {
            background: var(--bwb-panel);
            border: 1px solid var(--bwb-border);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 14px;
        }

        .bwb-subtle {
            color: var(--bwb-muted);
            font-size: 0.95rem;
        }

        .bwb-kpi {
            background: linear-gradient(180deg, #181c1e
