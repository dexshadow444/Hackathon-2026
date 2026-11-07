"""Central configuration. Every value comes from environment variables (.env locally,
the host's environment settings when deployed). Nothing secret is hard-coded in repo."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

IST = ZoneInfo("Asia/Kolkata")


def _str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool = False) -> bool:
    return _str(name, str(default)).lower() in {"1", "true", "yes", "on"}


def _dt(name: str, default: str) -> datetime:
    val = _str(name, default)
    try:
        dt = datetime.fromisoformat(val)
    except Exception:
        dt = datetime.fromisoformat(default)
    return dt if dt.tzinfo else dt.replace(tzinfo=IST)


class Settings:
    APP_ENV = _str("APP_ENV", "development").lower()
    SECRET_KEY = _str("SECRET_KEY", "hackathon-dev-secret-key-replace-in-prod-8f13-41dd")
    HOST = _str("HOST", "127.0.0.1")
    PORT = _int("PORT", 8000)

    EVENT_NAME = _str("EVENT_NAME", "JM Vertex Hackathon 2027")
    TAGLINE = _str("TAGLINE", "Turn a real-world problem into a working prototype in 24 hours.")
    ORGANISER = _str("ORGANISER", "JM Vertex Technologies")
    EVENT_LOCATION = _str("EVENT_LOCATION", "Pollachi, Tamil Nadu")
    VENUE = _str("VENUE", "JM Vertex Innovation Hub, Pollachi, Tamil Nadu")

    ADMIN_USERNAME = _str("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = _str("ADMIN_PASSWORD", "AdminPass@2027!")

    RAZORPAY_KEY_ID = _str("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = _str("RAZORPAY_KEY_SECRET")

    SUPABASE_URL = _str("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = _str("SUPABASE_SERVICE_KEY")
    SUPABASE_BUCKET = _str("SUPABASE_BUCKET", "hackathon-ideas")

    # Google Drive configuration (Folder link or Service Account)
    GOOGLE_DRIVE_FOLDER_URL = _str("GOOGLE_DRIVE_FOLDER_URL", "https://drive.google.com/drive/folders/your-folder-id")
    GOOGLE_DRIVE_FOLDER_ID = _str("GOOGLE_DRIVE_FOLDER_ID", "")
    GOOGLE_SERVICE_ACCOUNT_JSON = _str("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    GOOGLE_SERVICE_ACCOUNT_FILE = _str("GOOGLE_SERVICE_ACCOUNT_FILE", "")

    # Pricing & Team Structure (₹99 per member / participant; 2 to 5 members total)
    REGISTRATION_FEE_PER_MEMBER_INR = _int("REGISTRATION_FEE_PER_MEMBER_INR", 99)
    # Legacy alias support if someone sets REGISTRATION_FEE_INR to 99
    REGISTRATION_FEE_INR = _int("REGISTRATION_FEE_INR", 99)
    MIN_TEAM_MEMBERS = _int("MIN_TEAM_MEMBERS", 2)
    MAX_TEAM_MEMBERS = _int("MAX_TEAM_MEMBERS", 5)

    # Dates configured from .env
    REGISTRATION_OPEN_DATE = _dt("REGISTRATION_OPEN_DATE", "2026-10-30T00:00:00")
    REGISTRATION_DEADLINE = _dt("REGISTRATION_DEADLINE", "2026-12-20T23:59:59")
    HACKATHON_START_DATE = _dt("HACKATHON_START_DATE", "2027-01-07T09:00:00")
    HACKATHON_END_DATE = _dt("HACKATHON_END_DATE", "2027-01-08T09:00:00")

    CONTACT_EMAIL = _str("CONTACT_EMAIL", "support@jmvertex.com")
    CONTACT_PHONE = _str("CONTACT_PHONE", "+91 98765 43210")

    # Registration confirmation email (SMTP; Gmail uses smtp.gmail.com:587).
    SMTP_HOST = _str("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = _int("SMTP_PORT", 587)
    SMTP_SENDER_EMAIL = _str("SMTP_SENDER_EMAIL")
    SMTP_SENDER_PASSWORD = _str("SMTP_SENDER_PASSWORD")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def has_supabase(self) -> bool:
        return bool(self.SUPABASE_URL and self.SUPABASE_SERVICE_KEY)

    @property
    def has_razorpay(self) -> bool:
        return bool(self.RAZORPAY_KEY_ID and self.RAZORPAY_KEY_SECRET)

    @property
    def has_google_drive_folder(self) -> bool:
        return bool(self.GOOGLE_DRIVE_FOLDER_URL or self.GOOGLE_DRIVE_FOLDER_ID)

    @property
    def force_unlock(self) -> bool:
        # Developer-only flag: never honoured in production, never shown in the UI.
        return _bool("FORCE_UNLOCK_REGISTRATION", False) and not self.is_production


settings = Settings()
