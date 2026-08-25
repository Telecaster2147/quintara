"""Quintara: local A-share weekly research application."""
from __future__ import annotations

__version__ = "0.2.1"


def main() -> int:
    from .cli import main as cli_main

    return cli_main()
