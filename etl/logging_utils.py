import logging
import sys
from datetime import datetime

from etl.config import LOGS_DIR


def setup_logging(name: str) -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    for h in (logging.StreamHandler(sys.stdout),
              logging.FileHandler(LOGS_DIR / f"etl_{name}_{stamp}.log", encoding="utf-8")):
        h.setFormatter(fmt)
        root.addHandler(h)
    return logging.getLogger(f"etl.{name}")
