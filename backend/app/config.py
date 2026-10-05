import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DATA_DIR = Path(os.getenv("DATA_DIR", REPO / "data")).resolve()
DB_PATH = DATA_DIR / "inspection.db"
SIGNAL_DIR = DATA_DIR / "signals"
IMAGE_DIR = DATA_DIR / "images"
MODEL_DIR = DATA_DIR / "models"
FRONTEND_DIR = REPO / "frontend"

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me-please-0123456789")
TOKEN_TTL_MINUTES = int(os.getenv("TOKEN_TTL_MINUTES", "480"))
AUTO_SEED = os.getenv("AUTO_SEED", "1") == "1"
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "Demo@12345")

SEED_EQUIPMENT = int(os.getenv("SEED_EQUIPMENT", "1000"))
SEED_NDT = int(os.getenv("SEED_NDT", "50000"))
SEED_SIGNALS = int(os.getenv("SEED_SIGNALS", "10000"))
SEED_IMAGES = int(os.getenv("SEED_IMAGES", "2000"))

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "alerts@example.local")

# آستانه‌های ریسک
RISK_HIGH = 60.0
RISK_MEDIUM = 35.0
PREDICTION_HORIZON_YEARS = 5

for d in (DATA_DIR, SIGNAL_DIR, IMAGE_DIR, MODEL_DIR):
    d.mkdir(parents=True, exist_ok=True)
