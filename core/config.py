"""Конфигурация приложения."""
from pathlib import Path

APP_NAME = "SuperApp"
APP_VERSION = "0.1.0"

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
LOG_DIR = BASE_DIR / "logs"

CBR_BASE_URL = "https://www.cbr.ru/scripts"
CBR_DAILY = CBR_BASE_URL + "/XML_daily.asp"
CBR_DYNAMIC = CBR_BASE_URL + "/XML_dynamic.asp"

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
NAV_WIDTH = 220