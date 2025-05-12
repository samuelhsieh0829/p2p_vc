import logging

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

import logging

import logging
from logging.handlers import TimedRotatingFileHandler

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(
        '\x1b[36m{asctime} {levelname:<8} {name}: \x1b[37m{message}\x1b[0m',
        dt_fmt,
        style='{'
    )
    file_formatter = logging.Formatter(
        '{asctime} {levelname:<8} {name}: {message}',
        dt_fmt,
        style='{'
    )

    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)

    if not log.handlers:
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(formatter)
        log.addHandler(ch)

        # Timed rotating file handler: rotates daily, keeps 7 days
        fh = TimedRotatingFileHandler(
            "client.log",
            when="midnight",           # Rotate at midnight
            interval=1,
            backupCount=7,             # Keep last 7 days
            encoding="utf-8",
            utc=False
        )
        fh.suffix = "%Y-%m-%d"         # Timestamp suffix for rotated logs
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(file_formatter)
        log.addHandler(fh)

    return log
