"""
OmniRoute Analytics — Configuration
Connects to MySQL (default) or SQLite (fallback).
"""
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

# ---------- Database ----------
# Set USE_SQLITE=1 to fall back to SQLite (no MySQL needed)
USE_SQLITE = os.getenv("USE_SQLITE", "0") == "1"

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "omniroute")

if USE_SQLITE:
    DATABASE_URL = "sqlite:///./omniroute.db"
else:
    # URL-encode password to handle special characters like @
    encoded_password = quote_plus(MYSQL_PASSWORD)
    DATABASE_URL = (
        f"mysql+pymysql://{MYSQL_USER}:{encoded_password}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    )

# ---------- Paths ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_PATH = os.getenv(
    "CSV_PATH",
    os.path.join(
        os.path.dirname(BASE_DIR),
        "jan to may police violation_anonymized791b166.csv",
    ),
)

# ---------- App ----------
APP_TITLE = "OmniRoute Analytics"
APP_VERSION = "1.0.0"
CORS_ORIGINS = ["*"]

# ---------- Streaming ----------
STREAM_SPEED_MULTIPLIER = float(os.getenv("STREAM_SPEED", "50.0"))
