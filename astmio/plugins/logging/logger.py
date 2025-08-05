import logging
import logging.config
import sys
from datetime import datetime
from pathlib import Path

import dataset
import structlog
from sqlalchemy import JSON, TEXT
from structlog.processors import JSONRenderer
from structlog.types import EventDict, WrappedLogger

from astmio.plugins.base import BasePlugin


class StructlogPlugin(BasePlugin):
    """
    A plugin to configure the application-wide structlog setup.
    It encapsulates the existing setup_logging function.
    """

    name = "structlog_manager"
    description = "Configures structlog with console, file, and DB handlers."

    def __init__(self, **kwargs):
        """
        Initializes the plugin with configuration for setup_logging.

        Args:
            **kwargs: Arguments to be passed directly to setup_logging, e.g.,
                      log_level="INFO", log_to_file=True, db_path="logs.db", etc.
        """
        # We don't call super().__init__() because we want to pass all kwargs
        # directly to our config. BasePlugin's __init__ is simple enough to bypass.
        self.config = kwargs
        self.manager = None

    def install(self, manager):
        """
        Called when the plugin is activated. This triggers the logging configuration.
        """
        super().install(manager)
        logging.info("StructlogPlugin is activating. Configuring logging...")

        if self.config.get("log_to_file"):
            info_file = self.config.get("log_file_path")
            if info_file:
                Path(info_file).parent.mkdir(parents=True, exist_ok=True)

            error_file = self.config.get("error_log_path")
            if error_file:
                Path(error_file).parent.mkdir(parents=True, exist_ok=True)

        if self.config.get("log_to_db"):
            db_file = self.config.get("db_path")
            if db_file:
                db_dir = Path(db_file).parent
                db_dir.mkdir(parents=True, exist_ok=True)
                logging.info(f"Ensured database directory exists: {db_dir}")

        setup_logging(**self.config)

        logging.info("Logging has been configured by StructlogPlugin.")

    def uninstall(self, manager):
        """
        When the plugin is deactivated, we can reset the logging.
        """
        super().uninstall(manager)
        logging.getLogger().handlers.clear()
        logging.info("Logging handlers cleared by StructlogPlugin.")


class LevelFilter(logging.Filter):
    """
    Filters log records based on a specific level.
    Unlike the default level setting, this is an exact match.
    """

    def __init__(self, level):
        super().__init__()
        self.level = level

    def filter(self, record):
        return record.levelno == self.level


class BelowLevelFilter(logging.Filter):
    def __init__(self, max_level):
        super().__init__()
        self.max_level = max_level

    def filter(self, record):
        return record.levelno < self.max_level


def setup_logging(
    log_level: str = "INFO",
    log_to_console: bool = True,
    log_to_file: bool = False,
    info_log_path: str = "logs/info.log",
    error_log_path: str = "logs/error.log",
    log_to_db: bool = False,
    db_path: str = "astmio_logs.db",
):
    """
    Configures structured logging using structlog.

    Args:
        log_level (str): The minimum log level to output (e.g., "INFO", "DEBUG").
        log_to_console (bool): If True, logs will be output to the console.
        log_to_file (bool): If True, logs will be written to a file.
        log_to_db (bool): If True, logs will be stored in a SQLite database.
        log_file_path (str): The path to the log file.
        db_path (str): The path to the SQLite database file.
    """
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        DataMaskingProcessor(),
    ]

    # Console renderer for development
    console_formatter = structlog.dev.ConsoleRenderer()

    # JSON renderer for files and other structured outputs
    json_formatter = JSONRenderer(sort_keys=True)

    # Use a single, unified chain of processors
    # The final processor will be chosen by the handler
    structlog.configure(
        processors=processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "below_warning": {
                "()": BelowLevelFilter,
                "max_level": logging.WARNING,
            }
        },
        "formatters": {
            "console": {
                "()": "structlog.stdlib.ProcessorFormatter",
                "processor": console_formatter,
            },
            "json": {
                "()": "structlog.stdlib.ProcessorFormatter",
                "processor": json_formatter,
                "foreign_pre_chain": processors,
            },
        },
        "handlers": {},
        "loggers": {
            "": {
                "handlers": [],
                "level": log_level,
                "propagate": True,
            },
        },
    }

    if log_to_console:
        log_config["handlers"]["console"] = {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "console",
        }
        log_config["loggers"][""]["handlers"].append("console")

    if log_to_file:
        log_config["handlers"]["info_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": info_log_path,
            "maxBytes": 5 * 1024 * 1024,  # 5MB
            "backupCount": 3,
            "formatter": "json",
            "level": "INFO",  # This handler only cares about INFO and above
            "filters": [
                "below_warning"
            ],  # CRITICAL: Only log records BELOW WARNING
        }
        log_config["loggers"][""]["handlers"].append("info_file")

        log_config["handlers"]["error_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": error_log_path,
            "maxBytes": 5 * 1024 * 1024,  # 5MB
            "backupCount": 3,
            "formatter": "json",
            "level": "WARNING",  # This handler only cares about WARNING and above
        }
        log_config["loggers"][""]["handlers"].append("error_file")

    if log_to_db:
        log_config["handlers"]["sqlite"] = {
            "class": "astmio.logging.SQLiteHandler",
            "db_path": db_path,
            "formatter": "json",
        }
        log_config["loggers"][""]["handlers"].append("sqlite")

    logging.config.dictConfig(log_config)


class DataMaskingProcessor:
    """
    A structlog processor to mask sensitive data in log records.
    (Your full class code from logging.py goes here)
    """

    SENSITIVE_KEYS = {"password", "patient_id", "secret"}

    def __call__(
        self, logger: WrappedLogger, method_name: str, event_dict: EventDict
    ) -> EventDict:
        for key, value in event_dict.items():
            if key in self.SENSITIVE_KEYS:
                event_dict[key] = "********"
            elif isinstance(value, dict):
                event_dict[key] = self._mask_nested(value)
        return event_dict

    def _mask_nested(self, data: dict) -> dict:
        for key, value in data.items():
            if key in self.SENSITIVE_KEYS:
                data[key] = "********"
            elif isinstance(value, dict):
                data[key] = self._mask_nested(value)
        return data


class SQLiteHandler(logging.Handler):
    """

    A logging handler that writes log records to a SQLite database.
    (Your full class code from logging.py goes here)
    """

    def __init__(self, db_path: str = "astmio_logs.db"):
        super().__init__()
        self.db_path = db_path
        # Create table with an explicit schema if it doesn't exist
        db = self._get_db()
        with db as tx:
            if "logs" not in tx.tables:
                tx.create_table(
                    "logs", primary_id="id", primary_type=db.types.integer
                )
                table = tx["logs"]
                table.create_column("timestamp", TEXT)
                table.create_column("name", TEXT)
                table.create_column("level", TEXT)
                table.create_column("message", TEXT)
                # This explicitly uses SQLAlchemy's JSON type, which maps
                # to SQLite's native JSON/JSONB (BLOB) storage.
                table.create_column("data", JSON)

    def _get_db(self):
        """Returns a new database connection."""
        return dataset.connect(f"sqlite:///{self.db_path}")

    def emit(self, record: logging.LogRecord):
        try:
            message = ""
            data = {}

            if isinstance(record.msg, dict):  # This is a structlog record
                log_data = record.msg
                message = log_data.get("event", "")
                data = {
                    k: v
                    for k, v in log_data.items()
                    if k not in ["timestamp", "logger", "level", "event"]
                }
            else:  # This is a standard library record
                message = record.getMessage()
                standard_attrs = {
                    "args",
                    "asctime",
                    "created",
                    "exc_info",
                    "exc_text",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "message",
                    "module",
                    "msecs",
                    "msg",
                    "name",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "thread",
                    "threadName",
                    "extra",
                }
                data = {
                    k: v
                    for k, v in record.__dict__.items()
                    if k not in standard_attrs
                }

            with self._get_db() as tx:
                table = tx["logs"]
                table.insert(
                    {
                        "timestamp": datetime.fromtimestamp(
                            record.created
                        ).isoformat(),
                        "name": record.name,
                        "level": record.levelname,
                        "message": message,
                        "data": data,
                    }
                )
        except Exception as e:
            # Fallback for when even the database logging fails
            print(f"--- DATABASE LOGGING FAILED: {e} ---")
            print(f"--- ORIGINAL RECORD: {record.__dict__} ---")


def get_logger(name: str = None) -> WrappedLogger:
    """
    Returns a structlog logger.
    (Your full function code from logging.py goes here)
    """
    return structlog.get_logger(name)
