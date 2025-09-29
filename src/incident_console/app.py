"""애플리케이션 실행 진입점 (View + Presenter 조합)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .presenters.main_presenter import IncidentConsolePresenter
from .views.main_view import IncidentConsoleView


def run_app() -> None:
    """Incident console Qt 애플리케이션을 실행한다."""
    app = QApplication(sys.argv)
    view = IncidentConsoleView()
    IncidentConsolePresenter(view)
    view.show()
    sys.exit(app.exec())
