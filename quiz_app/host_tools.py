"""
Small host-dashboard pages other than Quiz Maker.
"""
import socket

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from pages.theme import BORDER, MUTED, PRIMARY, SURFACE, TEXT, panel_style, input_style


class PlayerRanks(QWidget):
    """Live ranking table backed by the host SQLite database with reset and removal tools."""
    reset_db_requested = Signal()
    remove_player_requested = Signal(str)

    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Player Ranks")
        title.setStyleSheet(f"font-size: 25px; font-weight: 800; color: {TEXT};")

        subtitle = QLabel("Live ranking table for players in the current quiz room (scored out of 100 pts per question, tie-broken by time).")
        subtitle.setStyleSheet(f"color: {MUTED};")

        actions_layout = QHBoxLayout()
        self.remove_btn = QPushButton("Remove Selected Player")
        self.remove_btn.setStyleSheet(f"background: #FFF1F1; color: #E74C3C; border: 1px solid #F0CACA; border-radius: 8px; padding: 6px 12px; font-weight: 600;")
        self.remove_btn.clicked.connect(self._on_remove_clicked)

        self.reset_btn = QPushButton("Reset Database / Clear Ranks")
        self.reset_btn.setStyleSheet(f"background: #1F2937; color: white; border: none; border-radius: 8px; padding: 6px 12px; font-weight: 600;")
        self.reset_btn.clicked.connect(self._on_reset_clicked)

        actions_layout.addWidget(self.remove_btn)
        actions_layout.addWidget(self.reset_btn)
        actions_layout.addStretch()

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Rank", "Player", "IP Address", "Score", "Time", "Status"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 14px;
                gridline-color: {BORDER};
            }}
            QHeaderView::section {{
                background: #F8F9FC;
                color: {TEXT};
                border: none;
                padding: 10px;
                font-weight: 700;
            }}
        """)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(10)
        root.addLayout(actions_layout)
        root.addSpacing(14)
        root.addWidget(self.table, 1)

        self._rows_data = []
        self.refresh([])

    def refresh(self, rows):
        self._rows_data = rows
        self.table.setRowCount(0)

        for rank, player in enumerate(rows, start=1):
            row = self.table.rowCount()
            self.table.insertRow(row)

            time_taken = f"{player.get('score_time', 0):.1f}s" if player.get("completed") else "—"

            values = [
                str(rank),
                player.get("name", "Player"),
                player.get("ip", "—"),
                f"{player.get('score', 0)} pts",
                time_taken,
                "Connected" if player.get("connected") else "Offline",
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, player.get("id"))
                self.table.setItem(row, column, item)

    def _on_remove_clicked(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "No selection", "Please select a player row to remove.")
            return
        row = selected_rows[0].row()
        item = self.table.item(row, 0)
        player_id = item.data(Qt.ItemDataRole.UserRole)
        player_name = self.table.item(row, 1).text()

        answer = QMessageBox.question(
            self,
            "Remove Player",
            f"Are you sure you want to remove player '{player_name}' from the ranks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes and player_id:
            self.remove_player_requested.emit(player_id)

    def _on_reset_clicked(self):
        answer = QMessageBox.question(
            self,
            "Reset Database",
            "Are you sure you want to completely clear and reset the quiz database and player ranks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.reset_db_requested.emit()


class NetworkSettings(QWidget):
    """Network settings page for the host."""

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Network Settings")
        title.setStyleSheet(f"font-size: 25px; font-weight: 800; color: {TEXT};")

        panel = QFrame()
        panel.setObjectName("panel")
        panel.setStyleSheet(panel_style())

        form = QFormLayout(panel)
        form.setContentsMargins(20, 20, 20, 20)
        form.setVerticalSpacing(14)

        self.room_name = QLineEdit("WiFi Quiz Room")
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(5050)

        self.ip = QLineEdit()
        self.ip.setReadOnly(True)
        self.ip.setText(self.detect_ip())

        save = QPushButton("Save Network Settings")
        save.setStyleSheet(
            f"background: {PRIMARY}; color: white; border: none; "
            "border-radius: 10px; padding: 10px 14px; font-weight: 700;"
        )

        form.addRow("Room name", self.room_name)
        form.addRow("Host IP", self.ip)
        form.addRow("Port", self.port)
        form.addRow("", save)

        root.addWidget(title)
        root.addSpacing(18)
        root.addWidget(panel)
        root.addStretch()

    @staticmethod
    def detect_ip():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
            return ip
        except OSError:
            return "127.0.0.1"
