"""Application configuration from environment variables."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "reviewbot.db"
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_STARTER = os.getenv("STRIPE_PRICE_STARTER", "")
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "")

# App
SECRET_KEY = os.getenv("SECRET_KEY", "reviewbot-dev-secret-change-me")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
SENTRY_DSN = os.getenv("SENTRY_DSN", "")

# Limits
FREE_TRIAL_DAYS = 7
STARTER_RESPONSE_LIMIT = 50

# Admin
ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "stan.evodek@gmail.com").split(",")
ADMIN_BACKDOOR_TOKEN = os.getenv("ADMIN_BACKDOOR_TOKEN", "")
# Redis
REDIS_URL = os.getenv("REDIS_URL", "")
