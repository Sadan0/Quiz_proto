"""
Shared visual theme for the host dashboard and its sub-pages.
"""

BG = "#F4F6FB"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F8F9FC"
BORDER = "#E5E8F0"
TEXT = "#1F2937"
MUTED = "#6B7280"
PRIMARY = "#6C5CE7"
PRIMARY_HOVER = "#5B4BD5"
SUCCESS = "#00B894"
DANGER = "#E74C3C"


def panel_style() -> str:
    return f"""
        QFrame#panel {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 18px;
        }}
    """


def input_style() -> str:
    return f"""
        QLineEdit, QSpinBox, QComboBox, QTextEdit, QListWidget {{
            background: {SURFACE};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 10px;
            padding: 8px 10px;
        }}
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
            border: 1px solid {PRIMARY};
        }}
    """


def button_style() -> str:
    return f"""
        QPushButton {{
            background: {SURFACE};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 10px;
            padding: 9px 14px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {SURFACE_ALT};
            border-color: #D2D6E1;
        }}
    """
