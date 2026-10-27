"""
Streamlined Google-Forms-style Quiz Maker with functional previewing, saving, loading, and sleek controls.
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
    QVBoxLayout,
    QWidget,
)

from pages.theme import BORDER, MUTED, PRIMARY, PRIMARY_HOVER, SURFACE, TEXT

TYPE_LABELS = {
    "Multiple choice": "mcq",
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
        """)


class OptionRow(QFrame):
    changed = Signal()
    deleted = Signal(object)

    def __init__(self, number, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
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
        """)

        self.text = QLineEdit()
        self.text.setPlaceholderText(f"Option {number}")
        self.correct = QCheckBox("Correct")
        self.image = ImageButton()

        delete = QPushButton("×")
        delete.setFixedWidth(30)
        delete.setStyleSheet(
            "QPushButton { background: transparent; color: #9CA3AF; border: none; font-size: 18px; } QPushButton:hover { color: #E74C3C; }"
        )
        delete.clicked.connect(self.on_delete)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.image)
        layout.addWidget(self.correct)
        layout.addWidget(delete)

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
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 6px;
                margin-bottom: 6px;
            }}
            QLineEdit {{
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px;
                color: {TEXT};
                background: #F9FAFB;
            }}
        """)

        self.text = QLineEdit()
        self.text.setPlaceholderText("Draggable Item / Source")

        self.target = QLineEdit()
        self.target.setPlaceholderText("Correct Target / Zone")

        self.image = ImageButton()

        delete = QPushButton("×")
        delete.setFixedWidth(30)
        delete.setStyleSheet(
            "QPushButton { background: transparent; color: #9CA3AF; border: none; font-size: 18px; } QPushButton:hover { color: #E74C3C; }"
        )
        delete.clicked.connect(self.on_delete)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
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


class MatchPairRow(QFrame):
    deleted = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: #FFFFFF;
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 6px;
                margin-bottom: 6px;
            }}
            QLineEdit {{
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px;
                color: {TEXT};
                background: #F9FAFB;
            }}
        """)

        self.left_text = QLineEdit()
        self.left_text.setPlaceholderText("Left Item")
        self.left_image = ImageButton()
        self.left_image.setText("Left Img")

        self.right_text = QLineEdit()
        self.right_text.setPlaceholderText("Correct Matching Right Item")
        self.right_image = ImageButton()
        self.right_image.setText("Right Img")

        delete = QPushButton("×")
        delete.setFixedWidth(30)
        delete.setStyleSheet(
            "QPushButton { background: transparent; color: #9CA3AF; border: none; font-size: 18px; } QPushButton:hover { color: #E74C3C; }"
        )
        delete.clicked.connect(self.on_delete)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        layout.addWidget(self.left_text, 1)
        layout.addWidget(self.left_image)
        layout.addWidget(QLabel("⟷"))
        layout.addWidget(self.right_text, 1)
        layout.addWidget(self.right_image)
        layout.addWidget(delete)

    def on_delete(self):
        self.deleted.emit(self)
        self.deleteLater()

    def to_dict(self):
        return {
            "left": {
                "text": self.left_text.text().strip(),
                "image": self.left_image.path or None,
            },
            "right": {
                "text": self.right_text.text().strip(),
                "image": self.right_image.path or None,
            },
        }


class QuestionCard(QFrame):
    duplicate_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, number, question=None, parent=None):
        super().__init__(parent)
        self.number = number
        self.question = question or self.default_question()

        self.setStyleSheet(f"""
            QFrame {{
                background: #FFFFFF;
                border: 1px solid {BORDER};
                border-radius: 14px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        number_label = QLabel(f"Question {number}")
        number_label.setStyleSheet(f"color: {MUTED}; font-weight: 700;")

        self.type_combo = EditComboBox()
        self.type_combo.addItems(TYPE_LABELS.keys())
        self.type_combo.setCurrentText(self.label_for_type(self.question["type"]))
        self.type_combo.currentTextChanged.connect(self.type_changed)

        header.addWidget(number_label)
        header.addStretch()
        header.addWidget(self.type_combo)
        root.addLayout(header)

        self.prompt = QLineEdit()
        self.prompt.setPlaceholderText("Question prompt")
        self.prompt.setText(self.question.get("question", ""))
        self.prompt.setStyleSheet(
            f"border: none; border-bottom: 1px solid {BORDER}; font-size: 18px; padding: 8px 2px; color: {TEXT};"
        )
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
        duplicate = QPushButton("Duplicate")
        secondary_button(duplicate)
        duplicate.clicked.connect(lambda: self.duplicate_requested.emit(self))

        delete = QPushButton("Delete")
        secondary_button(delete)
        delete.clicked.connect(lambda: self.delete_requested.emit(self))

        footer.addStretch()
        footer.addWidget(duplicate)
        footer.addWidget(delete)
        root.addLayout(footer)

        self.option_rows = []
        self.drag_rows = []
        self.match_rows = []
        self.build_editor()

    @staticmethod
    def default_question():
        return {
            "type": "mcq",
            "question": "",
            "question_image": None,
            "points": 100,
            "options": [{"text": "", "image": None, "correct": False} for _ in range(4)],
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
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

    def build_editor(self):
        self.clear_editor()
        qtype = self.question["type"]

        if qtype in ("mcq", "checkbox"):
            self.build_options()
        elif qtype == "drag_drop":
            self.build_drag_drop()
        elif qtype == "match":
            self.build_match()

    def build_options(self):
        self.options_host = QVBoxLayout()
        self.option_rows = []
        options = self.question.get("options") or [
            {"text": "", "image": None, "correct": False} for _ in range(4)
        ]
        for opt in options:
            row = OptionRow(len(self.option_rows) + 1)
            row.text.setText(opt.get("text", ""))
            if opt.get("image"):
                row.image.path = opt["image"]
                row.image.setText("Image added ✓")
            row.correct.setChecked(opt.get("correct", False))
            row.deleted.connect(lambda r=row: self.option_rows.remove(r))
            self.option_rows.append(row)
            self.options_host.addWidget(row)

        add = QPushButton("+ Add option")
        secondary_button(add)
        add.clicked.connect(self.add_option_row)
        self.options_host.addWidget(add)

        w = QWidget()
        w.setLayout(self.options_host)
        self.editor_layout.addWidget(w)

    def add_option_row(self):
        row = OptionRow(len(self.option_rows) + 1)
        row.deleted.connect(lambda r=row: self.option_rows.remove(r))
        self.option_rows.append(row)
        self.options_host.insertWidget(self.options_host.count() - 1, row)

    def build_drag_drop(self):
        hint = QLabel("Define items and their correct Target / Category zone:")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self.editor_layout.addWidget(hint)

        self.drag_host = QVBoxLayout()
        self.drag_rows = []
        items = self.question.get("items") or [
            {"text": "", "image": None, "target": ""} for _ in range(3)
        ]
        for it in items:
            row = DragRow()
            row.text.setText(it.get("text", ""))
            row.target.setText(it.get("target", ""))
            if it.get("image"):
                row.image.path = it["image"]
                row.image.setText("Image added ✓")
            row.deleted.connect(lambda r=row: self.drag_rows.remove(r))
            self.drag_rows.append(row)
            self.drag_host.addWidget(row)

        add = QPushButton("+ Add draggable item")
        secondary_button(add)
        add.clicked.connect(self.add_drag_row)
        self.drag_host.addWidget(add)

        w = QWidget()
        w.setLayout(self.drag_host)
        self.editor_layout.addWidget(w)

    def add_drag_row(self):
        row = DragRow()
        row.deleted.connect(lambda r=row: self.drag_rows.remove(r))
        self.drag_rows.append(row)
        self.drag_host.insertWidget(self.drag_host.count() - 1, row)

    def build_match(self):
        hint = QLabel("Define Left items and their correct Right-hand matching pairs:")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self.editor_layout.addWidget(hint)

        self.match_host = QVBoxLayout()
        self.match_rows = []

        pairs = self.question.get("pairs_list") or []
        if not pairs and "pairs" in self.question:
            for r in self.question["pairs"]:
                if len(r) >= 2:
                    pairs.append({"left": r[0], "right": r[1]})
        if not pairs:
            pairs = [
                {"left": {"text": "", "image": None}, "right": {"text": "", "image": None}}
                for _ in range(3)
            ]

        for p in pairs:
            row = MatchPairRow()
            row.left_text.setText(p.get("left", {}).get("text", ""))
            if p.get("left", {}).get("image"):
                row.left_image.path = p["left"]["image"]
                row.left_image.setText("Left Img ✓")
            row.right_text.setText(p.get("right", {}).get("text", ""))
            if p.get("right", {}).get("image"):
                row.right_image.path = p["right"]["image"]
                row.right_image.setText("Right Img ✓")
            row.deleted.connect(lambda r=row: self.match_rows.remove(r))
            self.match_rows.append(row)
            self.match_host.addWidget(row)

        add = QPushButton("+ Add matching pair")
        secondary_button(add)
        add.clicked.connect(self.add_match_row)
        self.match_host.addWidget(add)

        w = QWidget()
        w.setLayout(self.match_host)
        self.editor_layout.addWidget(w)

    def add_match_row(self):
        row = MatchPairRow()
        row.deleted.connect(lambda r=row: self.match_rows.remove(r))
        self.match_rows.append(row)
        self.match_host.insertWidget(self.match_host.count() - 1, row)

    def save(self):
        q = self.question
        q["question"] = self.prompt.text().strip()
        q["question_image"] = self.question_image.path or None
        q["points"] = 100

        qtype = q["type"]
        if qtype in ("mcq", "checkbox"):
            q["options"] = [r.to_dict() for r in self.option_rows]
        elif qtype == "drag_drop":
            q["items"] = [r.to_dict() for r in self.drag_rows]
        elif qtype == "match":
            q["pairs_list"] = [r.to_dict() for r in self.match_rows]
            q["pairs"] = [[r.to_dict()["left"], r.to_dict()["right"]] for r in self.match_rows]
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
            q_box.setStyleSheet(
                f"QFrame {{ background: white; border: 1px solid {BORDER}; border-radius: 8px; padding: 12px; }}"
            )
            q_layout = QVBoxLayout(q_box)

            header = QLabel(f"Q{i}. {q.get('question', '')} (100 pts)")
            header.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            q_layout.addWidget(header)

            if q.get("question_image"):
                image_path = Path(q["question_image"])
                if image_path.exists():
                    img_lbl = QLabel()
                    pixmap = QPixmap(str(image_path))
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(
                            620,
                            260,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        img_lbl.setPixmap(pixmap)
                        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        img_lbl.setStyleSheet(
                            f"border:1px solid {BORDER};border-radius:10px;background:#FFFFFF;padding:6px;"
                        )
                        q_layout.addWidget(img_lbl)

            qtype = q.get("type")
            if qtype == "mcq":
                for opt in q.get("options", []):
                    q_layout.addWidget(QRadioButton(opt.get("text") or "Option"))
            elif qtype == "checkbox":
                for opt in q.get("options", []):
                    q_layout.addWidget(QCheckBox(opt.get("text") or "Option"))
            elif qtype == "drag_drop":
                for item in q.get("items", []):
                    row = QHBoxLayout()
                    row.addWidget(QLabel(item.get("text", "Item")))
                    combo = QComboBox()
                    combo.addItems(
                        [
                            it.get("target", "Target")
                            for it in q.get("items", [])
                            if it.get("target")
                        ]
                    )
                    row.addWidget(combo)
                    q_layout.addLayout(row)
            elif qtype == "match":
                for pair in q.get("pairs_list", []):
                    row = QHBoxLayout()
                    row.addWidget(QLabel(pair.get("left", {}).get("text", "Left")))
                    row.addWidget(QLabel("⟷"))
                    row.addWidget(QLabel(pair.get("right", {}).get("text", "Right")))
                    q_layout.addLayout(row)

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

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QFrame()
        top.setStyleSheet(f"background: #FFFFFF; border-bottom: 1px solid {BORDER};")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(22, 14, 22, 14)

        title = QLabel("Quiz Maker")
        title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {TEXT};")

        self.quiz_title = QLineEdit("Untitled quiz")
        self.quiz_title.setStyleSheet(
            f"border: none; border-bottom: 1px solid {BORDER}; font-size: 16px; padding: 5px 2px;"
        )

        preview = QPushButton("Preview")
        secondary_button(preview)
        preview.clicked.connect(self.show_preview)

        load = QPushButton("Load JSON")
        secondary_button(load)
        load.clicked.connect(self.import_json)

        save = QPushButton("Save JSON")
        secondary_button(save)
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
        self.cards_container = QWidget()
        self.cards_container.setMaximumWidth(820)
        self.question_area = QVBoxLayout()
        self.question_area.setSpacing(14)
        self.cards_container.setLayout(self.question_area)

        add = QPushButton("+ Add question")
        add.setMinimumHeight(42)
        primary_button(add)
        add.clicked.connect(lambda: self.add_question())
        self.question_area.addWidget(add)

        self.cards_layout.addWidget(self.cards_container, 0, Qt.AlignmentFlag.AlignHCenter)
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
        self.question_area.insertWidget(self.question_area.count() - 1, card)

    def duplicate_question(self, card):
        self.sync_data()
        idx = self.cards.index(card)
        copied = json.loads(json.dumps(self.questions[idx]))
        self.questions.insert(idx + 1, copied)
        self.rebuild_cards()

    def delete_question(self, card):
        if len(self.cards) == 1:
            QMessageBox.information(
                self, "Quiz needs a question", "Keep at least one question in the quiz."
            )
            return
        self.sync_data()
        idx = self.cards.index(card)
        self.cards.pop(idx)
        self.questions.pop(idx)
        self.rebuild_cards()

    def rebuild_cards(self):
        while self.question_area.count() > 1:
            item = self.question_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards = []
        for index, q in enumerate(self.questions, start=1):
            card = QuestionCard(index, q)
            card.duplicate_requested.connect(self.duplicate_question)
            card.delete_requested.connect(self.delete_question)
            self.cards.append(card)
            self.question_area.insertWidget(index - 1, card)

    def show_preview(self):
        self.sync_data()
        quiz_data = {
            "title": self.quiz_title.text().strip() or "Untitled quiz",
            "questions": self.questions,
        }
        dialog = QuizPreviewDialog(quiz_data, self)
        dialog.exec()

    def import_json(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load quiz JSON", "", "JSON files (*.json)")
        if not filename:
            return
        try:
            raw = Path(filename).read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Load failed", f"Could not load JSON.\n\n{exc}")
            return

        quiz = data.get("quiz", data) if isinstance(data, dict) else None
        if not isinstance(quiz, dict):
            QMessageBox.warning(
                self, "Invalid quiz", "The selected JSON does not contain a valid quiz object."
            )
            return

        questions = quiz.get("questions")
        if not isinstance(questions, list) or not questions:
            QMessageBox.warning(self, "Invalid quiz", "No questions found in JSON.")
            return

        self.quiz_title.setText(quiz.get("title", "Untitled quiz"))
        self.questions = questions
        self.rebuild_cards()
        QMessageBox.information(self, "Quiz loaded", f"Loaded {len(questions)} question(s).")

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
            self, "Save quiz JSON", "quiz.json", "JSON files (*.json)"
        )
        if not filename:
            return
        try:
            Path(filename).write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        QMessageBox.information(self, "Saved", f"Saved to:\n{filename}")

    def start_quiz(self):
        self.sync_data()
        data = {
            "version": 1,
            "quiz": {
                "title": self.quiz_title.text().strip() or "Untitled quiz",
                "questions": self.questions,
            },
        }
        self.start_quiz_requested.emit(data["quiz"])
