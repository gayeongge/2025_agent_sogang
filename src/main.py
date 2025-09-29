"""Incident console application entrypoint."""

from incident_console.app import run_app


def main() -> None:
    """Launch the incident console UI."""
    run_app()


if __name__ == "__main__":
    main()
