"""
Role selection screen.

The original role cards and overall visual language are preserved:
light background, white cards, purple/green accents and rounded corners.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


EMOJI_FONTS = ["Segoe UI Emoji", "Noto Color Emoji", "Apple Color Emoji"]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class RoleCard(QFrame):
    def __init__(
        self, emoji, title, subtitle, button_text, accent, accent_hover, parent=None
    ):
        super().__init__(parent)
        self._accent = accent
        self._accent_hover = accent_hover

        self.setObjectName("roleCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(30, 30, 60, 40))
        self.setGraphicsEffect(shadow)

        self.emoji_label = QLabel(emoji)
        self.emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setFamilies(EMOJI_FONTS)
        self.emoji_label.setFont(font)

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)

        self.button = QPushButton(button_text)
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.addStretch(2)
        layout.addWidget(self.emoji_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addStretch(2)
        layout.addWidget(self.button)
        self._layout = layout

        self.apply_scale(1.0)

    def apply_scale(self, s: float) -> None:
        f = self.emoji_label.font()
        f.setPointSizeF(64 * s)
        self.emoji_label.setFont(f)

        for label, base, weight in (
            (self.title_label, 22, QFont.Weight.Bold),
            (self.subtitle_label, 11, QFont.Weight.Normal),
        ):
            font = label.font()
            font.setPointSizeF(base * s)
            font.setWeight(weight)
            label.setFont(font)

        bf = self.button.font()
        bf.setPointSizeF(13 * s)
        bf.setWeight(QFont.Weight.DemiBold)
        self.button.setFont(bf)
        self.button.setMinimumHeight(max(36, int(46 * s)))

        pad = int(28 * s)
        self._layout.setContentsMargins(pad, pad, pad, pad)
        self._layout.setSpacing(int(10 * s))

        self.setStyleSheet(f"""
            #roleCard {{
                background: #FFFFFF;
                border: 1px solid #E5E8F0;
                border-radius: {int(28 * s)}px;
            }}
            #roleCard QLabel {{
                background: transparent;
                border: none;
            }}
            #roleCard QPushButton {{
                background: {self._accent};
                color: white;
                border: none;
                border-radius: {int(14 * s)}px;
                padding: 0 {int(20 * s)}px;
            }}
            #roleCard QPushButton:hover {{
                background: {self._accent_hover};
            }}
        """)


class DashboardMain(QWidget):
    navigate = Signal(str)
    NARROW_WIDTH = 720

    def __init__(self, host_page="host_dashboard", player_page="player_dashboard"):
        super().__init__()

        heading = QLabel("Choose your role")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("color: #1F2937; font-weight: 700;")

        self.host_card = RoleCard(
            "👑",
            "Host",
            "Create a quiz, share the room on your WiFi and run the game.",
            "Open Host Dashboard",
            "#6C5CE7",
            "#5B4BD5",
        )
        self.player_card = RoleCard(
            "🎮",
            "Player",
            "Join a quiz hosted on your network and compete for the top spot.",
            "Open Player Dashboard",
            "#00B894",
            "#00A383",
        )

        self.host_card.button.clicked.connect(
            lambda: self.navigate.emit(host_page)
        )
        self.player_card.button.clicked.connect(
            lambda: self.navigate.emit(player_page)
        )

        self.grid = QGridLayout()
        root = QVBoxLayout(self)
        root.addWidget(heading)
        root.addLayout(self.grid, 1)

        self.heading = heading
        self.root = root
        self.vertical = None
        self._rescale()

    def _arrange(self, vertical):
        if vertical == self.vertical:
            return

        self.vertical = vertical
        self.grid.removeWidget(self.host_card)
        self.grid.removeWidget(self.player_card)

        if vertical:
            self.grid.addWidget(self.host_card, 0, 0)
            self.grid.addWidget(self.player_card, 1, 0)
        else:
            self.grid.addWidget(self.host_card, 0, 0)
            self.grid.addWidget(self.player_card, 0, 1)

        for i in range(2):
            self.grid.setRowStretch(i, 1)
            self.grid.setColumnStretch(i, 1)

    def _rescale(self):
        w, h = max(self.width(), 1), max(self.height(), 1)
        vertical = w < self.NARROW_WIDTH
        self._arrange(vertical)

        card_w = w if vertical else w / 2
        card_h = (h - 60) / 2 if vertical else h - 60
        scale = _clamp(min(card_w / 380, card_h / 420), 0.45, 2.4)

        self.grid.setSpacing(int(24 * scale))
        margin = int(28 * scale)
        self.root.setContentsMargins(margin, int(20 * scale), margin, margin)

        font = self.heading.font()
        font.setPointSizeF(24 * scale)
        font.setWeight(QFont.Weight.Bold)
        self.heading.setFont(font)

        self.host_card.apply_scale(scale)
        self.player_card.apply_scale(scale)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()
