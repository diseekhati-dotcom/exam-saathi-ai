"""
Central configuration for the Rajasthan Exam Information Bot.

All secrets/config come from environment variables so the project
never hardcodes a bot token or other secret. On Render these are set
in the service's Environment tab; locally, copy .env.example -> .env.
"""
import os


def _get_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


class Settings:
    # --- Telegram ---
    BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")

    # --- Database ---
    # On Render's free tier the filesystem is ephemeral across deploys but
    # persistent while the instance runs, which is fine for a cache/registry
    # DB. DATABASE_PATH can be overridden to point at a Render Disk mount.
    DATABASE_PATH: str = os.environ.get("DATABASE_PATH", "data/raj_exam_bot.sqlite3")

    # --- HTTP / scraping ---
    HTTP_TIMEOUT_SECONDS: float = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "12"))
    HTTP_MAX_REDIRECTS: int = _get_int("HTTP_MAX_REDIRECTS", 5)
    HTTP_USER_AGENT: str = os.environ.get(
        "HTTP_USER_AGENT",
        "RajasthanExamInfoBot/1.0 (+https://github.com/; contact via Telegram bot)",
    )
    MAX_DOWNLOAD_BYTES: int = _get_int("MAX_DOWNLOAD_BYTES", 25 * 1024 * 1024)  # 25MB
    PDF_SNIFF_BYTES: int = _get_int("PDF_SNIFF_BYTES", 4096)

    # --- Caching ---
    CACHE_TTL_SECONDS: int = _get_int("CACHE_TTL_SECONDS", 6 * 60 * 60)  # 6 hours

    # --- Security / SSRF protection ---
    # Only these domains (and subdomains of them) may ever be requested by
    # the scraper/validator. Anything else is rejected before a request is
    # even made.
    ALLOWED_DOMAINS = [
        "rajasthan.gov.in",
        "rssb.rajasthan.gov.in",
        "rsmssb.rajasthan.gov.in",
        "rpsc.rajasthan.gov.in",
        "rajeduboard.rajasthan.gov.in",
        "hcraj.nic.in",
        "recruitment.rajasthan.gov.in",
        "police.rajasthan.gov.in",
    ]

    DEBUG: bool = _get_bool("DEBUG", False)


settings = Settings()
