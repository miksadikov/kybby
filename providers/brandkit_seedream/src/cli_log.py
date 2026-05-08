"""
Консольный лог для CLI: все сообщения идут в терминал (stdout/stderr), не в браузер.
Формат близок к printf: есть функции *f(fmt, *args) с подстановкой через %.
"""
from __future__ import annotations

import sys
from datetime import datetime


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fmt(fmt: str, args: tuple) -> str:
    if not args:
        return fmt
    try:
        return fmt % args
    except (TypeError, ValueError):
        return fmt


def info(fmt: str, *args: object) -> None:
    print(f"[{_ts()}] [INFO] {_fmt(fmt, args)}", flush=True)


def warn(fmt: str, *args: object) -> None:
    print(f"[{_ts()}] [WARN] {_fmt(fmt, args)}", file=sys.stderr, flush=True)


def error(fmt: str, *args: object) -> None:
    print(f"[{_ts()}] [ERROR] {_fmt(fmt, args)}", file=sys.stderr, flush=True)


def debug(fmt: str, *args: object) -> None:
    """Подробности для отладки (в stderr)."""
    print(f"[{_ts()}] [DEBUG] {_fmt(fmt, args)}", file=sys.stderr, flush=True)
