"""
Shared utilities: Jinja2 environment, formatting helpers, logging setup.
"""

from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
import sys


def format_currency(value: float | int | None) -> str:
    """Format number as Indonesian Rupiah (e.g., 250000000 → '250.000.000')."""
    if value is None:
        return "-"
    return f"{int(value):,}".replace(",", ".")


def _strftime(value, format_str: str = "%d %B %Y"):
    """Jinja2 filter: format datetime/date/string to formatted date."""
    if value is None or value == "":
        return "-"
    if isinstance(value, str):
        # Parse ISO format or common formats
        for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
            try:
                value = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        else:
            return str(value)
    if isinstance(value, datetime):
        # Indonesian month names
        months = {
            1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
            5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
            9: "September", 10: "Oktober", 11: "November", 12: "Desember",
        }
        if "%B" in format_str:
            return value.strftime(format_str.replace("%B", months.get(value.month, "")))
        return value.strftime(format_str)
    return str(value)


def create_jinja_env(templates_dir: Path | str) -> Environment:
    """Create a Jinja2 Environment with custom filters for document templates."""
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals['today'] = datetime.now()
    env.globals['timedelta'] = timedelta
    env.filters["strftime"] = _strftime
    env.filters["format_currency"] = format_currency
    return env


def setup_logging(level: str = "INFO"):
    """Configure loguru logging."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    logger.add(
        "logs/app.log",
        level=level,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )
    return logger