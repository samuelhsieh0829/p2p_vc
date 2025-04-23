import logging

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter('\x1b[36m{asctime} {levelname:<8} {name}: \x1b[37m{message}\x1b[0m', dt_fmt, style='{')
    log = logging.getLogger(__name__)
    log.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    log.addHandler(ch)
    return log