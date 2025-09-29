"""메인 콘솔 View - Qt 위젯 구성과 UI 신호를 담당한다."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models import JiraSettings, PrometheusSettings, SlackSettings


class IncidentConsoleView(QMainWindow):
    """UI를 렌더링하고 사용자 입력 이벤트를 Signal로 내보내는 View."""

    trigger_alert_requested = Signal()
    verify_recovery_requested = Signal()

    slack_test_requested = Signal()
    slack_save_requested = Signal()

    jira_test_requested = Signal()
    jira_save_requested = Signal()

    prometheus_test_requested = Signal()
    prometheus_save_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Incident Response Console")
        self.resize(1280, 780)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        layout.addWidget(self._build_left_panel(), stretch=3)
        layout.addWidget(self._build_right_panel(), stretch=2)

        self.setCentralWidget(central)
        self._apply_theme()

        self._trigger_busy_count = 0

        self._wire_signals()

    # region UI 빌더
    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(18)

        header = QLabel("Ops Mission Control")
        header.setObjectName("headerLabel")
        header.setFont(QFont("Segoe UI", 28, QFont.Bold))
        layout.addWidget(header)

        subheader = QLabel("Prometheus ↔ Slack ↔ Jira")
        subheader.setObjectName("subheaderLabel")
        layout.addWidget(subheader)

        alert_section = QGroupBox("Active Alerts")
        alert_layout = QVBoxLayout(alert_section)
        alert_layout.setSpacing(12)

        self.alert_list = QListWidget()
        self.alert_list.setObjectName("alertList")
        self.alert_list.setMinimumHeight(180)
        alert_layout.addWidget(self.alert_list)

        trigger_row = QHBoxLayout()
        self.trigger_button = QPushButton("Trigger Alert")
        trigger_row.addWidget(self.trigger_button)
        trigger_row.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        alert_layout.addLayout(trigger_row)
        layout.addWidget(alert_section)

        diagnosis_section = QGroupBox("Root Cause Hypotheses (Top 3)")
        diagnosis_layout = QVBoxLayout(diagnosis_section)
        diagnosis_layout.setSpacing(12)

        self.diagnosis_view = QTextEdit()
        self.diagnosis_view.setObjectName("diagnosisView")
        self.diagnosis_view.setReadOnly(True)
        diagnosis_layout.addWidget(self.diagnosis_view)
        layout.addWidget(diagnosis_section)

        evidence_section = QGroupBox("Evidence & Telemetry")
        evidence_layout = QVBoxLayout(evidence_section)
        evidence_layout.setSpacing(12)

        self.evidence_view = QTextEdit()
        self.evidence_view.setObjectName("evidenceView")
        self.evidence_view.setReadOnly(True)
        evidence_layout.addWidget(self.evidence_view)
        layout.addWidget(evidence_section)

        action_section = QGroupBox("Recommended Actions")
        action_layout = QVBoxLayout(action_section)
        action_layout.setSpacing(12)

        self.action_view = QTextEdit()
        self.action_view.setObjectName("actionView")
        self.action_view.setReadOnly(True)
        action_layout.addWidget(self.action_view)

        self.verify_button = QPushButton("Verify Recovery")
        self.verify_button.setEnabled(False)
        action_layout.addWidget(self.verify_button)
        layout.addWidget(action_section)

        system_section = QGroupBox("System Feed")
        system_layout = QVBoxLayout(system_section)

        self.system_feed = QTextEdit()
        self.system_feed.setObjectName("systemFeed")
        self.system_feed.setReadOnly(True)
        system_layout.addWidget(self.system_feed)

        layout.addWidget(system_section)
        layout.addStretch(1)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(18)

        header = QLabel("Integration Settings")
        header.setObjectName("settingsHeader")
        header.setFont(QFont("Segoe UI", 22, QFont.Bold))
        layout.addWidget(header)

        tab_widget = QTabWidget()
        tab_widget.addTab(self._build_slack_tab(), "Slack")
        tab_widget.addTab(self._build_jira_tab(), "Jira")
        tab_widget.addTab(self._build_prometheus_tab(), "Prometheus")
        layout.addWidget(tab_widget)
        layout.addStretch(1)
        return panel

    def _build_slack_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(16)

        self.slack_token_input = QLineEdit()
        self.slack_token_input.setEchoMode(QLineEdit.Password)
        form.addRow("Bot Token", self.slack_token_input)

        self.slack_channel_combo = QComboBox()
        self.slack_channel_combo.addItems([
            "#ops-incident",
            "#sre",
            "#platform-alerts",
        ])
        form.addRow("Channel", self.slack_channel_combo)

        self.slack_workspace_input = QLineEdit()
        self.slack_workspace_input.setPlaceholderText("workspace-name.slack.com")
        form.addRow("Workspace", self.slack_workspace_input)

        button_row = QHBoxLayout()
        self.slack_test_button = QPushButton("Test Connection")
        button_row.addWidget(self.slack_test_button)

        self.slack_save_button = QPushButton("Save Slack Settings")
        button_row.addWidget(self.slack_save_button)

        form.addRow(button_row)
        return tab

    def _build_jira_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(16)

        self.jira_site_input = QLineEdit()
        self.jira_site_input.setPlaceholderText("https://your-company.atlassian.net")
        form.addRow("Site URL", self.jira_site_input)

        self.jira_project_input = QLineEdit()
        self.jira_project_input.setPlaceholderText("OPS")
        form.addRow("Project Key", self.jira_project_input)

        self.jira_email_input = QLineEdit()
        self.jira_email_input.setPlaceholderText("incident-bot@company.com")
        form.addRow("Agent Email", self.jira_email_input)

        self.jira_token_input = QLineEdit()
        self.jira_token_input.setEchoMode(QLineEdit.Password)
        form.addRow("API Token", self.jira_token_input)

        button_row = QHBoxLayout()
        self.jira_test_button = QPushButton("Test Connection")
        button_row.addWidget(self.jira_test_button)

        self.jira_save_button = QPushButton("Save Jira Settings")
        button_row.addWidget(self.jira_save_button)

        form.addRow(button_row)
        return tab

    def _build_prometheus_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(16)

        self.prom_url_input = QLineEdit()
        self.prom_url_input.setPlaceholderText("https://prometheus.company.com")
        form.addRow("Base URL", self.prom_url_input)

        self.prom_http_query_input = QLineEdit()
        self.prom_http_query_input.setPlaceholderText("avg_over_time(http_error_rate[5m])")
        form.addRow("HTTP Error Query", self.prom_http_query_input)

        self.prom_http_threshold_input = QLineEdit()
        self.prom_http_threshold_input.setPlaceholderText("0.05")
        form.addRow("HTTP Threshold", self.prom_http_threshold_input)

        self.prom_cpu_query_input = QLineEdit()
        self.prom_cpu_query_input.setPlaceholderText("max_over_time(cpu_usage[5m])")
        form.addRow("CPU Usage Query", self.prom_cpu_query_input)

        self.prom_cpu_threshold_input = QLineEdit()
        self.prom_cpu_threshold_input.setPlaceholderText("0.80")
        form.addRow("CPU Threshold", self.prom_cpu_threshold_input)

        button_row = QHBoxLayout()
        self.prom_test_button = QPushButton("Test Queries")
        button_row.addWidget(self.prom_test_button)

        self.prom_save_button = QPushButton("Save Prometheus Settings")
        button_row.addWidget(self.prom_save_button)

        form.addRow(button_row)
        return tab

    # endregion

    # region Signal 연결
    def _wire_signals(self) -> None:
        self.trigger_button.clicked.connect(self.trigger_alert_requested.emit)
        self.verify_button.clicked.connect(self.verify_recovery_requested.emit)

        self.slack_test_button.clicked.connect(self.slack_test_requested.emit)
        self.slack_save_button.clicked.connect(self.slack_save_requested.emit)

        self.jira_test_button.clicked.connect(self.jira_test_requested.emit)
        self.jira_save_button.clicked.connect(self.jira_save_requested.emit)

        self.prom_test_button.clicked.connect(self.prometheus_test_requested.emit)
        self.prom_save_button.clicked.connect(self.prometheus_save_requested.emit)

    # endregion

    # region 데이터 접근자
    def get_slack_form(self) -> SlackSettings:
        return SlackSettings(
            token=self.slack_token_input.text().strip(),
            channel=self.slack_channel_combo.currentText(),
            workspace=self.slack_workspace_input.text().strip(),
        )

    def get_jira_form(self) -> JiraSettings:
        return JiraSettings(
            site=self.jira_site_input.text().strip(),
            project=self.jira_project_input.text().strip(),
            email=self.jira_email_input.text().strip(),
            token=self.jira_token_input.text().strip(),
        )

    def get_prometheus_form(self) -> PrometheusSettings:
        return PrometheusSettings(
            url=self.prom_url_input.text().strip(),
            http_query=self.prom_http_query_input.text().strip(),
            http_threshold=self.prom_http_threshold_input.text().strip() or "0.05",
            cpu_query=self.prom_cpu_query_input.text().strip(),
            cpu_threshold=self.prom_cpu_threshold_input.text().strip() or "0.80",
        )

    # endregion

    # region View 업데이트 API
    def prepend_alert_entry(self, entry: str) -> None:
        self.alert_list.insertItem(0, entry)
        self.alert_list.setCurrentRow(0)

    def display_hypotheses(self, lines: List[str]) -> None:
        self.diagnosis_view.setText("\n".join(lines))

    def display_evidence(self, lines: List[str]) -> None:
        self.evidence_view.setText("\n".join(lines))

    def display_actions(self, lines: List[str]) -> None:
        self.action_view.setText("\n".join(lines))

    def append_feed(self, message: str) -> None:
        current = self.system_feed.toPlainText()
        next_text = message if not current else f"{current}\n{message}"
        self.system_feed.setText(next_text)
        self.system_feed.verticalScrollBar().setValue(
            self.system_feed.verticalScrollBar().maximum()
        )

    def set_verify_enabled(self, enabled: bool) -> None:
        self.verify_button.setEnabled(enabled)

    def set_trigger_busy(self, busy: bool, text: str = "Dispatching...") -> None:
        if busy:
            self._trigger_busy_count += 1
            if self._trigger_busy_count == 1:
                self._set_button_busy(self.trigger_button, True, text)
        else:
            self._trigger_busy_count = max(0, self._trigger_busy_count - 1)
            if self._trigger_busy_count == 0:
                self._set_button_busy(self.trigger_button, False)

    def set_verify_busy(self, busy: bool, text: str = "Verifying...") -> None:
        self._set_button_busy(self.verify_button, busy, text)

    def set_slack_test_busy(self, busy: bool, text: str = "Testing...") -> None:
        self._set_button_busy(self.slack_test_button, busy, text)

    def set_jira_test_busy(self, busy: bool, text: str = "Testing...") -> None:
        self._set_button_busy(self.jira_test_button, busy, text)

    def set_prom_test_busy(self, busy: bool, text: str = "Testing...") -> None:
        self._set_button_busy(self.prom_test_button, busy, text)

    def show_information(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def ask_yes_no(self, title: str, message: str) -> bool:
        reply = QMessageBox.question(self, title, message)
        return reply == QMessageBox.Yes

    # endregion

    # region 내부 유틸리티
    def _set_button_busy(self, button: QPushButton, busy: bool, text: str = "") -> None:
        if busy:
            if button.property("_orig_text") is None:
                button.setProperty("_orig_text", button.text())
            if text:
                button.setText(text)
            button.setEnabled(False)
        else:
            original = button.property("_orig_text")
            if original:
                button.setText(original)
            button.setProperty("_orig_text", None)
            button.setEnabled(True)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background-color: #19171D; }
            QLabel#headerLabel { color: #FFFFFF; }
            QLabel#subheaderLabel { color: #B7A0CC; font-size: 16px; }
            QLabel#settingsHeader { color: #FFFFFF; }
            QGroupBox { border: 1px solid #3C2A4D; border-radius: 8px; margin-top: 12px; padding: 12px; color: #F8F6FB; }
            QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 8px 0 8px; }
            QListWidget#alertList { background: #1F1F24; border: 1px solid #4D365C; border-radius: 6px; color: #FFFFFF; padding: 8px; }
            QTextEdit#diagnosisView, QTextEdit#evidenceView, QTextEdit#actionView, QTextEdit#systemFeed {
                background: #1F1F24; border: 1px solid #4D365C; border-radius: 6px; color: #EDEDED; padding: 12px;
            }
            QPushButton { background-color: #4A154B; color: #FFFFFF; padding: 10px 16px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #611F69; }
            QPushButton:disabled { background-color: #2D1330; color: #6E5F78; }
            QLineEdit, QComboBox {
                background: #1F1F24; color: #FFFFFF; border: 1px solid #4D365C; border-radius: 6px; padding: 8px;
            }
            QTabWidget::pane { border: 1px solid #3C2A4D; border-radius: 8px; }
            QTabBar::tab { background: #1F1F24; color: #D8CAE8; padding: 10px 18px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #4A154B; color: #FFFFFF; }
            """
        )

    # endregion
