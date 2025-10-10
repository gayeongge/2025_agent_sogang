"""Incident response console backend entrypoint."""

from __future__ import annotations

from src.backend.main import run


def main() -> None:
    """Launch the FastAPI backend server."""
    run()


if __name__ == "__main__":
    main()
