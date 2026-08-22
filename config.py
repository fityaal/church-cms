import os
from datetime import timedelta
from urllib.parse import quote_plus

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_db_uri():
    # Optional complete SQLAlchemy URI takes precedence.
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        return database_url.replace("mysql://", "mysql+pymysql://", 1)

    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = os.environ.get("MYSQL_PORT", "3306")
    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD", "")
    database = os.environ.get("MYSQL_DB", "church_cms")
    return (
        f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@"
        f"{host}:{port}/{quote_plus(database)}?charset=utf8mb4"
    )


def _build_connect_args():
    args = {
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
    }

    if _env_bool("MYSQL_SSL", False):
        # MYSQL_SSL_CA_PEM is treated as a FILE PATH.
        # This works on both Windows and Linux/Render.
        ca_path = os.environ.get("MYSQL_SSL_CA_PEM", "").strip()

        if not ca_path:
            ca_path = os.environ.get("MYSQL_SSL_CA", "").strip()

        if ca_path:
            ca_path = os.path.abspath(os.path.expanduser(ca_path))

            if not os.path.isfile(ca_path):
                raise FileNotFoundError(
                    f"MySQL CA certificate not found: {ca_path}"
                )

            args.update({
                "ssl_ca": ca_path,
                "ssl_verify_cert": _env_bool(
                    "MYSQL_SSL_VERIFY", True
                ),
                "ssl_verify_identity": _env_bool(
                    "MYSQL_SSL_VERIFY_IDENTITY", False
                ),
            })
        else:
            # Encrypted connection without explicit CA verification.
            args["ssl"] = {}

    return args


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "")

    MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DB = os.environ.get("MYSQL_DB", "church_cms")

    SQLALCHEMY_DATABASE_URI = _build_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 5,
        "connect_args": _build_connect_args(),
    }

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_USERNAME", "noreply@allsaintsnagpur.org")

    CHURCH_NAME = "All Saints' Cathedral, Nagpur"
    CHURCH_DIOCESE = "Diocese of Nagpur (C.N.I.)"
    CHURCH_ADDRESS = "All Saints' Cathedral, Nagpur - 440001, Maharashtra"
    CHURCH_PHONE = "+91-712-2520000"
    CHURCH_EMAIL = "office@allsaintsnagpur.org"
    CHURCH_PAN = os.environ.get("CHURCH_PAN", "")

    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")

    ITEMS_PER_PAGE = 20
    OTP_EXPIRY_MINUTES = 10
    DEFAULT_PASSWORD = os.environ.get("DEFAULT_PASSWORD", "")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    # Production bootstrap is intentionally off. Use create_admin.py once.
    SEED_DEFAULTS = _env_bool("SEED_DEFAULTS", False)


class DevelopmentConfig(Config):
    DEBUG = True
    SEED_DEFAULTS = _env_bool("SEED_DEFAULTS", True)
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": ProductionConfig,
}
