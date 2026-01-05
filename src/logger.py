import logging
import sys
import os
from datetime import datetime
import uuid

class MessageIDFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, 'msg_id'):
            record.msg_id = str(uuid.uuid4())
        if not hasattr(record, 'timestamp'):
            record.timestamp = datetime.now().isoformat(timespec='seconds')
        return True

class LoggerFactory:
    @staticmethod
    def create_logger(name: str = 'email_agent', level: str = 'INFO', log_file: str = None, console: bool = True) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        logger.handlers.clear()  # Reset handlers for tests

        formatter = logging.Formatter(
            fmt='%(timestamp)s %(levelname)s [%(msg_id)s] %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S'  # ISO8601
        )
        filter_ = MessageIDFilter()
        
        if console:
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(getattr(logging, level.upper(), logging.INFO))
            ch.setFormatter(formatter)
            ch.addFilter(filter_)
            logger.addHandler(ch)

        if log_file:
            fh = logging.FileHandler(log_file)
            fh.setLevel(getattr(logging, level.upper(), logging.INFO))
            fh.setFormatter(formatter)
            fh.addFilter(filter_)
            logger.addHandler(fh)

        return logger
