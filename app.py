import os
import io
import re
import json
import math
import uuid
import time
import hashlib
import sqlite3
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

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
    """Apply BWB dark theme styling for Streamlit."""
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
            background: linear-gradient(180deg, #181c1e 0%, #111416 100%);
            border: 1px solid var(--bwb-border);
            border-radius: 18px;
            padding: 16px;
        }

        .stButton > button,
        div[data-testid="stDownloadButton"] > button {
            background: var(--bwb-teal);
            color: black;
            border: none;
            border-radius: 10px;
            font-weight: 700;
        }

        .stButton > button:hover,
        div[data-testid="stDownloadButton"] > button:hover {
            background: var(--bwb-teal-dark);
            color: white;
        }

        [data-testid="stSidebar"] {
            background: #101315;
            border-right: 1px solid var(--bwb-border);
        }

        .bwb-pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background: #0f3d40;
            border: 1px solid #136c71;
            color: #c9ffff;
            font-size: 0.82rem;
            margin-right: 6px;
            margin-bottom: 6px;
        }

        .bwb-divider {
            border-top: 1px solid var(--bwb-border);
            margin: 12px 0;
        }

        @media (max-width: 768px) {
            .block-container {
                padding-left: 0.8rem;
                padding-right: 0.8rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


apply_theme()


# =========================================================
# DATABASE CONNECTION
# =========================================================

@st.cache_resource
def get_conn() -> sqlite3.Connection:
    """
    Create and cache a SQLite connection for the Streamlit app.

    Using check_same_thread=False is necessary for Streamlit reruns.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


CONN = get_conn()


# =========================================================
# DATABASE HELPERS
# =========================================================

def run(query: str, params: Tuple[Any, ...] = ()) -> None:
    """Execute a write query and commit immediately."""
    cur = CONN.cursor()
    cur.execute(query, params)
    CONN.commit()


def fetch_all(query: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
    """Return all rows for a query."""
    cur = CONN.cursor()
    cur.execute(query, params)
    return cur.fetchall()


def fetch_one(query: str, params: Tuple[Any, ...] = ()) -> Optional[sqlite3.Row]:
    """Return a single row for a query."""
    cur = CONN.cursor()
    cur.execute(query, params)
    return cur.fetchone()


def now_iso() -> str:
    """Return a timestamp string for persistence."""
    return datetime.now().isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    """Hash text for simple password storage."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(text: Optional[str], fallback: Any) -> Any:
    """Safely parse JSON text."""
    try:
        return json.loads(text) if text else fallback
    except Exception:
        return fallback


def dump_json(value: Any) -> str:
    """Safely dump JSON text."""
    return json.dumps(value, ensure_ascii=False, indent=2)


# =========================================================
# SCHEMA CREATION
# =========================================================

def init_db() -> None:
    """Initialize all SQLite tables required by the BWB app."""

    run(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            display_name TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS drills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            level TEXT NOT NULL,
            equipment_json TEXT NOT NULL,
            stance_relevance TEXT,
            coaching_notes TEXT,
            constraints_json TEXT NOT NULL,
            explanation TEXT,
            athlete_description TEXT,
            tags TEXT,
            rounds_default INTEGER DEFAULT 0,
            round_length_sec INTEGER DEFAULT 0,
            rest_sec INTEGER DEFAULT 0,
            intensity TEXT,
            tactical_focus TEXT,
            image_path TEXT,
            is_archived INTEGER NOT NULL DEFAULT 0,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            class_type TEXT NOT NULL,
            level TEXT NOT NULL,
            training_goal TEXT NOT NULL,
            intensity TEXT NOT NULL,
            coach TEXT,
            tags TEXT,
            status TEXT NOT NULL,
            is_favorite INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            parent_workout_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            template_type TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            payload_json TEXT NOT NULL,
            is_archived INTEGER NOT NULL DEFAULT 0,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            weeks INTEGER NOT NULL,
            level TEXT NOT NULL,
            goal_priority TEXT NOT NULL,
            tags TEXT,
            is_archived INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS whiteboards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            file_path TEXT NOT NULL,
            notes TEXT,
            tags TEXT,
            linked_workout_id INTEGER,
            linked_program_id INTEGER,
            coach TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            actor TEXT,
            created_at TEXT NOT NULL
        )
        """
    )


# =========================================================
# SEEDING
# =========================================================

def seed_users() -> None:
    """Seed default staff accounts if they do not exist."""
    existing_admin = fetch_one(
        "SELECT id FROM users WHERE username = ?",
        (DEFAULT_ADMIN_USERNAME,),
    )
    if existing_admin is None:
        run(
            """
            INSERT INTO users (
                username, password_hash, role, display_name, is_active, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                DEFAULT_ADMIN_USERNAME,
                sha256_text(DEFAULT_ADMIN_PASSWORD),
                "admin",
                "BWB Admin",
                1,
                now_iso(),
            ),
        )

    existing_coach = fetch_one(
        "SELECT id FROM users WHERE username = ?",
        ("coach",),
    )
    if existing_coach is None:
        run(
            """
            INSERT INTO users (
                username, password_hash, role, display_name, is_active, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "coach",
                sha256_text("coach123"),
                "coach",
                "Head Coach",
                1,
                now_iso(),
            ),
        )


def seed_drills() -> None:
    """
    Seed a minimal starter drill bank only if the drill table is empty.
    This keeps first launch usable without creating duplicate seed data.
    """
    existing = fetch_one("SELECT COUNT(*) AS c FROM drills")
    if existing and existing["c"] > 0:
        return

    starter_drills = [
        {
            "name": "Jump Rope Rhythm Build",
            "category": "warmup",
            "subcategory": "rope",
            "level": "all",
            "equipment_json": dump_json(["jump rope"]),
            "stance_relevance": "both",
            "coaching_notes": "Light bounce, elbows in, shoulders relaxed.",
            "constraints_json": dump_json({
                "low_impact_ok": False,
                "needs_partner": False,
                "needs_bag": False
            }),
            "explanation": "Builds rhythm, foot timing, calf elasticity, and temperature for later boxing work.",
            "athlete_description": "Smooth rope rhythm with relaxed shoulders and clean breathing.",
            "tags": "warmup,rope,footwork,conditioning",
            "rounds_default": 3,
            "round_length_sec": 120,
            "rest_sec": 30,
            "intensity": "technical",
            "tactical_focus": "rhythm",
        },
        {
            "name": "Shadowbox Slip-Pivot Flow",
            "category": "warmup",
            "subcategory": "shadowboxing",
            "level": "all",
            "equipment_json": dump_json(["bodyweight"]),
            "stance_relevance": "both",
            "coaching_notes": "Punches long, defend with eyes up, finish each exchange with feet set.",
            "constraints_json": dump_json({
                "low_impact_ok": True,
                "needs_partner": False,
                "needs_bag": False
            }),
            "explanation": "Preps hands, shoulders, defense, and foot placement before partner drilling.",
            "athlete_description": "Shadowbox with controlled defense and pivots after each combo.",
            "tags": "warmup,shadowboxing,defense,footwork",
            "rounds_default": 3,
            "round_length_sec": 180,
            "rest_sec": 30,
            "intensity": "technical",
            "tactical_focus": "defense",
        },
    ]

    for d in starter_drills:
        run(
            """
            INSERT INTO drills (
                name, category, subcategory, level, equipment_json, stance_relevance,
                coaching_notes, constraints_json, explanation, athlete_description,
                tags, rounds_default, round_length_sec, rest_sec, intensity,
                tactical_focus, image_path, is_archived, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                d["name"],
                d["category"],
                d["subcategory"],
                d["level"],
                d["equipment_json"],
                d["stance_relevance"],
                d["coaching_notes"],
                d["constraints_json"],
                d["explanation"],
                d["athlete_description"],
                d["tags"],
                d["rounds_default"],
                d["round_length_sec"],
                d["rest_sec"],
                d["intensity"],
                d["tactical_focus"],
                None,
                "system",
                now_iso(),
                now_iso(),
            ),
        )


def log_audit(
    entity_type: str,
    entity_id: int,
    action: str,
    payload: Dict[str, Any],
    actor: str
) -> None:
    """Insert an audit log entry."""
    run(
        """
        INSERT INTO audit_log (
            entity_type, entity_id, action, payload_json, actor, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (entity_type, entity_id, action, dump_json(payload), actor, now_iso()),
    )


# =========================================================
# BOOTSTRAP
# =========================================================

init_db()
seed_users()
seed_drills()


# =========================================================
# SAFE PLACEHOLDER
# =========================================================

st.title(APP_TITLE)
st.caption("Phase 1 foundation loaded successfully.")

st.info(
    "This file currently includes:\n"
    "- imports\n"
    "- config\n"
    "- theme\n"
    "- SQLite connection\n"
    "- DB helpers\n"
    "- schema creation\n"
    "- seed users/drills\n\n"
    "Next phase should add auth + navigation or generator logic."
)
