import os
import sys
from pathlib import Path

from loguru import logger

BASE_URL = os.getenv("SCRAPER_BASE_URL", "http://books.toscrape.com/")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CONNECT_TIMEOUT = float(os.getenv("SCRAPER_CONNECT_TIMEOUT", "10"))
READ_TIMEOUT = float(os.getenv("SCRAPER_READ_TIMEOUT", "30"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("SCRAPER_MAX_CONCURRENT", "5"))
MAX_RETRIES = int(os.getenv("SCRAPER_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("SCRAPER_RETRY_DELAY", "2.0"))
DEFAULT_MAX_PAGES = int(os.getenv("SCRAPER_DEFAULT_MAX_PAGES", "0"))
REQUEST_DELAY = float(os.getenv("SCRAPER_REQUEST_DELAY", "0.2"))

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
LOGS_DIR = PROJECT_ROOT / "logs"

EXCEL_SHEET_NAME = "Products"
EXCEL_COLUMNS = [
    "Title",
    "Category",
    "Price",
    "Rating",
    "Availability",
    "Image URL",
    "Product URL",
]
HEADER_FILL_COLOR = "1F3864"
HEADER_FONT_COLOR = "FFFFFF"
PRICE_NUMBER_FORMAT = "#,##0.00"
OUTPUT_FILENAME_PATTERN = "products_%Y-%m-%d_%H-%M.xlsx"

LOG_FILE_ROTATION = "10 MB"
LOG_FILE_RETENTION = "7 days"


def setup_logger(logs_dir=LOGS_DIR, colorize=True):
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        colorize=colorize,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(
        logs_dir / "scraper.log",
        level="DEBUG",
        rotation=LOG_FILE_ROTATION,
        retention=LOG_FILE_RETENTION,
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    )
