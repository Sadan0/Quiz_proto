"""
Host dashboard with LAN discovery, TCP player registration and SQLite storage.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QMessageBox,
    QPushButton,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from quiz_maker import QuizMaker
from host_tools import NetworkSettings, PlayerRanks
from pages.theme import (
    BG, BORDER, MUTED, PRIMARY, PRIMARY_HOVER, SURFACE, TEXT, DANGER
)

from quiz_network import HostNetworkService


class HostDashboard(QWidget):
    navigate = Signal(str)
    players_updated = Signal(list)
    quiz_completed = Signal(list)

    def __init__(self, back_page="dashboard"):
        super().__init__()
        self.back_page = back_page
        self._quitting = False

        self.setStyleSheet(f"background: {BG};")

        self.network = HostNetworkService(
            room_name="WiFi Quiz Room",
            port=5050,
            db_path="wifi_quiz.db",
        )
        self.network.player_registered_callback = self._network_players_changed
        self.network.quiz_complete_callback = self._network_quiz_completed
        self.network.error_callback = self._network_error
        self.network.start()

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(235)
        sidebar.setStyleSheet(f"""
            QFrame#sidebar {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 18px;
            }}
            QLabel#brand {{
                color: {TEXT};
                font-size: 20px;
                font-weight: 800;
            }}
            QLabel#section {{
                color: {MUTED};
                font-size: 11px;
                font-weight: 700;
                padding-left: 4px;
            }}
            QPushButton#nav {{
                text-align: left;
                background: transparent;
                color: {TEXT};
                border: none;
                border-radius: 10px;
                padding: 12px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#nav:hover {{
                background: #F1F0FF;
            }}
            QPushButton#nav[selected="true"] {{
                background: #EEEAFE;
                color: {PRIMARY};
            }}
            QPushButton#quit {{
                text-align: left;
                background: transparent;
                color: {TEXT};
                border: none;
                border-radius: 10px;
                padding: 12px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#quit:hover {{
                background: #FFF1F1;
                color: {DANGER};
            }}
        """)

        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 18, 16, 14)
        side.setSpacing(6)

        brand = QLabel("👑  Host Dashboard")
        brand.setObjectName("brand")
        side.addWidget(brand)
        side.addSpacing(24)

        section = QLabel("WORKSPACE")
        section.setObjectName("section")
        side.addWidget(section)
        side.addSpacing(4)

        self.nav_buttons = []
        self.stack = QStackedWidget()

        self.player_ranks = PlayerRanks()
        self.player_ranks.reset_db_requested.connect(self._reset_database)
        self.player_ranks.remove_player_requested.connect(self._remove_player)

        self.network_settings = NetworkSettings()
        self.quiz_maker = QuizMaker()
        self.quiz_maker.start_quiz_requested.connect(self._start_quiz)

        pages = [
            ("🏆", "Player Ranks", self.player_ranks),
            ("🌐", "Network Settings", self.network_settings),
            ("📝", "Quiz Maker", self.quiz_maker),
        ]

        for icon, title, page in pages:
            button = QPushButton(f"{icon}  {title}")
            button.setObjectName("nav")
            side.addWidget(button)
            self.nav_buttons.append(button)
            self.stack.addWidget(page)

        side.addStretch(1)

        self.network_status = QLabel(f"●  Listening on {self.network.ip}:{self.network.port}")
        self.network_status.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; padding: 4px;"
        )
        self.network_status.setWordWrap(True)
        side.addWidget(self.network_status)

        quit_button = QPushButton("⏻  Quit")
        quit_button.setObjectName("quit")
        quit_button.clicked.connect(self.confirm_quit)
        side.addWidget(quit_button)

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)

        for index, button in enumerate(self.nav_buttons):
            button.clicked.connect(
                lambda checked=False, i=index: self.select_page(i)
            )

        self.players_updated.connect(self.player_ranks.refresh)
        self.quiz_completed.connect(self.player_ranks.refresh)

        self.select_page(0)
        self.player_ranks.refresh(self.network.ranking())

    def _start_quiz(self, quiz):
        try:
            self.network.start_quiz(quiz)
            self.network_status.setText(f"●  Quiz sent to connected players")
            self.network_status.setStyleSheet(f"color: {PRIMARY}; font-size: 11px; padding: 4px;")
        except Exception as exc:
            self._network_error(str(exc))

    def _reset_database(self):
        self.network.reset_database()
        self.player_ranks.refresh(self.network.ranking())
        QMessageBox.information(self, "Database Reset", "The database and player rankings have been cleared.")

    def _remove_player(self, player_id):
        self.network.remove_player(player_id)
        self.player_ranks.refresh(self.network.ranking())

    def _network_players_changed(self, rows):
        self.players_updated.emit(rows)

    def _network_quiz_completed(self, rows):
        self.quiz_completed.emit(rows)

    def _network_error(self, message):
        self.network_status.setText(f"●  Network error: {message}")
        self.network_status.setStyleSheet(
            f"color: {DANGER}; font-size: 11px; padding: 4px;"
        )

    def select_page(self, index: int):
        self.stack.setCurrentIndex(index)

        for i, button in enumerate(self.nav_buttons):
            button.setProperty("selected", i == index)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

        if index == 0:
            self.player_ranks.refresh(self.network.ranking())

    def confirm_quit(self):
        answer = QMessageBox.question(
            self,
            "Quit Host Dashboard",
            "Are you sure you want to quit the host dashboard?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer == QMessageBox.StandardButton.Yes:
            self._quitting = True
            self.network.stop()
            self.navigate.emit(self.back_page)

    def closeEvent(self, event):
        if getattr(self, "_quitting", False):
            self.network.stop()
            event.accept()
            return

        answer = QMessageBox.question(
            self,
            "Exit Host Dashboard",
            "Are you sure you want to exit the host dashboard?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._quitting = True
            self.network.stop()
            event.accept()
        else:
            event.ignore()
