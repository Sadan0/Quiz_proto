"""
Streamlined Google-Forms-style Quiz Maker with functional previewing and sleek controls.
"""
import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pages.theme import BORDER, MUTED, PRIMARY, PRIMARY_HOVER, SURFACE, TEXT


TYPE_LABELS = {
    "Multiple choice": "mcq",
    "Short answer": "text_input",
    "Checkboxes": "checkbox",
    "Drag and drop": "drag_drop",
    "Match the following": "match",
}


def secondary_button(button):
    button.setStyleSheet(f"""
        QPushButton {{
            background: #FFFFFF;
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 9px;
            padding: 8px 12px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: #F6F5FF;
            border-color: #D8D3FA;
        }}
    """)


def primary_button(button):
    button.setStyleSheet(f"""
        QPushButton {{
            background: {PRIMARY};
            color: white;
            border: none;
            border-radius: 9px;
            padding: 9px 15px;
            font-weight: 700;
        }}
        QPushButton:hover {{
            background: {PRIMARY_HOVER};
        }}
    """)


class SleekNumberInput(QFrame):
    """Sleek replacement for standard QSpinBox with clean + / - buttons."""
    valueChanged = Signal(int)

    def __init__(self, label_text, value=3, min_val=1, max_val=20, parent=None):
        super().__init__(parent)
        self.value = value
        self.min_val = min_val
        self.max_val = max_val

        self.setStyleSheet(f"""
            QFrame {{
                background: #F9FAFB;
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            QLabel {{
                color: {TEXT};
                font-weight: 600;
                font-size: 13px;
                border: none;
            }}
            QPushButton {{
                background: #FFFFFF;
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }}
            QPushButton:hover {{
                background: #EEECFE;
                border-color: {PRIMARY};
                color: {PRIMARY};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        lbl = QLabel(label_text)
        
        btn_minus = QPushButton("−")
        btn_minus.clicked.connect(self.decrement)

        self.val_label = QLabel(str(self.value))
        self.val_label.setStyleSheet("font-weight: 700; padding: 0 4px;")

        btn_plus = QPushButton("+")
        btn_plus.clicked.connect(self.increment)

        layout.addWidget(lbl)
        layout.addWidget(btn_minus)
        layout.addWidget(self.val_label)
        layout.addWidget(btn_plus)

    def increment(self):
        if self.value < self.max_val:
            self.value += 1
            self.val_label.setText(str(self.value))
            self.valueChanged.emit(self.value)

    def decrement(self):
        if self.value > self.min_val:
            self.value -= 1
            self.val_label.setText(str(self.value))
            self.valueChanged.emit(self.value)

    def getValue(self):
        return self.value

    def setValue(self, val):
        self.value = max(self.min_val, min(self.max_val, val))
        self.val_label.setText(str(self.value))


class ImageButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__("Add image", parent)
        self.path = ""
        secondary_button(self)
        self.clicked.connect(self.choose)

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        )
        if path:
            self.path = path
            self.setText("Image added ✓")

    def clear_image(self):
        self.path = ""
        self.setText("Add image")


class EditComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QComboBox {{
                background: #FFFFFF;
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 7px 30px 7px 10px;
                min-width: 145px;
            }}
            QComboBox:hover {{
                border-color: #D8D3FA;
            }}
            QComboBox:focus {{
                border: 1px solid {PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 0px;
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
            }}
        """)


class OptionRow(QFrame):
    changed = Signal()
    deleted = Signal(object)

    def __init__(self, number, parent=None):
        super().__init__(parent)
        self.setObjectName("optionRow")
        self.setStyleSheet(f"""
            QFrame#optionRow {{
                background: #FFFFFF;
                border: none;
            }}
            QLineEdit {{
                background: #FFFFFF;
                border: none;
                border-bottom: 1px solid {BORDER};
                padding: 8px 4px;
                color: {TEXT};
            }}
            QLineEdit:focus {{
                border-bottom: 2px solid {PRIMARY};
            }}
            QCheckBox {{
                color: {TEXT};
            }}
        """)

        self.text = QLineEdit()
        self.text.setPlaceholderText(f"Option {number}")

        self.correct = QCheckBox("Correct")
        self.image = ImageButton()

        delete = QPushButton("×")
        delete.setToolTip("Remove option")
        delete.setFixedWidth(30)
        delete.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #9CA3AF;
                border: none;
                font-size: 18px;
            }
            QPushButton:hover { color: #E74C3C; }
        """)
        delete.clicked.connect(self.on_delete)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.image)
        layout.addWidget(self.correct)
        layout.addWidget(delete)

        self.text.textChanged.connect(self.changed.emit)
        self.correct.stateChanged.connect(self.changed.emit)

    def on_delete(self):
        self.deleted.emit(self)
        self.deleteLater()

    def to_dict(self):
        return {
            "text": self.text.text().strip(),
            "image": self.image.path or None,
            "correct": self.correct.isChecked(),
        }


class DragRow(QFrame):
    deleted = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: #FFFFFF;
                border-bottom: 1px solid {BORDER};
            }}
            QLineEdit {{
                border: none;
                padding: 7px 3px;
                color: {TEXT};
            }}
        """)

        self.text = QLineEdit()
        self.text.setPlaceholderText("Draggable item")

        self.target = QLineEdit()
        self.target.setPlaceholderText("Target / category")

        self.image = ImageButton()

        delete = QPushButton("×")
        delete.setToolTip("Remove item")
        delete.setFixedWidth(30)
        delete.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #9CA3AF;
                border: none;
                font-size: 18px;
            }
            QPushButton:hover { color: #E74C3C; }
        """)
        delete.clicked.connect(self.on_delete)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.image)
        layout.addWidget(self.target, 1)
        layout.addWidget(delete)

    def on_delete(self):
        self.deleted.emit(self)
        self.deleteLater()

    def to_dict(self):
        return {
            "text": self.text.text().strip(),
            "image": self.image.path or None,
            "target": self.target.text().strip(),
        }


class MatchCell(QFrame):
    def __init__(self, row, col, parent=None):
        super().__init__(parent)
        self.setObjectName("matchCell")
        self.setStyleSheet(f"""
            QFrame#matchCell {{
                background: #FFFFFF;
                border: 1px solid {BORDER};
                border-radius: 9px;
            }}
            QLineEdit {{
                border: none;
                background: transparent;
                padding: 7px;
                color: {TEXT};
            }}
        """)

        self.text = QLineEdit()
        self.text.setPlaceholderText(f"R{row + 1}, C{col + 1}")
        self.image = ImageButton()
        self.image.setText("Img")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(self.text)
        layout.addWidget(self.image)

    def to_dict(self):
        return {
            "text": self.text.text().strip(),
            "image": self.image.path or None,
        }


class QuestionCard(QFrame):
    duplicate_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, number, question=None, parent=None):
        super().__init__(parent)
        self.number = number
        self.question = question or self.default_question()

        self.setObjectName("questionCard")
        self.setStyleSheet(f"""
            QFrame#questionCard {{
                background: #FFFFFF;
                border: 1px solid {BORDER};
                border-radius: 14px;
            }}
            QLabel#number {{
                color: {MUTED};
                font-weight: 700;
            }}
            QLineEdit#questionTitle {{
                background: #FFFFFF;
                color: {TEXT};
                border: none;
                border-bottom: 1px solid {BORDER};
                font-size: 18px;
                padding: 8px 2px;
            }}
            QLineEdit#questionTitle:focus {{
                border-bottom: 2px solid {PRIMARY};
            }}
            QTextEdit {{
                background: #FFFFFF;
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 9px;
                padding: 8px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        number_label = QLabel(f"Question {number}")
        number_label.setObjectName("number")

        self.type_combo = EditComboBox()
        self.type_combo.addItems(TYPE_LABELS.keys())
        self.type_combo.setCurrentText(self.label_for_type(self.question["type"]))
        self.type_combo.currentTextChanged.connect(self.type_changed)

        header.addWidget(number_label)
        header.addStretch()
        header.addWidget(self.type_combo)

        root.addLayout(header)

        self.prompt = QLineEdit()
        self.prompt.setObjectName("questionTitle")
        self.prompt.setPlaceholderText("Question")
        self.prompt.setText(self.question.get("question", ""))
        root.addWidget(self.prompt)

        media_row = QHBoxLayout()
        self.question_image = ImageButton()
        if self.question.get("question_image"):
            self.question_image.path = self.question["question_image"]
            self.question_image.setText("Image added ✓")
        media_row.addWidget(self.question_image)
        media_row.addStretch()
        root.addLayout(media_row)

        self.editor_host = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_host)
        self.editor_layout.setContentsMargins(0, 4, 0, 0)
        root.addWidget(self.editor_host)

        footer = QHBoxLayout()

        self.required = QCheckBox("Required")
        self.required.setChecked(self.question.get("required", False))

        # Binary points logic (Right/Wrong toggle)
        self.grading_toggle = QCheckBox("Right / Wrong (1 pt)")
        self.grading_toggle.setChecked(self.question.get("points", 1) > 0)

        duplicate = QPushButton("Duplicate")
        secondary_button(duplicate)
        duplicate.clicked.connect(lambda: self.duplicate_requested.emit(self))

        delete = QPushButton("Delete")
        secondary_button(delete)
        delete.clicked.connect(lambda: self.delete_requested.emit(self))

        footer.addWidget(self.required)
        footer.addSpacing(12)
        footer.addWidget(self.grading_toggle)
        footer.addStretch()
        footer.addWidget(duplicate)
        footer.addWidget(delete)

        root.addLayout(footer)

        self.option_rows = []
        self.drag_items = []
        self.build_editor()

    @staticmethod
    def default_question():
        return {
            "type": "mcq",
            "question": "",
            "question_image": None,
            "required": False,
            "points": 1,
            "options": [
                {"text": "", "image": None, "correct": False}
                for _ in range(4)
            ],
        }

    @staticmethod
    def label_for_type(qtype):
        for label, value in TYPE_LABELS.items():
            if value == qtype:
                return label
        return "Multiple choice"

    def type_changed(self, label):
        self.save()
        self.question["type"] = TYPE_LABELS[label]
        self.build_editor()

    def clear_editor(self):
        while self.editor_layout.count():
            item = self.editor_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Clean up nested layouts safely
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

    def build_editor(self):
        self.clear_editor()
        qtype = self.question["type"]

        if qtype in ("mcq", "checkbox"):
            self.build_options()
        elif qtype == "text_input":
            self.build_short_answer()
        elif qtype == "drag_drop":
            self.build_drag_drop()
        elif qtype == "match":
            self.build_match()

    def build_options(self):
        self.options_host = QVBoxLayout()
        self.option_rows = []

        options = self.question.get("options") or [
            {"text": "", "image": None, "correct": False}
            for _ in range(4)
        ]

        for option in options:
            self.add_option_row(option)

        add = QPushButton("+ Add option")
        secondary_button(add)
        add.clicked.connect(lambda: self.add_option_row())
        self.options_host.addWidget(add)

        wrapper = QWidget()
        wrapper.setLayout(self.options_host)
        self.editor_layout.addWidget(wrapper)

    def add_option_row(self, data=None):
        row = OptionRow(len(self.option_rows) + 1)
        if data:
            row.text.setText(data.get("text", ""))
            if data.get("image"):
                row.image.path = data["image"]
                row.image.setText("Image added ✓")
            row.correct.setChecked(data.get("correct", False))

        row.deleted.connect(self.remove_option_row)
        self.option_rows.append(row)
        self.options_host.insertWidget(
            max(0, self.options_host.count() - 1), row
        )

    def remove_option_row(self, row):
        if row in self.option_rows:
            self.option_rows.remove(row)

    def build_short_answer(self):
        self.accepted = QTextEdit()
        self.accepted.setPlaceholderText(
            "Accepted answers — one per line\n"
            "Example: Paris"
        )
        self.accepted.setFixedHeight(100)
        self.accepted.setPlainText(
            "\n".join(self.question.get("accepted_answers", []))
        )

        hint = QLabel("Short answer")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 12px;")

        self.editor_layout.addWidget(hint)
        self.editor_layout.addWidget(self.accepted)

    def build_drag_drop(self):
        hint = QLabel("Define each draggable item and the target it belongs to.")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self.editor_layout.addWidget(hint)

        self.drag_rows_layout = QVBoxLayout()
        self.drag_items = []

        items = self.question.get("items") or [
            {"text": "", "image": None, "target": ""}
            for _ in range(3)
        ]

        for item in items:
            self.add_drag_row(item)

        add = QPushButton("+ Add item")
        secondary_button(add)
        add.clicked.connect(lambda: self.add_drag_row())
        self.drag_rows_layout.addWidget(add)

        wrapper = QWidget()
        wrapper.setLayout(self.drag_rows_layout)
        self.editor_layout.addWidget(wrapper)

    def add_drag_row(self, data=None):
        row = DragRow()
        if data:
            row.text.setText(data.get("text", ""))
            row.target.setText(data.get("target", ""))
            if data.get("image"):
                row.image.path = data["image"]
                row.image.setText("Image added ✓")

        row.deleted.connect(self.remove_drag_row)
        self.drag_items.append(row)
        self.drag_rows_layout.insertWidget(
            max(0, self.drag_rows_layout.count() - 1), row
        )

    def remove_drag_row(self, row):
        if row in self.drag_items:
            self.drag_items.remove(row)

    def build_match(self):
        top = QHBoxLayout()

        rows_val = max(1, self.question.get("rows", 3))
        cols_val = max(1, self.question.get("columns", 2))

        self.rows_input = SleekNumberInput("Rows", value=rows_val, min_val=1, max_val=20)
        self.cols_input = SleekNumberInput("Columns", value=cols_val, min_val=1, max_val=10)

        self.rows_input.valueChanged.connect(self.rebuild_match)
        self.cols_input.valueChanged.connect(self.rebuild_match)

        top.addWidget(self.rows_input)
        top.addWidget(self.cols_input)
        top.addStretch()

        self.editor_layout.addLayout(top)

        self.match_grid_host = QWidget()
        self.match_grid = QGridLayout(self.match_grid_host)
        self.match_grid.setSpacing(8)
        self.editor_layout.addWidget(self.match_grid_host)

        self.populate_match()

    def rebuild_match(self):
        self.save()
        self.question["rows"] = self.rows_input.getValue()
        self.question["columns"] = self.cols_input.getValue()
        self.populate_match()

    def populate_match(self):
        while self.match_grid.count():
            item = self.match_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = self.rows_input.getValue()
        cols = self.cols_input.getValue()
        old = self.question.get("pairs", [])

        self.match_cells = []

        for r in range(rows):
            row_cells = []
            for c in range(cols):
                cell = MatchCell(r, c)
                if r < len(old) and c < len(old[r]):
                    data = old[r][c]
                    cell.text.setText(data.get("text", ""))
                    if data.get("image"):
                        cell.image.path = data["image"]
                        cell.image.setText("Img ✓")

                self.match_grid.addWidget(cell, r, c)
                row_cells.append(cell)
            self.match_cells.append(row_cells)

    def save(self):
        q = self.question
        q["question"] = self.prompt.text().strip()
        q["question_image"] = self.question_image.path or None
        q["required"] = self.required.isChecked()
        q["points"] = 1 if self.grading_toggle.isChecked() else 0

        if q["type"] in ("mcq", "checkbox"):
            q["options"] = [row.to_dict() for row in self.option_rows]

        elif q["type"] == "text_input":
            q["accepted_answers"] = [
                line.strip()
                for line in self.accepted.toPlainText().splitlines()
                if line.strip()
            ]

        elif q["type"] == "drag_drop":
            q["items"] = [item.to_dict() for item in self.drag_items]

        elif q["type"] == "match":
            q["rows"] = self.rows_input.getValue()
            q["columns"] = self.cols_input.getValue()
            q["pairs"] = [
                [cell.to_dict() for cell in row]
                for row in self.match_cells
            ]

        return q


class QuizPreviewDialog(QDialog):
    def __init__(self, quiz_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quiz Preview")
        self.resize(750, 700)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel(quiz_data.get("title", "Untitled quiz"))
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(20)

        for i, q in enumerate(quiz_data.get("questions", []), start=1):
            q_box = QFrame()
            q_box.setStyleSheet(f"QFrame {{ background: white; border: 1px solid {BORDER}; border-radius: 8px; padding: 12px; }}")
            q_layout = QVBoxLayout(q_box)

            req_str = " *" if q.get("required") else ""
            pts_str = f" ({q.get('points', 0)} pt)"
            header = QLabel(f"Q{i}. {q.get('question', '')}{req_str}{pts_str}")
            header.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            q_layout.addWidget(header)

            if q.get("question_image"):
                image_path = Path(q["question_image"])
                if image_path.exists():
                    from PySide6.QtGui import QPixmap
                    img_lbl = QLabel()
                    pixmap = QPixmap(str(image_path))
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(620, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        img_lbl.setPixmap(pixmap)
                        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        img_lbl.setStyleSheet(f"border:1px solid {BORDER};border-radius:10px;background:#FFFFFF;padding:6px;")
                        q_layout.addWidget(img_lbl)
                else:
                    missing = QLabel(f"Image not found: {image_path.name}")
                    missing.setStyleSheet("color:#9CA3AF;")
                    q_layout.addWidget(missing)

            qtype = q.get("type")

            if qtype == "mcq":
                for opt in q.get("options", []):
                    rb = QRadioButton(opt.get("text") or "Option")
                    q_layout.addWidget(rb)
                    if opt.get("image") and Path(opt["image"]).exists():
                        pixmap = QPixmap(opt["image"])
                        if not pixmap.isNull():
                            img = QLabel()
                            img.setPixmap(pixmap.scaled(420, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                            q_layout.addWidget(img)

            elif qtype == "checkbox":
                for opt in q.get("options", []):
                    cb = QCheckBox(opt.get("text") or "Option")
                    q_layout.addWidget(cb)
                    if opt.get("image") and Path(opt["image"]).exists():
                        pixmap = QPixmap(opt["image"])
                        if not pixmap.isNull():
                            img = QLabel()
                            img.setPixmap(pixmap.scaled(420, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                            q_layout.addWidget(img)

            elif qtype == "text_input":
                inp = QLineEdit()
                inp.setPlaceholderText("Your answer...")
                q_layout.addWidget(inp)

            elif qtype == "drag_drop":
                for item in q.get("items", []):
                    row = QHBoxLayout()
                    row.addWidget(QLabel(item.get("text", "Draggable Item")))
                    combo = QComboBox()
                    combo.addItems([it.get("target", "Target") for it in q.get("items", []) if it.get("target")])
                    row.addWidget(combo)
                    q_layout.addLayout(row)

            elif qtype == "match":
                grid = QGridLayout()
                for r, row in enumerate(q.get("pairs", [])):
                    for c, cell in enumerate(row):
                        grid.addWidget(QLabel(cell.get("text", f"[{r},{c}]")), r, c)
                q_layout.addLayout(grid)

            scroll_layout.addWidget(q_box)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        close_btn = QPushButton("Close Preview")
        secondary_button(close_btn)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


class QuizMaker(QWidget):
    start_quiz_requested = Signal(dict)

    def __init__(self):
        super().__init__()

        self.questions = []
        self.cards = []

        self.setStyleSheet(f"""
            QWidget {{
                color: {TEXT};
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QFrame()
        top.setStyleSheet(f"""
            QFrame {{
                background: #FFFFFF;
                border-bottom: 1px solid {BORDER};
            }}
        """)

        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(22, 14, 22, 14)

        title = QLabel("Quiz Maker")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: 800; color: {TEXT};"
        )

        self.quiz_title = QLineEdit("Untitled quiz")
        self.quiz_title.setPlaceholderText("Quiz title")
        self.quiz_title.setStyleSheet(f"""
            QLineEdit {{
                border: none;
                border-bottom: 1px solid {BORDER};
                font-size: 16px;
                padding: 5px 2px;
            }}
            QLineEdit:focus {{
                border-bottom: 2px solid {PRIMARY};
            }}
        """)

        preview = QPushButton("Preview")
        secondary_button(preview)
        preview.clicked.connect(self.show_preview)

        load = QPushButton("Load JSON")
        secondary_button(load)
        load.clicked.connect(self.import_json)

        save = QPushButton("Save JSON")
        primary_button(save)
        save.clicked.connect(self.export_json)

        start = QPushButton("Start Quiz")
        primary_button(start)
        start.clicked.connect(self.start_quiz)

        top_layout.addWidget(title)
        top_layout.addSpacing(20)
        top_layout.addWidget(self.quiz_title, 1)
        top_layout.addStretch()
        top_layout.addWidget(preview)
        top_layout.addWidget(load)
        top_layout.addWidget(save)
        top_layout.addWidget(start)

        root.addWidget(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        canvas = QWidget()
        canvas.setStyleSheet("background: #F4F6FB;")

        self.cards_layout = QVBoxLayout(canvas)
        self.cards_layout.setContentsMargins(0, 24, 0, 32)
        self.cards_layout.setSpacing(14)

        self.cards_container = QWidget()
        self.cards_container.setMaximumWidth(820)

        container_layout = QVBoxLayout(self.cards_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(14)

        self.question_area = QVBoxLayout()
        self.question_area.setSpacing(14)
        container_layout.addLayout(self.question_area)

        add = QPushButton("+ Add question")
        add.setMinimumHeight(42)
        primary_button(add)
        add.clicked.connect(self.add_question)
        container_layout.addWidget(add)

        self.add_button = add

        self.cards_layout.addWidget(
            self.cards_container,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )
        self.cards_layout.addStretch()

        scroll.setWidget(canvas)
        root.addWidget(scroll, 1)

        self.add_question()

    def sync_data(self):
        self.questions = [card.save() for card in self.cards]

    def add_question(self, data=None):
        q = data or QuestionCard.default_question()
        self.questions.append(q)

        card = QuestionCard(len(self.questions), q)
        card.duplicate_requested.connect(self.duplicate_question)
        card.delete_requested.connect(self.delete_question)

        self.cards.append(card)
        self.question_area.addWidget(card)
        card.prompt.setFocus()

    def duplicate_question(self, card):
        self.sync_data()
        index = self.cards.index(card)

        copied = json.loads(json.dumps(self.questions[index]))
        self.questions.insert(index + 1, copied)

        self.rebuild_cards()

    def delete_question(self, card):
        if len(self.cards) == 1:
            QMessageBox.information(
                self,
                "Quiz needs a question",
                "Keep at least one question in the quiz.",
            )
            return

        self.sync_data()
        index = self.cards.index(card)
        self.cards.pop(index)
        self.questions.pop(index)

        self.rebuild_cards()

    def rebuild_cards(self):
        while self.question_area.count():
            item = self.question_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.cards = []

        for index, question in enumerate(self.questions, start=1):
            card = QuestionCard(index, question)
            card.duplicate_requested.connect(self.duplicate_question)
            card.delete_requested.connect(self.delete_question)
            self.cards.append(card)
            self.question_area.addWidget(card)

    def build_quiz_data(self):
        self.sync_data()
        return {
            "version": 1,
            "quiz": {
                "title": self.quiz_title.text().strip() or "Untitled quiz",
                "questions": self.questions,
            },
        }

    def start_quiz(self):
        data = self.build_quiz_data()
        self.start_quiz_requested.emit(data["quiz"])

    def show_preview(self):
        self.sync_data()
        quiz_data = {
            "title": self.quiz_title.text().strip() or "Untitled quiz",
            "questions": self.questions,
        }
        dialog = QuizPreviewDialog(quiz_data, self)
        dialog.exec()

    def import_json(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load quiz JSON",
            "",
            "JSON files (*.json)",
        )

        if not filename:
            return

        try:
            raw = Path(filename).read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Load failed", f"Could not load the quiz JSON.\n\n{exc}")
            return

        quiz = data.get("quiz", data) if isinstance(data, dict) else None
        if not isinstance(quiz, dict):
            QMessageBox.warning(self, "Invalid quiz", "The selected JSON does not contain a valid quiz object.")
            return

        questions = quiz.get("questions")
        if not isinstance(questions, list) or not questions:
            QMessageBox.warning(self, "Invalid quiz", "The selected JSON does not contain any questions.")
            return

        normalized = []
        for index, question in enumerate(questions):
            if not isinstance(question, dict):
                continue
            q = json.loads(json.dumps(question))
            q.setdefault("id", f"q{index + 1}")
            q.setdefault("type", "mcq")
            q.setdefault("question", "")
            normalized.append(q)

        if not normalized:
            QMessageBox.warning(self, "Invalid quiz", "No valid questions were found in the JSON file.")
            return

        self.quiz_title.setText(quiz.get("title", "Untitled quiz"))
        self.questions = normalized
        self.rebuild_cards()

        QMessageBox.information(
            self,
            "Quiz loaded",
            f"Loaded {len(normalized)} question(s) from:\n{filename}",
        )

    def export_json(self):
        self.sync_data()

        data = {
            "version": 1,
            "quiz": {
                "title": self.quiz_title.text().strip() or "Untitled quiz",
                "questions": self.questions,
            },
        }

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save quiz JSON",
            "quiz.json",
            "JSON files (*.json)",
        )

        if not filename:
            return

        try:
            Path(filename).write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return

        QMessageBox.information(
            self,
            "Saved",
            f"Quiz JSON saved to:\n{filename}",
        )
