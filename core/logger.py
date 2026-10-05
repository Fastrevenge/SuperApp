"""Настройка логирования."""
import logging
from core.config import LOG_DIR


def setup_logger(level: int = logging.INFO) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(LOG_DIR / "superapp.log"), encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )