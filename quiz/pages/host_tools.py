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
)

from pages.theme import BORDER, MUTED, PRIMARY, SURFACE, TEXT, panel_style, input_style


class PlayerRanks(QWidget):
    """Live ranking table backed by the host SQLite database."""

    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Player Ranks")
        title.setStyleSheet(f"font-size: 25px; font-weight: 800; color: {TEXT};")

        subtitle = QLabel("Live ranking table for players in the current quiz room.")
        subtitle.setStyleSheet(f"color: {MUTED};")

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Rank", "Player", "IP Address", "Score", "Correct", "Status"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
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
        root.addSpacing(18)
        root.addWidget(self.table, 1)

        self.refresh([])

    def refresh(self, rows):
        self.table.setRowCount(0)

        for rank, player in enumerate(rows, start=1):
            row = self.table.rowCount()
            self.table.insertRow(row)

            values = [
                str(rank),
                player.get("name", "Player"),
                player.get("ip", "—"),
                str(player.get("score", 0)),
                f'{player.get("correct", 0)}/{player.get("total", 0)}',
                "Connected" if player.get("connected") else "Offline",
            ]

            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))


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
