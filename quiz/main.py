"""
WiFi Quiz application entry point.
"""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QWidget

from pages.dashboard_main import DashboardMain
from host_dashboard import HostDashboard
from player_dashboard import PlayerDashboard


PAGE_DASHBOARD = "dashboard"
PAGE_HOST = "host_dashboard"
PAGE_PLAYER = "player_dashboard"


def apply_light_theme(app: QApplication) -> None:
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except AttributeError:
        pass

    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#F4F6FB"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1F2937"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F0F2F8"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1F2937"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1F2937"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#6C5CE7"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)


class PlaceholderPage(QWidget):
    pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WiFi Quiz")
        self.resize(1180, 760)
        self.setMinimumSize(900, 600)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.pages: dict[str, QWidget] = {}

        self.register_page(PAGE_DASHBOARD, DashboardMain(PAGE_HOST, PAGE_PLAYER))
        self.register_page(PAGE_HOST, HostDashboard(PAGE_DASHBOARD))
        self.register_page(
            PAGE_PLAYER,
            PlayerDashboard(PAGE_DASHBOARD),
        )

        self.show_page(PAGE_DASHBOARD)

    def register_page(self, name: str, widget: QWidget) -> None:
        self.pages[name] = widget
        self.stack.addWidget(widget)

        nav = getattr(widget, "navigate", None)
        if nav is not None:
            nav.connect(self.show_page)

    def show_page(self, name: str) -> None:
        widget = self.pages.get(name)
        if widget is None:
            return

        self.stack.setCurrentWidget(widget)

        hook = getattr(widget, "on_enter", None)
        if callable(hook):
            hook()


def main() -> int:
    app = QApplication(sys.argv)
    apply_light_theme(app)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
