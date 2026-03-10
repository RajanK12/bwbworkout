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
# AUTH / PERMISSIONS
# =========================================================

ROLE_PERMISSIONS = {
    "admin": {
        "generate",
        "edit_content",
        "import",
        "delete",
        "manage_templates",
        "manage_users",
        "archive",
        "favorite",
        "whiteboard",
        "view_dashboard",
    },
    "coach": {
        "generate",
        "edit_content",
        "import",
        "manage_templates",
        "favorite",
        "whiteboard",
        "view_dashboard",
    },
    "assistant": {
        "generate",
        "favorite",
        "whiteboard",
        "view_dashboard",
    },
    "read_only": {
        "view_dashboard",
    },
}


def get_current_user() -> Optional[Dict[str, Any]]:
    """Return the currently logged-in user from Streamlit session state."""
    return st.session_state.get("user")


def is_logged_in() -> bool:
    """Check whether a user is currently logged in."""
    return get_current_user() is not None


def has_perm(permission: str) -> bool:
    """Check whether the current user has a specific permission."""
    current_user = get_current_user()
    if not current_user:
        return False
    return permission in ROLE_PERMISSIONS.get(current_user["role"], set())


def require_permission(permission: str) -> None:
    """Stop execution if the current user lacks a permission."""
    if not has_perm(permission):
        st.error("You do not have permission to access this section.")
        st.stop()


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    """Fetch a user row by username."""
    return fetch_one(
        "SELECT * FROM users WHERE username = ? AND is_active = 1",
        (username.strip(),),
    )


def verify_login(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Validate credentials and return a user dict if successful."""
    row = get_user_by_username(username)
    if not row:
        return None

    if row["password_hash"] != sha256_text(password):
        return None

    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
    }


def login_user(user_dict: Dict[str, Any]) -> None:
    """Persist authenticated user into Streamlit session state."""
    st.session_state["user"] = user_dict
    st.session_state.setdefault("nav", "Dashboard")


def logout() -> None:
    """Clear auth-related session state and rerun."""
    keys_to_clear = [
        "user",
        "nav",
        "current_workout",
        "current_program",
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def login_screen() -> None:
    """Render the login screen."""
    st.title("🥊 Boxing With Bakr")
    st.caption("Internal Coach Platform")

    st.markdown('<div class="bwb-card">', unsafe_allow_html=True)

    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    col1, col2 = st.columns([1, 2])

    with col1:
        if st.button("Login", use_container_width=True):
            authenticated = verify_login(username, password)
            if authenticated:
                login_user(authenticated)
                st.success("Login successful.")
                st.rerun()
            else:
                st.error("Invalid credentials.")

    with col2:
        st.info(
            "Default accounts:\n\n"
            f"- admin / {DEFAULT_ADMIN_PASSWORD}\n"
            "- coach / coach123"
        )

    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# UI / GENERAL HELPERS
# =========================================================

def clean_text(text: str) -> str:
    """Normalize whitespace in a string."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


def parse_tags(value: str) -> List[str]:
    """Split a comma-separated tag string into a clean list."""
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def to_int(value: Any, default: int = 0) -> int:
    """Convert value to int safely."""
    try:
        return int(value)
    except Exception:
        return default


def seconds_to_label(seconds: int) -> str:
    """Render seconds as a readable label."""
    if seconds <= 0:
        return "0s"
    if seconds % 60 == 0:
        return f"{seconds // 60} min"
    return f"{seconds}s"


def list_to_pills(items: List[str]) -> str:
    """Render a list of tags/equipment as styled pills."""
    return "".join(
        [f'<span class="bwb-pill">{clean_text(item)}</span>' for item in items if clean_text(item)]
    )


def safe_get_session_list(key: str) -> List[Any]:
    """Ensure a session-state key exists as a list."""
    if key not in st.session_state or not isinstance(st.session_state[key], list):
        st.session_state[key] = []
    return st.session_state[key]


def safe_get_session_dict(key: str) -> Dict[str, Any]:
    """Ensure a session-state key exists as a dict."""
    if key not in st.session_state or not isinstance(st.session_state[key], dict):
        st.session_state[key] = {}
    return st.session_state[key]


def metric_card(label: str, value: Any, help_text: str = "") -> None:
    """Render a styled KPI card."""
    st.markdown(
        f"""
        <div class="bwb-kpi">
            <div class="bwb-subtle">{label}</div>
            <div style="font-size: 1.8rem; font-weight: 800; margin-top: 4px;">{value}</div>
            <div class="bwb-subtle" style="margin-top: 6px;">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_user_badge() -> None:
    """Show the current user badge in the sidebar."""
    current_user = get_current_user()
    if not current_user:
        return

    st.sidebar.markdown(
        f"""
        <div class="bwb-card" style="padding: 12px;">
            <div style="font-weight: 700;">{current_user['display_name']}</div>
            <div class="bwb-subtle">@{current_user['username']} · {current_user['role']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_navigation_options() -> List[str]:
    """Return the sidebar navigation options."""
    return [
        "Dashboard",
        "Generate Class",
        "Generate Program",
        "Drill Library",
        "Saved Workouts",
        "Templates",
        "Whiteboard Archive",
        "Import Content",
        "Settings",
    ]


def render_sidebar_navigation() -> str:
    """
    Render the sidebar shell and return the selected nav item.
    Must only be called after login.
    """
    current_user = get_current_user()
    if not current_user:
        return "Login"

    with st.sidebar:
        st.title("BWB Coach Platform")
        render_user_badge()

        nav = st.radio(
            "Navigation",
            options=get_navigation_options(),
            key="nav",
        )

        st.markdown("---")

        if st.button("Log Out", use_container_width=True):
            logout()

    return nav


def render_top_shell() -> str:
    """
    Handle auth gate and render the sidebar shell.
    Returns the selected page name.
    """
    if not is_logged_in():
        login_screen()
        st.stop()

    return render_sidebar_navigation()

def render_placeholder_page(title: str, description: str) -> None:
    """Simple placeholder page renderer for pages not yet implemented."""
    st.title(title)
    st.markdown(
        f"""
        <div class="bwb-card">
            <div>{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
# =========================================================
# BOXING LOGIC ENGINE
# =========================================================

PUNCH_MAP = {
    "1": {"name": "jab", "hand": "lead", "type": "straight", "range": "long"},
    "2": {"name": "straight", "hand": "rear", "type": "straight", "range": "long"},
    "3": {"name": "lead hook", "hand": "lead", "type": "hook", "range": "mid"},
    "4": {"name": "rear hook", "hand": "rear", "type": "hook", "range": "mid"},
    "5": {"name": "lead uppercut", "hand": "lead", "type": "uppercut", "range": "close"},
    "6": {"name": "rear uppercut", "hand": "rear", "type": "uppercut", "range": "close"},
    "7": {"name": "lead body", "hand": "lead", "type": "body", "range": "mid"},
    "8": {"name": "rear body", "hand": "rear", "type": "body", "range": "mid"},
    "OVR": {"name": "overhand right", "hand": "rear", "type": "overhand", "range": "mid"},
    "OVL": {"name": "overhand left", "hand": "lead", "type": "overhand", "range": "mid"},
}

DEFENSE_ACTIONS = [
    "slip outside",
    "slip inside",
    "roll under",
    "pull back",
    "pivot out",
    "step back reset",
    "angle out",
    "level change",
    "shuffle out",
    "step in behind jab",
]

TACTICAL_THEMES = [
    "technique development",
    "conditioning",
    "endurance",
    "power",
    "movement quality",
    "body punching",
    "defense",
    "counterpunching",
    "angle work",
    "boxing-specific strength",
    "cardio capacity",
]


def combo_complexity_by_level(level: str) -> int:
    """
    Return target combo complexity by class level.
    """
    mapping = {
        "beginner": 3,
        "intermediate": 4,
        "advanced": 5,
        "fighter": 6,
        "teen": 3,
        "general fitness": 3,
        "all": 4,
    }
    return mapping.get(level.lower(), 4)


def choose_opening_by_theme(theme: str) -> List[str]:
    """
    Choose a sensible combo opener based on tactical focus.
    """
    theme = theme.lower()

    if "body" in theme:
        return random.choice([
            ["1", "7"],
            ["1", "2", "7"],
            ["2", "3", "7"],
        ])

    if "defense" in theme or "counter" in theme:
        return random.choice([
            ["1", "2"],
            ["1", "slip outside", "2"],
            ["pull back", "2", "3"],
        ])

    if "angle" in theme or "movement" in theme:
        return random.choice([
            ["1", "2", "pivot out"],
            ["1", "3", "angle out"],
            ["1", "2", "shuffle out"],
        ])

    if "power" in theme:
        return random.choice([
            ["1", "2", "3"],
            ["1", "OVR", "3"],
            ["2", "3", "2"],
        ])

    return random.choice([
        ["1", "2"],
        ["1", "1", "2"],
        ["1", "2", "3"],
    ])


def legal_followups(prev: str, theme: str) -> List[str]:
    """
    Return logically valid follow-up options after a prior token.
    Includes punches, exits, defense, and theme-biased choices.
    """
    if prev not in PUNCH_MAP:
        return ["1", "2", "3", "pivot out", "angle out", "step back reset"]

    prev_meta = PUNCH_MAP[prev]
    hand = prev_meta["hand"]
    range_zone = prev_meta["range"]

    options: List[str] = []

    # Hand alternation base
    for code, meta in PUNCH_MAP.items():
        if meta["hand"] != hand:
            options.append(code)

    # Logical continuations
    if prev in {"1", "2"}:
        options.extend(["3", "7", "pivot out", "step back reset"])

    if prev in {"3", "4"}:
        options.extend(["2", "6", "roll under", "angle out"])

    if prev in {"5", "6", "7", "8"}:
        options.extend(["3", "2", "roll under", "pivot out"])

    # Theme bias
    t = theme.lower()

    if "body" in t:
        options.extend(["7", "8", "5", "6"])

    if "defense" in t:
        options.extend(["slip outside", "roll under", "pull back", "pivot out"])

    if "angle" in t or "movement" in t:
        options.extend(["angle out", "pivot out", "shuffle out"])

    if "power" in t:
        options.extend(["OVR", "3", "2"])

    # Range-aware bias
    if range_zone == "long":
        options.extend(["1", "2", "3"])
    elif range_zone == "mid":
        options.extend(["3", "4", "7", "8", "2"])
    else:
        options.extend(["5", "6", "3", "roll under", "pivot out"])

    # Deduplicate while keeping order
    return list(dict.fromkeys(options))


def render_combo_for_coach(tokens: List[str]) -> str:
    """
    Return the coach-facing combo string using punch numbers / action terms.
    """
    return " - ".join(tokens)


def combo_to_plain_language(tokens: List[str]) -> str:
    """
    Convert combo tokens into athlete-friendly language.
    """
    readable = []
    for token in tokens:
        if token in PUNCH_MAP:
            readable.append(PUNCH_MAP[token]["name"])
        else:
            readable.append(token)
    return ", then ".join(readable)


def generate_boxing_combo(
    level: str,
    theme: str,
    intensity: str,
    beginner_safe: bool = False,
) -> Dict[str, str]:
    """
    Generate a technically coherent boxing combo with cues/explanation.
    """
    target_len = combo_complexity_by_level(level)

    if intensity.lower() in {"technical", "recovery-focused"}:
        target_len = max(2, target_len - 1)
    elif intensity.lower() in {"high intensity", "conditioning-focused"}:
        target_len = min(7, target_len + 1)

    if beginner_safe:
        target_len = min(target_len, 4)

    tokens = choose_opening_by_theme(theme)

    while len(tokens) < target_len:
        prev = tokens[-1]
        options = legal_followups(prev, theme)

        if beginner_safe:
            options = [o for o in options if o not in {"OVR", "OVL", "4"}]

        next_token = random.choice(options)
        tokens.append(next_token)

        if len(tokens) < target_len and random.random() < 0.25:
            defense = random.choice(["slip outside", "roll under", "pivot out", "angle out"])
            if defense not in tokens[-2:]:
                tokens.append(defense)

        if len(tokens) >= target_len:
            break

    if tokens[-1] in PUNCH_MAP and random.random() < 0.7:
        tokens.append(random.choice(["pivot out", "step back reset", "angle out"]))

    coach = render_combo_for_coach(tokens)
    plain = combo_to_plain_language(tokens)

    why = (
        f"This sequence supports {theme.lower()} by linking offense with "
        f"defensive transition and better positional exits."
    )

    cues = "Stay balanced, eyes up, finish each exchange with your feet under you."

    if "body" in theme.lower():
        cues = "Change levels without folding the chest. Touch body cleanly, then come back upstairs or exit."

    if "angle" in theme.lower():
        cues = "Do not stand in front after the last punch. Land and move."

    if "power" in theme.lower():
        cues = "Rotate through the floor and hips, but do not overswing."

    return {
        "combo": coach,
        "athlete_friendly": plain,
        "why": why,
        "cues": cues,
        "mistakes": (
            "Common mistakes: overreaching, squaring up, admiring the combo, "
            "and dropping the opposite hand."
        ),
    }


# =========================================================
# DRILL LIBRARY HELPERS
# =========================================================

def drill_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """
    Convert a SQLite row from drills into a Python dict with decoded JSON fields.
    """
    d = dict(row)
    d["equipment"] = load_json(d.get("equipment_json", "[]"), [])
    d["constraints"] = load_json(d.get("constraints_json", "{}"), {})
    return d


def get_drills(
    category: Optional[str] = None,
    level: Optional[str] = None,
    include_archived: bool = False,
    equipment_filter: Optional[List[str]] = None,
    tactical_focus: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Query all drills in memory and filter them.
    """
    rows = fetch_all("SELECT * FROM drills")
    drills = [drill_row_to_dict(r) for r in rows]

    filtered: List[Dict[str, Any]] = []

    for d in drills:
        if not include_archived and d["is_archived"]:
            continue

        if category and d["category"] != category:
            continue

        if level and d["level"] not in {level, "all"}:
            continue

        if tactical_focus and tactical_focus.lower() not in clean_text(d.get("tactical_focus", "")).lower():
            continue

        if equipment_filter:
            if not set(equipment_filter).issubset(set(d["equipment"])):
                continue

        filtered.append(d)

    return filtered


def choose_drill_from_library(
    category: str,
    level: str,
    equipment_available: List[str],
    focus: str,
    constraints: Dict[str, Any],
    fallback_name: str,
) -> Dict[str, Any]:
    """
    Pick a drill from the drill library that matches constraints.
    Returns a fallback drill if no drill matches.
    """
    candidates = get_drills(category=category, level=level)
    allowed: List[Dict[str, Any]] = []

    for d in candidates:
        c = d["constraints"]

        if constraints.get("no_partner_drills") and c.get("needs_partner"):
            continue

        if constraints.get("no_bags") and c.get("needs_bag"):
            continue

        if constraints.get("low_impact_only") and not c.get("low_impact_ok", False):
            continue

        if constraints.get("bodyweight_only_strength") and category in {"strength", "core"}:
            if set(d["equipment"]) - {"bodyweight"}:
                continue

        if equipment_available:
            if not set(d["equipment"]).issubset(set(equipment_available) | {"bodyweight"}):
                continue

        if focus and d.get("tactical_focus"):
            if focus.lower() in d["tactical_focus"].lower():
                allowed.append(d)
                continue

        allowed.append(d)

    if allowed:
        return random.choice(allowed)

    return {
        "name": fallback_name,
        "explanation": f"Fallback {category} drill because no library drill matched all constraints.",
        "athlete_description": fallback_name,
        "coaching_notes": "Coach to the standard and keep structure simple.",
        "rounds_default": 1,
        "round_length_sec": 180,
        "rest_sec": 30,
        "equipment": ["bodyweight"],
        "category": category,
    }


# =========================================================
# WORKOUT GENERATION HELPERS
# =========================================================

def make_round_item(
    title: str,
    details: str,
    coach_cues: str,
    explanation: str,
    athlete_desc: str,
    rounds: int = 0,
    round_length_sec: int = 0,
    rest_sec: int = 0,
) -> Dict[str, Any]:
    """
    Create a standardized workout item block.
    """
    return {
        "title": title,
        "details": details,
        "coach_cues": coach_cues,
        "explanation": explanation,
        "athlete_description": athlete_desc,
        "rounds": rounds,
        "round_length_sec": round_length_sec,
        "rest_sec": rest_sec,
    }


def build_constraints_dict(
    limited_space: bool,
    no_partner_drills: bool,
    no_bags: bool,
    low_impact_only: bool,
    bodyweight_only_strength: bool,
    beginner_safe_only: bool,
    mixed_level: bool,
) -> Dict[str, Any]:
    """
    Standardize class constraints into a single dict.
    """
    return {
        "limited_space": limited_space,
        "no_partner_drills": no_partner_drills,
        "no_bags": no_bags,
        "low_impact_only": low_impact_only,
        "bodyweight_only_strength": bodyweight_only_strength,
        "beginner_safe_only": beginner_safe_only,
        "mixed_level": mixed_level,
    }


def section_duration_map(
    format_name: str,
    total_duration: int,
    custom_split: Dict[str, int],
) -> Dict[str, int]:
    """
    Map class format names to section durations.
    """
    if format_name == "Standard 60 Boxing":
        return {
            "warmup": 15,
            "partner": 15,
            "bag": 15,
            "strength_or_core": 10,
            "cooldown": 5,
        }

    if format_name == "30 Boxing / 30 Strength":
        return {
            "warmup": 10,
            "partner": 10,
            "bag": 10,
            "strength_or_core": 25,
            "cooldown": 5,
        }

    if format_name == "30 Boxing / 30 Cardio":
        return {
            "warmup": 10,
            "partner": 10,
            "bag": 10,
            "cardio": 25,
            "cooldown": 5,
        }

    if format_name == "40 Boxing / 20 Strength":
        return {
            "warmup": 10,
            "partner": 15,
            "bag": 15,
            "strength_or_core": 15,
            "cooldown": 5,
        }

    if format_name == "45 Boxing / 15 Conditioning":
        return {
            "warmup": 12,
            "partner": 15,
            "bag": 18,
            "cardio": 10,
            "cooldown": 5,
        }

    if format_name == "20 / 20 / 20 Hybrid":
        return {
            "warmup": 8,
            "partner": 10,
            "bag": 10,
            "strength_or_core": 12,
            "cardio": 15,
            "cooldown": 5,
        }

    if format_name == "Custom":
        d = {
            "warmup": custom_split.get("warmup", 10),
            "partner": custom_split.get("partner", 10),
            "bag": custom_split.get("bag", 10),
            "strength_or_core": custom_split.get("strength_or_core", 10),
            "cardio": custom_split.get("cardio", 10),
            "cooldown": custom_split.get("cooldown", 5),
        }
        total = sum(d.values())
        if total != total_duration:
            diff = total_duration - total
            d["cooldown"] = max(3, d["cooldown"] + diff)
        return d

    return {
        "warmup": 12,
        "partner": 15,
        "bag": 15,
        "strength_or_core": 13,
        "cooldown": 5,
    }


# =========================================================
# SECTION BUILDERS
# =========================================================

def generate_warmup_section(
    level: str,
    theme: str,
    duration_min: int,
    equipment: List[str],
    constraints: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a warm-up section that primes the tactical goal.
    """
    warmup_drill = choose_drill_from_library(
        category="warmup",
        level=level,
        equipment_available=equipment,
        focus=theme,
        constraints=constraints,
        fallback_name="Jump Rope + Shadowboxing Prep",
    )

    combo = generate_boxing_combo(
        level=level,
        theme=theme,
        intensity="technical",
        beginner_safe=constraints.get("beginner_safe_only", False),
    )

    items = [
        make_round_item(
            title=warmup_drill["name"],
            details=warmup_drill["explanation"],
            coach_cues=warmup_drill.get("coaching_notes", ""),
            explanation=warmup_drill["explanation"],
            athlete_desc=warmup_drill.get("athlete_description", ""),
            rounds=warmup_drill.get("rounds_default", 0),
            round_length_sec=warmup_drill.get("round_length_sec", 0),
            rest_sec=warmup_drill.get("rest_sec", 0),
        ),
        make_round_item(
            title="Technical Shadowboxing Build",
            details=f"Work this flow: {combo['combo']}",
            coach_cues=combo["cues"],
            explanation="This primes the exact movements and tactical theme before partner or bag work begins.",
            athlete_desc=combo["athlete_friendly"],
            rounds=2,
            round_length_sec=180,
            rest_sec=30,
        ),
    ]

    notes = f"Warm-up should prepare for {theme.lower()} and raise temperature without blowing up the room early."

    return {
        "name": "Warm-Up",
        "duration_min": duration_min,
        "coach_notes": notes,
        "items": items,
    }


def generate_partner_section(
    level: str,
    theme: str,
    duration_min: int,
    equipment: List[str],
    constraints: Dict[str, Any],
    rounds: int,
    round_length_sec: int,
    rest_sec: int,
) -> Dict[str, Any]:
    """
    Build partner drill section or solo substitute if no partners allowed.
    """
    if constraints.get("no_partner_drills"):
        return {
            "name": "Technical Drills",
            "duration_min": duration_min,
            "coach_notes": "Partner work unavailable. Replaced with solo technical flows.",
            "items": [
                make_round_item(
                    title="Mirror Shadowboxing Reaction Rounds",
                    details="Athletes mirror the coach’s offense-defense calls without partners.",
                    coach_cues="Keep reactions clean and stay organized between calls.",
                    explanation="Substitutes partner timing and reading work when partner drills are not possible.",
                    athlete_desc="React to coach commands with clean offense and defense.",
                    rounds=rounds,
                    round_length_sec=round_length_sec,
                    rest_sec=rest_sec,
                )
            ],
        }

    library_drill = choose_drill_from_library(
        category="partner",
        level=level,
        equipment_available=equipment,
        focus=theme,
        constraints=constraints,
        fallback_name="Partner Timing Rounds",
    )

    combos = [
        generate_boxing_combo(
            level=level,
            theme=theme,
            intensity="moderate",
            beginner_safe=constraints.get("beginner_safe_only", False),
        )
        for _ in range(max(2, rounds))
    ]

    items: List[Dict[str, Any]] = []

    for i, combo in enumerate(combos, start=1):
        items.append(
            make_round_item(
                title=f"Partner Round {i}",
                details=f"Technical pattern: {combo['combo']}",
                coach_cues=combo["cues"],
                explanation=(
                    f"{combo['why']} Use partner rounds to teach the read, response, "
                    "and exit before the bag reinforces volume."
                ),
                athlete_desc=combo["athlete_friendly"],
                rounds=1,
                round_length_sec=round_length_sec,
                rest_sec=rest_sec,
            )
        )

    items.insert(
        0,
        make_round_item(
            title=library_drill["name"],
            details=library_drill["explanation"],
            coach_cues=library_drill.get("coaching_notes", ""),
            explanation=library_drill["explanation"],
            athlete_desc=library_drill.get("athlete_description", ""),
            rounds=library_drill.get("rounds_default", 0),
            round_length_sec=library_drill.get("round_length_sec", 0),
            rest_sec=library_drill.get("rest_sec", 0),
        ),
    )

    return {
        "name": "Partner Drills",
        "duration_min": duration_min,
        "coach_notes": "Teach the concept first, then add pace, defense, and decision-making.",
        "items": items,
    }


def generate_bag_section(
    level: str,
    theme: str,
    duration_min: int,
    equipment: List[str],
    constraints: Dict[str, Any],
    rounds: int,
    round_length_sec: int,
    rest_sec: int,
) -> Dict[str, Any]:
    """
    Build bag section or solo substitute if no bags available.
    """
    if constraints.get("no_bags"):
        return {
            "name": "Boxing Rounds",
            "duration_min": duration_min,
            "coach_notes": "Heavy bags unavailable. Replaced with shadowboxing / station boxing rounds.",
            "items": [
                make_round_item(
                    title="Shadowboxing Pressure Rounds",
                    details="Athletes perform the same technical focus with sharper pace and cleaner exits.",
                    coach_cues="Punch through full range, defend after offense, and own the reset.",
                    explanation="Maintains the reinforcement phase of class without bags.",
                    athlete_desc="High-quality boxing rounds in place of bag work.",
                    rounds=rounds,
                    round_length_sec=round_length_sec,
                    rest_sec=rest_sec,
                )
            ],
        }

    bag_drill = choose_drill_from_library(
        category="bag",
        level=level,
        equipment_available=equipment,
        focus=theme,
        constraints=constraints,
        fallback_name="Heavy Bag Reinforcement Rounds",
    )

    items = [
        make_round_item(
            title=bag_drill["name"],
            details=bag_drill["explanation"],
            coach_cues=bag_drill.get("coaching_notes", ""),
            explanation=bag_drill["explanation"],
            athlete_desc=bag_drill.get("athlete_description", ""),
            rounds=bag_drill.get("rounds_default", 0),
            round_length_sec=bag_drill.get("round_length_sec", 0),
            rest_sec=bag_drill.get("rest_sec", 0),
        )
    ]

    for i in range(1, rounds + 1):
        combo = generate_boxing_combo(
            level=level,
            theme=theme,
            intensity="conditioning-focused" if i >= rounds - 1 else "moderate",
            beginner_safe=constraints.get("beginner_safe_only", False),
        )

        pacing = "Build clean volume." if i < rounds else "Last round: maintain form under fatigue."

        items.append(
            make_round_item(
                title=f"Bag Round {i}",
                details=f"Work {combo['combo']} with bag emphasis on {theme.lower()}. {pacing}",
                coach_cues=combo["cues"],
                explanation="Bag work reinforces mechanics with more output and less hesitation than partner rounds.",
                athlete_desc=combo["athlete_friendly"],
                rounds=1,
                round_length_sec=round_length_sec,
                rest_sec=rest_sec,
            )
        )

    return {
        "name": "Heavy Bag",
        "duration_min": duration_min,
        "coach_notes": "Reinforce the earlier lesson. Volume is allowed, but not sloppy reps.",
        "items": items,
    }


def generate_strength_section(
    level: str,
    theme: str,
    duration_min: int,
    equipment: List[str],
    constraints: Dict[str, Any],
    intensity: str,
) -> Dict[str, Any]:
    """
    Build strength/core section matching boxing needs.
    """
    strength_candidates: List[Dict[str, Any]] = []

    for cat in ["strength", "core"]:
        strength_candidates.extend(
            get_drills(category=cat, level=level, equipment_filter=None, tactical_focus=None)
        )

    allowed: List[Dict[str, Any]] = []

    for d in strength_candidates:
        c = d["constraints"]

        if constraints.get("low_impact_only") and not c.get("low_impact_ok", False):
            continue

        if constraints.get("bodyweight_only_strength"):
            if set(d["equipment"]) - {"bodyweight"}:
                continue

        if equipment:
            if not set(d["equipment"]).issubset(set(equipment) | {"bodyweight"}):
                continue

        allowed.append(d)

    if not allowed:
        allowed = [
            {
                "name": "Pushup + Split Squat + Plank Circuit",
                "explanation": "Fallback boxing-specific strength circuit.",
                "athlete_description": "Bodyweight strength circuit for trunk and lower-body control.",
                "coaching_notes": "Clean reps, no rushing.",
                "rounds_default": 3,
                "round_length_sec": 45,
                "rest_sec": 20,
            }
        ]

    chosen = random.sample(allowed, k=min(3, len(allowed)))
    format_name = random.choice(["circuit", "EMOM", "timed rounds", "station rotation", "AMRAP"])

    items: List[Dict[str, Any]] = []

    for d in chosen:
        items.append(
            make_round_item(
                title=d["name"],
                details=f"{d.get('explanation', '')} Format: {format_name}.",
                coach_cues=d.get("coaching_notes", ""),
                explanation=d.get("explanation", ""),
                athlete_desc=d.get("athlete_description", ""),
                rounds=d.get("rounds_default", 3),
                round_length_sec=d.get("round_length_sec", 45),
                rest_sec=d.get("rest_sec", 20),
            )
        )

    notes = (
        "Strength should complement the boxing theme: rotation, anti-rotation, stance stability, "
        "hip drive, punching endurance, and trunk control."
    )

    return {
        "name": "Strength / Core",
        "duration_min": duration_min,
        "coach_notes": notes,
        "items": items,
    }


def generate_cardio_section(
    level: str,
    theme: str,
    duration_min: int,
    equipment: List[str],
    constraints: Dict[str, Any],
    intensity: str,
) -> Dict[str, Any]:
    """
    Build cardio / conditioning section.
    """
    cardio_drills = get_drills(category="cardio", level=level)
    allowed: List[Dict[str, Any]] = []

    for d in cardio_drills:
        c = d["constraints"]

        if constraints.get("low_impact_only") and not c.get("low_impact_ok", False):
            continue

        if equipment:
            if not set(d["equipment"]).issubset(set(equipment) | {"bodyweight"}):
                continue

        allowed.append(d)

    if not allowed:
        allowed = [
            {
                "name": "Marching Shadowboxing Intervals",
                "explanation": "Low-equipment fallback cardio choice.",
                "athlete_description": "Fast boxing intervals with active recovery.",
                "coaching_notes": "Keep output high while maintaining position.",
                "rounds_default": 5,
                "round_length_sec": 90,
                "rest_sec": 30,
            }
        ]

    chosen = random.sample(allowed, k=min(2, len(allowed)))

    items: List[Dict[str, Any]] = []

    for d in chosen:
        items.append(
            make_round_item(
                title=d["name"],
                details=d.get("explanation", ""),
                coach_cues=d.get("coaching_notes", ""),
                explanation=d.get("explanation", ""),
                athlete_desc=d.get("athlete_description", ""),
                rounds=d.get("rounds_default", 4),
                round_length_sec=d.get("round_length_sec", 90),
                rest_sec=d.get("rest_sec", 30),
            )
        )

    items.append(
        make_round_item(
            title="Finisher Intervals",
            details="30s on / 15s off for boxing footwork + straight-punch pace bursts.",
            coach_cues="Fast hands, feet under you, no flaring elbows.",
            explanation="Finishes the session with controlled fatigue exposure specific to boxing.",
            athlete_desc="Short hard bursts with quick recovery windows.",
            rounds=6,
            round_length_sec=30,
            rest_sec=15,
        )
    )

    return {
        "name": "Cardio / Conditioning",
        "duration_min": duration_min,
        "coach_notes": "Cardio should stay specific to the class goal when possible.",
        "items": items,
    }


def generate_cooldown_section(
    level: str,
    duration_min: int,
    equipment: List[str],
    constraints: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build cooldown / mobility section.
    """
    drill = choose_drill_from_library(
        category="cooldown",
        level=level,
        equipment_available=equipment,
        focus="recovery",
        constraints=constraints,
        fallback_name="Breathing + Mobility Reset",
    )

    return {
        "name": "Cooldown / Mobility",
        "duration_min": duration_min,
        "coach_notes": "Downshift the room. Finish with breathing and posture.",
        "items": [
            make_round_item(
                title=drill["name"],
                details=drill["explanation"],
                coach_cues=drill.get("coaching_notes", ""),
                explanation=drill["explanation"],
                athlete_desc=drill.get("athlete_description", ""),
                rounds=1,
                round_length_sec=max(180, duration_min * 60),
                rest_sec=0,
            )
        ],
    }


# =========================================================
# FULL WORKOUT GENERATION
# =========================================================

def generate_full_workout(
    name: str,
    class_type: str,
    level: str,
    training_goal: str,
    intensity: str,
    coach: str,
    total_duration: int,
    format_name: str,
    custom_split: Dict[str, int],
    equipment_available: List[str],
    constraints: Dict[str, Any],
    rounds: int,
    round_length_sec: int,
    rest_sec: int,
    tags: List[str],
) -> Dict[str, Any]:
    """
    Generate a full structured BWB workout.
    """
    durations = section_duration_map(format_name, total_duration, custom_split)
    sections: List[Dict[str, Any]] = []

    sections.append(
        generate_warmup_section(
            level,
            training_goal,
            durations.get("warmup", 10),
            equipment_available,
            constraints,
        )
    )

    sections.append(
        generate_partner_section(
            level,
            training_goal,
            durations.get("partner", 10),
            equipment_available,
            constraints,
            rounds,
            round_length_sec,
            rest_sec,
        )
    )

    sections.append(
        generate_bag_section(
            level,
            training_goal,
            durations.get("bag", 10),
            equipment_available,
            constraints,
            rounds,
            round_length_sec,
            rest_sec,
        )
    )

    if durations.get("strength_or_core", 0) > 0:
        sections.append(
            generate_strength_section(
                level,
                training_goal,
                durations.get("strength_or_core", 10),
                equipment_available,
                constraints,
                intensity,
            )
        )

    if durations.get("cardio", 0) > 0:
        sections.append(
            generate_cardio_section(
                level,
                training_goal,
                durations.get("cardio", 10),
                equipment_available,
                constraints,
                intensity,
            )
        )

    sections.append(
        generate_cooldown_section(
            level,
            durations.get("cooldown", 5),
            equipment_available,
            constraints,
        )
    )

    workout = {
        "name": clean_text(name) or f"{training_goal} {level.title()} Session",
        "class_type": class_type,
        "level": level,
        "training_goal": training_goal,
        "intensity": intensity,
        "coach": coach,
        "tags": tags,
        "format_name": format_name,
        "total_duration": total_duration,
        "equipment_available": equipment_available,
        "constraints": constraints,
        "rounds": rounds,
        "round_length_sec": round_length_sec,
        "rest_sec": rest_sec,
        "sections": sections,
        "created_at": now_iso(),
    }

    return workout


def regenerate_section(workout: Dict[str, Any], section_name: str) -> Dict[str, Any]:
    """
    Regenerate only one section of an existing workout.
    """
    workout = json.loads(json.dumps(workout))

    level = workout["level"]
    goal = workout["training_goal"]
    equipment = workout["equipment_available"]
    constraints = workout["constraints"]
    rounds = workout["rounds"]
    round_length_sec = workout["round_length_sec"]
    rest_sec = workout["rest_sec"]
    intensity = workout["intensity"]

    duration_lookup = {s["name"]: s["duration_min"] for s in workout["sections"]}

    new_section = None

    if section_name == "Warm-Up":
        new_section = generate_warmup_section(
            level, goal, duration_lookup.get("Warm-Up", 10), equipment, constraints
        )

    elif section_name == "Partner Drills":
        new_section = generate_partner_section(
            level,
            goal,
            duration_lookup.get("Partner Drills", 10),
            equipment,
            constraints,
            rounds,
            round_length_sec,
            rest_sec,
        )

    elif section_name == "Heavy Bag":
        new_section = generate_bag_section(
            level,
            goal,
            duration_lookup.get("Heavy Bag", 10),
            equipment,
            constraints,
            rounds,
            round_length_sec,
            rest_sec,
        )

    elif section_name == "Strength / Core":
        new_section = generate_strength_section(
            level,
            goal,
            duration_lookup.get("Strength / Core", 10),
            equipment,
            constraints,
            intensity,
        )

    elif section_name == "Cardio / Conditioning":
        new_section = generate_cardio_section(
            level,
            goal,
            duration_lookup.get("Cardio / Conditioning", 10),
            equipment,
            constraints,
            intensity,
        )

    elif section_name == "Cooldown / Mobility":
        new_section = generate_cooldown_section(
            level,
            duration_lookup.get("Cooldown / Mobility", 5),
            equipment,
            constraints,
        )

    if new_section:
        updated_sections: List[Dict[str, Any]] = []
        for section in workout["sections"]:
            if section["name"] == section_name:
                updated_sections.append(new_section)
            else:
                updated_sections.append(section)
        workout["sections"] = updated_sections

    return workout

# =========================================================
# PERSISTENCE / CRUD HELPERS
# =========================================================

def create_workout_record(
    workout: Dict[str, Any],
    status: str = "draft",
    favorite: bool = False,
) -> int:
    """
    Create a new workout record and audit the creation.
    Returns the inserted workout ID.
    """
    run(
        """
        INSERT INTO workouts (
            name, class_type, level, training_goal, intensity, coach,
            tags, status, is_favorite, payload_json, version,
            parent_workout_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            workout["name"],
            workout["class_type"],
            workout["level"],
            workout["training_goal"],
            workout["intensity"],
            workout.get("coach", ""),
            ",".join(workout.get("tags", [])),
            status,
            1 if favorite else 0,
            dump_json(workout),
            1,
            None,
            now_iso(),
            now_iso(),
        ),
    )
    row = fetch_one("SELECT last_insert_rowid() AS id")
    workout_id = row["id"]

    current_user = get_current_user()
    actor = current_user["username"] if current_user else "system"
    log_audit("workout", workout_id, "create", workout, actor)

    return workout_id


def update_workout_record(
    workout_id: int,
    workout: Dict[str, Any],
    status: str,
    favorite: bool,
) -> None:
    """
    Update an existing workout record and increment its version.
    """
    current = fetch_one("SELECT * FROM workouts WHERE id = ?", (workout_id,))
    if current is None:
        raise ValueError(f"Workout {workout_id} does not exist.")

    current_payload = load_json(current["payload_json"], {})
    new_version = int(current["version"]) + 1

    run(
        """
        UPDATE workouts
        SET name = ?, class_type = ?, level = ?, training_goal = ?, intensity = ?,
            coach = ?, tags = ?, status = ?, is_favorite = ?, payload_json = ?,
            version = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            workout["name"],
            workout["class_type"],
            workout["level"],
            workout["training_goal"],
            workout["intensity"],
            workout.get("coach", ""),
            ",".join(workout.get("tags", [])),
            status,
            1 if favorite else 0,
            dump_json(workout),
            new_version,
            now_iso(),
            workout_id,
        ),
    )

    current_user = get_current_user()
    actor = current_user["username"] if current_user else "system"
    log_audit(
        "workout",
        workout_id,
        "update",
        {"before": current_payload, "after": workout},
        actor,
    )


def delete_workout_record(workout_id: int) -> None:
    """
    Delete a workout record and audit the deletion.
    """
    current = fetch_one("SELECT * FROM workouts WHERE id = ?", (workout_id,))
    if current is None:
        return

    payload = load_json(current["payload_json"], {})
    run("DELETE FROM workouts WHERE id = ?", (workout_id,))

    current_user = get_current_user()
    actor = current_user["username"] if current_user else "system"
    log_audit("workout", workout_id, "delete", {"deleted": payload}, actor)


def get_workout_by_id(workout_id: int) -> Optional[sqlite3.Row]:
    """Fetch a single workout row."""
    return fetch_one("SELECT * FROM workouts WHERE id = ?", (workout_id,))


def get_workouts_filtered(
    search: str = "",
    coach_filter: str = "",
    class_type: str = "",
    level: str = "",
    tag_filter: str = "",
    status_filter: str = "",
    favorites_only: bool = False,
) -> List[sqlite3.Row]:
    """
    Filter workouts in Python for flexible UI querying.
    """
    rows = fetch_all("SELECT * FROM workouts ORDER BY updated_at DESC")
    out: List[sqlite3.Row] = []
    search = search.lower().strip()

    for r in rows:
        if favorites_only and not r["is_favorite"]:
            continue
        if coach_filter and coach_filter != r["coach"]:
            continue
        if class_type and class_type != r["class_type"]:
            continue
        if level and level != r["level"]:
            continue
        if status_filter and status_filter != r["status"]:
            continue
        if tag_filter and tag_filter.lower() not in (r["tags"] or "").lower():
            continue

        blob = f"{r['name']} {(r['tags'] or '')} {r['training_goal']} {r['level']}".lower()
        if search and search not in blob:
            continue

        out.append(r)

    return out


def toggle_workout_favorite(workout_id: int) -> None:
    """
    Toggle favorite flag for a workout.
    """
    row = get_workout_by_id(workout_id)
    if row is None:
        raise ValueError(f"Workout {workout_id} does not exist.")

    new_value = 0 if row["is_favorite"] else 1
    run(
        "UPDATE workouts SET is_favorite = ?, updated_at = ? WHERE id = ?",
        (new_value, now_iso(), workout_id),
    )

    current_user = get_current_user()
    actor = current_user["username"] if current_user else "system"
    log_audit(
        "workout",
        workout_id,
        "toggle_favorite",
        {"is_favorite": bool(new_value)},
        actor,
    )


# =========================================================
# TEMPLATE CRUD
# =========================================================

def create_template(
    name: str,
    template_type: str,
    description: str,
    tags: List[str],
    payload: Dict[str, Any],
) -> int:
    """
    Create a template record and audit it.
    """
    run(
        """
        INSERT INTO templates (
            name, template_type, description, tags, payload_json,
            is_archived, created_by, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
        """,
        (
            name,
            template_type,
            description,
            ",".join(tags),
            dump_json(payload),
            get_current_user()["username"] if get_current_user() else "system",
            now_iso(),
            now_iso(),
        ),
    )

    row = fetch_one("SELECT last_insert_rowid() AS id")
    template_id = row["id"]

    current_user = get_current_user()
    actor = current_user["username"] if current_user else "system"
    log_audit("template", template_id, "create", payload, actor)

    return template_id


def duplicate_template(template_id: int, new_name: Optional[str] = None) -> int:
    """
    Duplicate an existing template and return the new ID.
    """
    row = fetch_one("SELECT * FROM templates WHERE id = ?", (template_id,))
    if row is None:
        raise ValueError(f"Template {template_id} does not exist.")

    payload = load_json(row["payload_json"], {})
    new_template_name = new_name or f"{row['name']} Copy"

    return create_template(
        name=new_template_name,
        template_type=row["template_type"],
        description=row["description"] or "",
        tags=parse_tags(row["tags"] or ""),
        payload=payload,
    )


def archive_template(template_id: int) -> None:
    """
    Soft-archive a template.
    """
    row = fetch_one("SELECT * FROM templates WHERE id = ?", (template_id,))
    if row is None:
        return

    run(
        "UPDATE templates SET is_archived = 1, updated_at = ? WHERE id = ?",
        (now_iso(), template_id),
    )

    current_user = get_current_user()
    actor = current_user["username"] if current_user else "system"
    log_audit("template", template_id, "archive", {"archived": True}, actor)


def get_templates(include_archived: bool = False) -> List[sqlite3.Row]:
    """
    List templates ordered by most recently updated.
    """
    if include_archived:
        return fetch_all("SELECT * FROM templates ORDER BY updated_at DESC")
    return fetch_all(
        "SELECT * FROM templates WHERE is_archived = 0 ORDER BY updated_at DESC"
    )


def get_template_by_id(template_id: int) -> Optional[sqlite3.Row]:
    """Fetch a single template."""
    return fetch_one("SELECT * FROM templates WHERE id = ?", (template_id,))


# =========================================================
# PROGRAM CRUD
# =========================================================

def create_program_record(
    name: str,
    weeks: int,
    level: str,
    goal_priority: str,
    tags: List[str],
    payload: Dict[str, Any],
) -> int:
    """
    Create a program record and audit it.
    """
    run(
        """
        INSERT INTO programs (
            name, weeks, level, goal_priority, tags, is_archived,
            payload_json, created_by, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
        """,
        (
            name,
            weeks,
            level,
            goal_priority,
            ",".join(tags),
            dump_json(payload),
            get_current_user()["username"] if get_current_user() else "system",
            now_iso(),
            now_iso(),
        ),
    )

    row = fetch_one("SELECT last_insert_rowid() AS id")
    program_id = row["id"]

    current_user = get_current_user()
    actor = current_user["username"] if current_user else "system"
    log_audit("program", program_id, "create", payload, actor)

    return program_id


def archive_program(program_id: int) -> None:
    """
    Soft-archive a program.
    """
    row = fetch_one("SELECT * FROM programs WHERE id = ?", (program_id,))
    if row is None:
        return

    run(
        "UPDATE programs SET is_archived = 1, updated_at = ? WHERE id = ?",
        (now_iso(), program_id),
    )

    current_user = get_current_user()
    actor = current_user["username"] if current_user else "system"
    log_audit("program", program_id, "archive", {"archived": True}, actor)


def get_programs(include_archived: bool = False) -> List[sqlite3.Row]:
    """
    List program rows ordered by most recently updated.
    """
    if include_archived:
        return fetch_all("SELECT * FROM programs ORDER BY updated_at DESC")
    return fetch_all(
        "SELECT * FROM programs WHERE is_archived = 0 ORDER BY updated_at DESC"
    )


def get_program_by_id(program_id: int) -> Optional[sqlite3.Row]:
    """Fetch a single program."""
    return fetch_one("SELECT * FROM programs WHERE id = ?", (program_id,))


# =========================================================
# WHITEBOARD CRUD
# =========================================================

def save_uploaded_file(uploaded_file) -> str:
    """
    Save an uploaded Streamlit file to disk and return its path.
    """
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    file_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return file_path


def create_whiteboard_record(
    title: str,
    uploaded_file,
    notes: str = "",
    tags: str = "",
    linked_workout_id: Optional[int] = None,
    linked_program_id: Optional[int] = None,
    coach: str = "",
) -> int:
    """
    Save a whiteboard image and persist its metadata.
    """
    file_path = save_uploaded_file(uploaded_file)

    run(
        """
        INSERT INTO whiteboards (
            title, file_path, notes, tags, linked_workout_id,
            linked_program_id, coach, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            file_path,
            notes,
            tags,
            linked_workout_id,
            linked_program_id,
            coach,
            now_iso(),
        ),
    )

    row = fetch_one("SELECT last_insert_rowid() AS id")
    whiteboard_id = row["id"]

    current_user = get_current_user()
    actor = current_user["username"] if current_user else "system"
    log_audit(
        "whiteboard",
        whiteboard_id,
        "create",
        {
            "title": title,
            "file_path": file_path,
            "notes": notes,
            "tags": tags,
            "linked_workout_id": linked_workout_id,
            "linked_program_id": linked_program_id,
            "coach": coach,
        },
        actor,
    )

    return whiteboard_id


def get_whiteboards() -> List[sqlite3.Row]:
    """
    Return all whiteboards ordered newest first.
    """
    return fetch_all("SELECT * FROM whiteboards ORDER BY created_at DESC")


def get_whiteboard_by_id(whiteboard_id: int) -> Optional[sqlite3.Row]:
    """Fetch a single whiteboard."""
    return fetch_one("SELECT * FROM whiteboards WHERE id = ?", (whiteboard_id,))


def delete_whiteboard_record(whiteboard_id: int) -> None:
    """
    Delete a whiteboard record and remove its file if present.
    """
    row = get_whiteboard_by_id(whiteboard_id)
    if row is None:
        return

    payload = dict(row)

    try:
        if row["file_path"] and os.path.exists(row["file_path"]):
            os.remove(row["file_path"])
    except Exception:
        pass

    run("DELETE FROM whiteboards WHERE id = ?", (whiteboard_id,))

    current_user = get_current_user()
    actor = current_user["username"] if current_user else "system"
    log_audit("whiteboard", whiteboard_id, "delete", {"deleted": payload}, actor)


# =========================================================
# AUDIT HELPERS
# =========================================================

def get_audit_entries(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    limit: int = 50,
) -> List[sqlite3.Row]:
    """
    Fetch audit entries optionally filtered by entity type / entity id.
    """
    query = "SELECT * FROM audit_log"
    params: List[Any] = []
    clauses: List[str] = []

    if entity_type:
        clauses.append("entity_type = ?")
        params.append(entity_type)

    if entity_id is not None:
        clauses.append("entity_id = ?")
        params.append(entity_id)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    return fetch_all(query, tuple(params))


# =========================================================
# EXPORT HELPERS
# =========================================================

def export_workout_txt(workout: Dict[str, Any]) -> bytes:
    """
    Export a workout as plain text.
    """
    lines: List[str] = []
    lines.append(f"Workout: {workout.get('name', 'Unnamed')}")
    lines.append(f"Class Type: {workout.get('class_type', '')}")
    lines.append(f"Level: {workout.get('level', '')}")
    lines.append(f"Goal: {workout.get('training_goal', '')}")
    lines.append(f"Intensity: {workout.get('intensity', '')}")
    lines.append("")

    for section in workout.get("sections", []):
        lines.append(f"## {section['name']} ({section['duration_min']} min)")
        lines.append(section.get("coach_notes", ""))

        for idx, item in enumerate(section.get("items", []), start=1):
            lines.append(f"{idx}. {item.get('title', '')}")

            if item.get("details"):
                lines.append(f"   Details: {item['details']}")

            if item.get("coach_cues"):
                lines.append(f"   Coach Cues: {item['coach_cues']}")

        lines.append("")

    return "\n".join(lines).encode("utf-8")


def export_json_bytes(payload: Dict[str, Any]) -> bytes:
    """
    Export any payload as JSON bytes.
    """
    return dump_json(payload).encode("utf-8")


def export_workout_pdf(workout: Dict[str, Any]) -> bytes:
    """
    Export a workout as PDF if reportlab is available.
    """
    if not PDF_EXPORT_AVAILABLE:
        raise RuntimeError("PDF export is unavailable because reportlab is not installed.")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    _, height = letter
    y = height - 40

    def line(text: str, size: int = 10, gap: int = 14) -> None:
        nonlocal y
        c.setFont("Helvetica", size)

        max_chars = 100
        wrapped = [text[i:i + max_chars] for i in range(0, len(text), max_chars)] or [""]

        for w in wrapped:
            if y < 60:
                c.showPage()
                y = height - 40
                c.setFont("Helvetica", size)
            c.drawString(40, y, w)
            y -= gap

    line(workout.get("name", "Workout"), size=14, gap=18)
    line(
        f"Type: {workout.get('class_type', '')} | "
        f"Level: {workout.get('level', '')} | "
        f"Goal: {workout.get('training_goal', '')} | "
        f"Intensity: {workout.get('intensity', '')}",
        size=10,
        gap=14,
    )
    line(" ", gap=8)

    for section in workout.get("sections", []):
        line(f"{section.get('name', 'Section')} ({section.get('duration_min', 0)} min)", size=12, gap=16)

        if section.get("coach_notes"):
            line(f"Notes: {section['coach_notes']}", size=9, gap=12)

        for item in section.get("items", []):
            line(f"- {item.get('title', '')}", size=10, gap=12)

            if item.get("details"):
                line(f"  {item['details']}", size=9, gap=11)

            if item.get("coach_cues"):
                line(f"  Coach cues: {item['coach_cues']}", size=9, gap=11)

        line(" ", gap=8)

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# =========================================================
# WORKOUT UI HELPERS
# =========================================================

def render_workout_preview(workout: Dict[str, Any], mobile: bool = False) -> None:
    """
    Render a workout in preview format.
    """
    st.markdown('<div class="bwb-card">', unsafe_allow_html=True)
    st.subheader(workout.get("name", "Workout"))

    meta = [
        f"Type: {workout.get('class_type', '')}",
        f"Level: {workout.get('level', '')}",
        f"Goal: {workout.get('training_goal', '')}",
        f"Intensity: {workout.get('intensity', '')}",
        f"Coach: {workout.get('coach', '')}",
    ]
    st.caption(" | ".join(meta))

    if workout.get("tags"):
        st.markdown(list_to_pills(workout["tags"]), unsafe_allow_html=True)

    for section in workout.get("sections", []):
        if mobile:
            st.markdown(f"### {section['name']} · {section['duration_min']} min")
            for item in section.get("items", []):
                st.write(f"**{item['title']}**")
                if item.get("details"):
                    st.write(item["details"])
        else:
            with st.expander(f"{section['name']} · {section['duration_min']} min", expanded=True):
                st.caption(section.get("coach_notes", ""))

                for item in section.get("items", []):
                    st.write(f"**{item['title']}**")

                    if item.get("details"):
                        st.write(item["details"])

                    small = []
                    if item.get("rounds"):
                        small.append(f"Rounds: {item['rounds']}")
                    if item.get("round_length_sec"):
                        small.append(f"Round Length: {seconds_to_label(item['round_length_sec'])}")
                    if item.get("rest_sec"):
                        small.append(f"Rest: {seconds_to_label(item['rest_sec'])}")

                    if small:
                        st.caption(" | ".join(small))

                    if item.get("coach_cues"):
                        st.write(f"_Coach cues:_ {item['coach_cues']}")

    st.markdown("</div>", unsafe_allow_html=True)


def render_workout_editor(workout_key: str) -> Optional[Dict[str, Any]]:
    """
    Render the editable workout UI for a workout stored in session state.
    """
    workout = st.session_state.get(workout_key)
    if not workout:
        return None

    st.subheader("Workout Editor")

    workout["name"] = st.text_input(
        "Workout Name",
        value=workout.get("name", ""),
        key=f"{workout_key}_name",
    )

    workout["coach"] = st.text_input(
        "Coach",
        value=workout.get("coach", ""),
        key=f"{workout_key}_coach",
    )

    workout["tags"] = parse_tags(
        st.text_input(
            "Tags (comma-separated)",
            value=",".join(workout.get("tags", [])),
            key=f"{workout_key}_tags",
        )
    )

    for idx, section in enumerate(workout["sections"]):
        with st.expander(f"{section['name']} · {section['duration_min']} min", expanded=True):
            c1, c2 = st.columns([3, 1])

            with c1:
                section["coach_notes"] = st.text_area(
                    "Coach Notes",
                    value=section.get("coach_notes", ""),
                    key=f"{workout_key}_section_notes_{idx}",
                    height=90,
                )

            with c2:
                if st.button("Regenerate Section", key=f"{workout_key}_regen_{idx}"):
                    st.session_state[workout_key] = regenerate_section(workout, section["name"])
                    st.rerun()

            for item_idx, item in enumerate(section.get("items", [])):
                st.markdown('<div class="bwb-divider"></div>', unsafe_allow_html=True)

                item["title"] = st.text_input(
                    f"Item {item_idx + 1} Title",
                    value=item.get("title", ""),
                    key=f"{workout_key}_{idx}_{item_idx}_title",
                )

                item["details"] = st.text_area(
                    "Details",
                    value=item.get("details", ""),
                    key=f"{workout_key}_{idx}_{item_idx}_details",
                    height=80,
                )

                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    item["rounds"] = st.number_input(
                        "Rounds",
                        min_value=0,
                        value=to_int(item.get("rounds", 0)),
                        key=f"{workout_key}_{idx}_{item_idx}_rounds",
                    )

                with col_b:
                    item["round_length_sec"] = st.number_input(
                        "Round Length (sec)",
                        min_value=0,
                        value=to_int(item.get("round_length_sec", 0)),
                        key=f"{workout_key}_{idx}_{item_idx}_round_len",
                    )

                with col_c:
                    item["rest_sec"] = st.number_input(
                        "Rest (sec)",
                        min_value=0,
                        value=to_int(item.get("rest_sec", 0)),
                        key=f"{workout_key}_{idx}_{item_idx}_rest",
                    )

                item["coach_cues"] = st.text_area(
                    "Coach Cues",
                    value=item.get("coach_cues", ""),
                    key=f"{workout_key}_{idx}_{item_idx}_cues",
                    height=70,
                )

                item["athlete_description"] = st.text_area(
                    "Athlete-Friendly Description",
                    value=item.get("athlete_description", ""),
                    key=f"{workout_key}_{idx}_{item_idx}_athlete",
                    height=70,
                )

                item["explanation"] = st.text_area(
                    "Why This Is In The Class",
                    value=item.get("explanation", ""),
                    key=f"{workout_key}_{idx}_{item_idx}_why",
                    height=70,
                )

    st.session_state[workout_key] = workout
    return workout


# =========================================================
# PAGE: DASHBOARD
# =========================================================

def render_dashboard_page() -> None:
    """
    Render the real dashboard page.
    """
    require_permission("view_dashboard")

    st.title("Dashboard")

    workout_count = fetch_one("SELECT COUNT(*) AS c FROM workouts")["c"]
    drill_count = fetch_one("SELECT COUNT(*) AS c FROM drills WHERE is_archived = 0")["c"]
    program_count = fetch_one("SELECT COUNT(*) AS c FROM programs WHERE is_archived = 0")["c"]
    whiteboard_count = fetch_one("SELECT COUNT(*) AS c FROM whiteboards")["c"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Saved Workouts", workout_count, "All draft + completed sessions")
    with c2:
        metric_card("Active Drills", drill_count, "Library items available to coaches")
    with c3:
        metric_card("Programs", program_count, "Saved multi-week plans")
    with c4:
        metric_card("Whiteboards", whiteboard_count, "Archived session photos")

    st.markdown("### Recent Activity")
    recent = get_audit_entries(limit=12)
    if not recent:
        st.info("No activity yet.")
    else:
        for row in recent:
            st.markdown(
                f"""
                <div class="bwb-card">
                    <b>{row['action'].title()}</b> · {row['entity_type']} #{row['entity_id']}<br>
                    <span class="bwb-subtle">By {row['actor']} at {row['created_at']}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("### Quick Coach Notes")
    st.write(
        "Use **Generate Class** for daily sessions. "
        "Later pages will cover saved workouts, templates, programs, whiteboards, and imports."
    )


# =========================================================
# PAGE: GENERATE CLASS
# =========================================================

def render_generate_class_page() -> None:
    """
    Render the Generate Class page using the existing generator + persistence layer.
    """
    require_permission("generate")

    st.title("Generate Class")

    with st.form("generate_class_form"):
        left, right = st.columns(2)

        with left:
            name = st.text_input(
                "Session Name",
                value=f"{datetime.now().strftime('%b %d')} BWB Session",
            )

            class_type = st.selectbox(
                "Class Type",
                [
                    "boxing",
                    "boxing + strength",
                    "boxing + cardio",
                    "strength-only",
                    "cardio-only",
                    "mixed class",
                ],
            )

            level = st.selectbox(
                "Level",
                ["beginner", "intermediate", "advanced", "fighter", "teen", "general fitness"],
            )

            training_goal = st.selectbox("Training Goal", TACTICAL_THEMES)

            intensity = st.selectbox(
                "Intensity",
                [
                    "technical",
                    "moderate",
                    "high intensity",
                    "conditioning-focused",
                    "recovery-focused",
                ],
            )

            total_duration = st.selectbox("Total Duration (min)", [45, 50, 60, 75, 90], index=2)

            format_name = st.selectbox(
                "Format",
                [
                    "Standard 60 Boxing",
                    "30 Boxing / 30 Strength",
                    "30 Boxing / 30 Cardio",
                    "40 Boxing / 20 Strength",
                    "45 Boxing / 15 Conditioning",
                    "20 / 20 / 20 Hybrid",
                    "Custom",
                ],
            )

        with right:
            rounds = st.number_input(
                "Default Boxing Rounds",
                min_value=1,
                max_value=10,
                value=4,
            )

            round_length_sec = st.selectbox(
                "Round Length",
                [120, 150, 180],
                index=2,
                format_func=seconds_to_label,
            )

            rest_sec = st.selectbox(
                "Rest Between Rounds",
                [15, 20, 30, 45, 60],
                index=3,
            )

            equipment_available = st.multiselect(
                "Equipment Available",
                [
                    "bodyweight",
                    "jump rope",
                    "heavy bag",
                    "dumbbells",
                    "kettlebells",
                    "medicine ball",
                    "bands",
                    "bench",
                    "boxes",
                    "sled",
                    "cables",
                ],
                default=["bodyweight", "jump rope", "heavy bag", "dumbbells", "bands"],
            )

            st.markdown("**Constraints**")
            limited_space = st.checkbox("Limited Space")
            no_partner_drills = st.checkbox("No Partner Drills")
            no_bags = st.checkbox("No Bags")
            low_impact_only = st.checkbox("Low Impact Only")
            bodyweight_only_strength = st.checkbox("Bodyweight-Only Strength")
            beginner_safe_only = st.checkbox("Beginner-Safe Only")
            mixed_level = st.checkbox("Mixed-Level Class")

        custom_split: Dict[str, int] = {}
        if format_name == "Custom":
            st.markdown("### Custom Split")
            a, b, c_, d, e, f = st.columns(6)

            with a:
                custom_split["warmup"] = st.number_input("Warmup", min_value=0, value=10)
            with b:
                custom_split["partner"] = st.number_input("Partner", min_value=0, value=10)
            with c_:
                custom_split["bag"] = st.number_input("Bag", min_value=0, value=10)
            with d:
                custom_split["strength_or_core"] = st.number_input("Strength/Core", min_value=0, value=10)
            with e:
                custom_split["cardio"] = st.number_input("Cardio", min_value=0, value=10)
            with f:
                custom_split["cooldown"] = st.number_input("Cooldown", min_value=0, value=5)

        tags_raw = st.text_input("Tags (comma-separated)", value=f"{level},{training_goal}")

        submitted = st.form_submit_button("Generate Class", use_container_width=True)

    if submitted:
        constraints = build_constraints_dict(
            limited_space=limited_space,
            no_partner_drills=no_partner_drills,
            no_bags=no_bags,
            low_impact_only=low_impact_only,
            bodyweight_only_strength=bodyweight_only_strength,
            beginner_safe_only=beginner_safe_only,
            mixed_level=mixed_level,
        )

        current_user = get_current_user()

        workout = generate_full_workout(
            name=name,
            class_type=class_type,
            level=level,
            training_goal=training_goal,
            intensity=intensity,
            coach=current_user["display_name"] if current_user else "",
            total_duration=total_duration,
            format_name=format_name,
            custom_split=custom_split,
            equipment_available=equipment_available,
            constraints=constraints,
            rounds=rounds,
            round_length_sec=round_length_sec,
            rest_sec=rest_sec,
            tags=parse_tags(tags_raw),
        )

        st.session_state["current_workout"] = workout
        st.success("Workout generated.")

    current_workout = render_workout_editor("current_workout")

    if current_workout:
        st.markdown("### Preview")
        render_workout_preview(current_workout)

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            if st.button("Save as Draft", use_container_width=True):
                workout_id = create_workout_record(
                    current_workout,
                    status="draft",
                    favorite=False,
                )
                st.success(f"Saved draft workout #{workout_id}.")

        with c2:
            if st.button("Save as Completed Class", use_container_width=True):
                workout_id = create_workout_record(
                    current_workout,
                    status="completed",
                    favorite=False,
                )
                st.success(f"Saved completed workout #{workout_id}.")

        with c3:
            if st.button("Save as Favorite", use_container_width=True):
                workout_id = create_workout_record(
                    current_workout,
                    status="draft",
                    favorite=True,
                )
                st.success(f"Saved favorite workout #{workout_id}.")

        with c4:
            if st.button("Save as Template", use_container_width=True):
                template_id = create_template(
                    name=current_workout["name"],
                    template_type="workout",
                    description="Saved from generator",
                    tags=current_workout.get("tags", []),
                    payload=current_workout,
                )
                st.success(f"Template #{template_id} saved.")

        export_col1, export_col2, export_col3 = st.columns(3)

        with export_col1:
            st.download_button(
                "Download JSON",
                data=export_json_bytes(current_workout),
                file_name=f"{clean_text(current_workout['name']).replace(' ', '_')}.json",
                mime="application/json",
                use_container_width=True,
            )

        with export_col2:
            st.download_button(
                "Download TXT",
                data=export_workout_txt(current_workout),
                file_name=f"{clean_text(current_workout['name']).replace(' ', '_')}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        with export_col3:
            if PDF_EXPORT_AVAILABLE:
                st.download_button(
                    "Download PDF",
                    data=export_workout_pdf(current_workout),
                    file_name=f"{clean_text(current_workout['name']).replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.info("PDF export unavailable: add `reportlab` to requirements.txt")
# =========================================================
# PAGE: GENERATE PROGRAM
# =========================================================

def render_generate_program_page() -> None:
    """
    Render the Generate Program page using the existing generator + persistence layer.
    """
    require_permission("generate")

    st.title("Generate Program")

    with st.form("program_form"):
        p1, p2, p3 = st.columns(3)

        with p1:
            program_name = st.text_input("Program Name", value="BWB 4-Week Block")
            weeks = st.slider("Weeks", 2, 12, 4)
            level = st.selectbox(
                "Level",
                ["beginner", "intermediate", "advanced", "fighter", "teen", "general fitness"],
                key="program_level",
            )

        with p2:
            priority = st.selectbox(
                "Primary Priority",
                [
                    "skill accumulation",
                    "conditioning progression",
                    "technique variety",
                    "balanced development",
                ],
            )
            base_goal = st.selectbox("Base Technical Focus", TACTICAL_THEMES, key="program_base_goal")

        with p3:
            equipment_available = st.multiselect(
                "Equipment Available",
                [
                    "bodyweight",
                    "jump rope",
                    "heavy bag",
                    "dumbbells",
                    "kettlebells",
                    "medicine ball",
                    "bands",
                    "bench",
                    "boxes",
                    "sled",
                    "cables",
                ],
                default=["bodyweight", "jump rope", "heavy bag", "dumbbells", "bands"],
                key="program_equipment",
            )
            tags_raw = st.text_input("Tags", value=f"{level},{priority},{base_goal}")

        gen_program = st.form_submit_button("Generate Program", use_container_width=True)

    if gen_program:
        program_sessions: List[Dict[str, Any]] = []

        goal_cycle = {
            "skill accumulation": [base_goal, "technique development", "defense", "angle work"],
            "conditioning progression": [base_goal, "conditioning", "endurance", "cardio capacity"],
            "technique variety": [base_goal, "counterpunching", "body punching", "movement quality"],
            "balanced development": [base_goal, "conditioning", "power", "defense"],
        }[priority]

        current_user = get_current_user()
        coach_name = current_user["display_name"] if current_user else ""

        for wk in range(1, weeks + 1):
            week_goal = goal_cycle[(wk - 1) % len(goal_cycle)]
            week_intensity = "technical" if wk == 1 else ("moderate" if wk < weeks else "high intensity")

            workout = generate_full_workout(
                name=f"Week {wk} - {week_goal.title()}",
                class_type="boxing" if week_goal not in {"boxing-specific strength", "cardio capacity"} else "mixed class",
                level=level,
                training_goal=week_goal,
                intensity=week_intensity,
                coach=coach_name,
                total_duration=60,
                format_name="Standard 60 Boxing",
                custom_split={},
                equipment_available=equipment_available,
                constraints=build_constraints_dict(
                    limited_space=False,
                    no_partner_drills=False,
                    no_bags=False,
                    low_impact_only=False,
                    bodyweight_only_strength=False,
                    beginner_safe_only=(level == "beginner"),
                    mixed_level=False,
                ),
                rounds=4 if wk < weeks else 5,
                round_length_sec=180,
                rest_sec=45 if wk < weeks else 30,
                tags=parse_tags(tags_raw),
            )

            program_sessions.append(
                {
                    "week": wk,
                    "theme": week_goal,
                    "progression_note": (
                        "Lower complexity opener."
                        if wk == 1 else
                        "Add pace or a defensive layer."
                        if wk < weeks else
                        "Peak execution under fatigue."
                    ),
                    "workout": workout,
                }
            )

        program_payload = {
            "name": program_name,
            "weeks": weeks,
            "level": level,
            "goal_priority": priority,
            "base_goal": base_goal,
            "sessions": program_sessions,
            "tags": parse_tags(tags_raw),
            "created_at": now_iso(),
        }

        st.session_state["current_program"] = program_payload
        st.success("Program generated.")

    program = st.session_state.get("current_program")
    if program:
        st.subheader(program["name"])
        st.caption(f"{program['weeks']} weeks · {program['level']} · {program['goal_priority']}")

        for session in program["sessions"]:
            with st.expander(
                f"Week {session['week']} · {session['theme'].title()}",
                expanded=session["week"] == 1,
            ):
                st.write(f"**Progression note:** {session['progression_note']}")
                render_workout_preview(session["workout"], mobile=False)

        c1, c2 = st.columns(2)

        with c1:
            if st.button("Save Program", use_container_width=True):
                program_id = create_program_record(
                    name=program["name"],
                    weeks=program["weeks"],
                    level=program["level"],
                    goal_priority=program["goal_priority"],
                    tags=program.get("tags", []),
                    payload=program,
                )
                st.success(f"Saved program #{program_id}.")

        with c2:
            st.download_button(
                "Download Program JSON",
                data=export_json_bytes(program),
                file_name=f"{clean_text(program['name']).replace(' ', '_')}.json",
                mime="application/json",
                use_container_width=True,
            )


# =========================================================
# PAGE: DRILL LIBRARY
# =========================================================

def render_drill_library_page() -> None:
    """
    Render the Drill Library page with filtering, editing, and add-drill support.
    """
    st.title("Drill Library")

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

    with filter_col1:
        category_filter = st.selectbox(
            "Category",
            ["", "warmup", "partner", "bag", "strength", "core", "cardio", "cooldown"],
        )

    with filter_col2:
        level_filter = st.selectbox(
            "Level",
            ["", "beginner", "intermediate", "advanced", "fighter", "teen", "general fitness", "all"],
        )

    with filter_col3:
        focus_filter = st.text_input("Tactical Focus Contains")

    with filter_col4:
        search_filter = st.text_input("Search")

    drill_rows = get_drills(
        category=category_filter or None,
        level=level_filter or None,
        include_archived=False,
    )

    if search_filter:
        drill_rows = [
            d for d in drill_rows
            if search_filter.lower() in f"{d['name']} {d.get('tags', '')} {d.get('explanation', '')}".lower()
        ]

    if focus_filter:
        drill_rows = [
            d for d in drill_rows
            if focus_filter.lower() in clean_text(d.get("tactical_focus", "")).lower()
        ]

    st.caption(f"{len(drill_rows)} drills found")

    for d in drill_rows:
        with st.expander(f"{d['name']} · {d['category']} · {d['level']}", expanded=False):
            st.write(d.get("explanation", ""))
            st.caption(d.get("athlete_description", ""))
            st.markdown(list_to_pills(d.get("equipment", [])), unsafe_allow_html=True)

            if d.get("tags"):
                st.write(f"Tags: {d['tags']}")

            st.write(f"Rounds default: {d.get('rounds_default', 0)}")
            st.write(f"Round length: {seconds_to_label(to_int(d.get('round_length_sec', 0)))}")
            st.write(f"Rest: {seconds_to_label(to_int(d.get('rest_sec', 0)))}")

            if has_perm("edit_content"):
                with st.form(f"edit_drill_{d['id']}"):
                    new_name = st.text_input("Name", value=d["name"])
                    new_expl = st.text_area("Explanation", value=d.get("explanation", ""))
                    new_ath = st.text_area(
                        "Athlete-Friendly Description",
                        value=d.get("athlete_description", ""),
                    )
                    new_notes = st.text_area("Coaching Notes", value=d.get("coaching_notes", ""))
                    new_tags = st.text_input("Tags", value=d.get("tags", ""))

                    save_edit = st.form_submit_button("Save Changes")
                    archive = st.form_submit_button("Archive Drill")

                    if save_edit:
                        run(
                            """
                            UPDATE drills
                            SET name = ?, explanation = ?, athlete_description = ?,
                                coaching_notes = ?, tags = ?, updated_at = ?
                            WHERE id = ?
                            """,
                            (new_name, new_expl, new_ath, new_notes, new_tags, now_iso(), d["id"]),
                        )
                        current_user = get_current_user()
                        actor = current_user["username"] if current_user else "system"
                        log_audit("drill", d["id"], "update", {"name": new_name}, actor)
                        st.success("Drill updated.")
                        st.rerun()

                    if archive and has_perm("archive"):
                        run(
                            "UPDATE drills SET is_archived = 1, updated_at = ? WHERE id = ?",
                            (now_iso(), d["id"]),
                        )
                        current_user = get_current_user()
                        actor = current_user["username"] if current_user else "system"
                        log_audit("drill", d["id"], "archive", {"archived": True}, actor)
                        st.success("Drill archived.")
                        st.rerun()

    if has_perm("edit_content"):
        st.markdown("---")
        st.subheader("Add Drill")

        with st.form("add_drill_form"):
            c1, c2 = st.columns(2)

            with c1:
                name = st.text_input("Name")
                category = st.selectbox(
                    "Category",
                    ["warmup", "partner", "bag", "strength", "core", "cardio", "cooldown"],
                    key="add_drill_category",
                )
                subcategory = st.text_input("Subcategory")
                level = st.selectbox(
                    "Level",
                    ["beginner", "intermediate", "advanced", "fighter", "teen", "general fitness", "all"],
                    key="add_drill_level",
                )
                equipment = st.multiselect(
                    "Equipment",
                    [
                        "bodyweight",
                        "jump rope",
                        "heavy bag",
                        "dumbbells",
                        "kettlebells",
                        "medicine ball",
                        "bands",
                        "bench",
                        "boxes",
                        "sled",
                        "cables",
                    ],
                    default=["bodyweight"],
                    key="add_drill_equipment",
                )
                stance_relevance = st.selectbox("Stance Relevance", ["both", "orthodox", "southpaw"])
                tactical_focus = st.text_input("Tactical Focus")
                intensity = st.selectbox("Default Intensity", ["technical", "moderate", "high", "recovery"])

            with c2:
                explanation = st.text_area("Coach-Facing Explanation")
                athlete_description = st.text_area("Athlete-Friendly Description")
                coaching_notes = st.text_area("Coaching Notes")
                tags = st.text_input("Tags")
                rounds_default = st.number_input("Rounds Default", min_value=0, value=3)
                round_length_sec = st.number_input("Round Length (sec)", min_value=0, value=180)
                rest_sec = st.number_input("Rest (sec)", min_value=0, value=30)
                low_impact_ok = st.checkbox("Low Impact OK", value=True)
                needs_partner = st.checkbox("Needs Partner")
                needs_bag = st.checkbox("Needs Bag")

            submit = st.form_submit_button("Add Drill", use_container_width=True)

            if submit:
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
                        name,
                        category,
                        subcategory,
                        level,
                        dump_json(equipment),
                        stance_relevance,
                        coaching_notes,
                        dump_json({
                            "low_impact_ok": low_impact_ok,
                            "needs_partner": needs_partner,
                            "needs_bag": needs_bag,
                        }),
                        explanation,
                        athlete_description,
                        tags,
                        rounds_default,
                        round_length_sec,
                        rest_sec,
                        intensity,
                        tactical_focus,
                        None,
                        get_current_user()["username"] if get_current_user() else "system",
                        now_iso(),
                        now_iso(),
                    ),
                )

                row = fetch_one("SELECT last_insert_rowid() AS id")
                new_id = row["id"]

                current_user = get_current_user()
                actor = current_user["username"] if current_user else "system"
                log_audit("drill", new_id, "create", {"name": name}, actor)

                st.success("Drill added.")
                st.rerun()


# =========================================================
# PAGE: SAVED WORKOUTS
# =========================================================

def render_saved_workouts_page() -> None:
    """
    Render the Saved Workouts page with filters, preview, loading, editing, and version saves.
    """
    st.title("Saved Workouts")

    f1, f2, f3, f4, f5, f6 = st.columns(6)

    with f1:
        search = st.text_input("Search")

    with f2:
        coach_filter = st.text_input("Coach")

    with f3:
        class_type = st.selectbox(
            "Class Type",
            ["", "boxing", "boxing + strength", "boxing + cardio", "strength-only", "cardio-only", "mixed class"],
        )

    with f4:
        level = st.selectbox(
            "Level",
            ["", "beginner", "intermediate", "advanced", "fighter", "teen", "general fitness"],
        )

    with f5:
        status_filter = st.selectbox("Status", ["", "draft", "completed"])

    with f6:
        favorites_only = st.checkbox("Favorites Only")

    tag_filter = st.text_input("Tag Contains")

    rows = get_workouts_filtered(
        search=search,
        coach_filter=coach_filter,
        class_type=class_type,
        level=level,
        tag_filter=tag_filter,
        status_filter=status_filter,
        favorites_only=favorites_only,
    )

    st.caption(f"{len(rows)} workouts found")

    for row in rows:
        payload = load_json(row["payload_json"], {})

        with st.expander(
            f"#{row['id']} · {row['name']} · v{row['version']} · {row['status']}",
            expanded=False,
        ):
            c1, c2 = st.columns([3, 1])

            with c1:
                render_workout_preview(payload, mobile=False)

            with c2:
                st.write(f"Coach: {row['coach']}")
                st.write(f"Tags: {row['tags']}")
                st.write(f"Favorite: {'Yes' if row['is_favorite'] else 'No'}")
                st.write(f"Updated: {row['updated_at']}")

                if st.button("Load into Generate Class", key=f"load_workout_{row['id']}", use_container_width=True):
                    st.session_state["current_workout"] = payload
                    st.session_state["nav"] = "Generate Class"
                    st.rerun()

                if has_perm("favorite") and st.button(
                    "Toggle Favorite",
                    key=f"fav_{row['id']}",
                    use_container_width=True,
                ):
                    toggle_workout_favorite(row["id"])
                    st.rerun()

                if has_perm("delete") and st.button(
                    "Delete Workout",
                    key=f"delete_{row['id']}",
                    use_container_width=True,
                ):
                    delete_workout_record(row["id"])
                    st.warning("Workout deleted.")
                    st.rerun()

                st.download_button(
                    "Download JSON",
                    data=export_json_bytes(payload),
                    file_name=f"workout_{row['id']}.json",
                    mime="application/json",
                    key=f"download_json_{row['id']}",
                    use_container_width=True,
                )

                st.download_button(
                    "Download TXT",
                    data=export_workout_txt(payload),
                    file_name=f"workout_{row['id']}.txt",
                    mime="text/plain",
                    key=f"download_txt_{row['id']}",
                    use_container_width=True,
                )

            if has_perm("edit_content"):
                st.markdown("### Quick Edit + Save New Version")
                editor_key = f"saved_workout_editor_{row['id']}"
                if editor_key not in st.session_state:
                    st.session_state[editor_key] = payload
               
                edited = render_workout_editor(editor_key)

                if edited and st.button(
                    "Save New Version",
                    key=f"save_new_version_{row['id']}",
                    use_container_width=True,
                ):
                    update_workout_record(
                        workout_id=row["id"],
                        workout=edited,
                        status=row["status"],
                        favorite=bool(row["is_favorite"]),
                    )
                    st.success("Saved new version.")
                    st.rerun()

            audit_rows = get_audit_entries(entity_type="workout", entity_id=row["id"], limit=8)
            if audit_rows:
                st.markdown("### Version / Audit History")
                for entry in audit_rows:
                    st.caption(f"{entry['created_at']} · {entry['action']} · {entry['actor']}")

    st.markdown("---")
    st.subheader("Coach Mobile View")

    if rows:
        selected_id = st.selectbox(
            "Choose Workout",
            [r["id"] for r in rows],
            format_func=lambda x: f"Workout #{x}",
        )
        chosen_row = get_workout_by_id(selected_id)
        if chosen_row:
            render_workout_preview(load_json(chosen_row["payload_json"], {}), mobile=True)

# =========================================================
# NAVIGATION ROUTER (REAL PAGES SO FAR)
# =========================================================

nav = render_top_shell()

if nav == "Dashboard":
    render_dashboard_page()

elif nav == "Generate Class":
    render_generate_class_page()

elif nav == "Generate Program":
    render_generate_program_page()

elif nav == "Drill Library":
    render_drill_library_page()

elif nav == "Saved Workouts":
    render_saved_workouts_page()

elif nav == "Templates":
    render_placeholder_page(
        "Templates",
        "Template management UI has not been added yet."
    )

elif nav == "Whiteboard Archive":
    render_placeholder_page(
        "Whiteboard Archive",
        "Whiteboard archive UI has not been added yet."
    )

elif nav == "Import Content":
    render_placeholder_page(
        "Import Content",
        "Import content UI has not been added yet."
    )

elif nav == "Settings":
    render_placeholder_page(
        "Settings",
        "Settings UI has not been added yet."
    )
