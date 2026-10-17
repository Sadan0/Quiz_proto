"""Player side for WiFi Quiz with rich UI for Drag & Drop and Match Questions."""

import base64
import json
import socket
import threading
import time
import uuid

from PySide6.QtCore import QObject, QTimer, Qt, Signal, QMimeData
from PySide6.QtGui import QPixmap, QDrag
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pages.theme import BG, BORDER, DANGER, MUTED, PRIMARY, PRIMARY_HOVER, SUCCESS, SURFACE, TEXT

DISCOVERY_PORT = 5051
DISCOVERY_MESSAGE = b"WIFI_QUIZ_DISCOVER_V1"
DISCOVERY_TIMEOUT = 0.8
CONNECT_TIMEOUT = 2.0
DEFAULT_HOST_PORT = 5050


def local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


class PlayerNetwork(QObject):
    status_changed = Signal(str)
    connected = Signal(dict)
    quiz_received = Signal(dict)
    result_received = Signal(dict)
    submission_rejected = Signal(str)
    disconnected = Signal(str)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player_id = str(uuid.uuid4())
        self.name = ""
        self.sock = None
        self.host_ip = None
        self.host_port = DEFAULT_HOST_PORT
        self.quiz_id = None
        self._stop = threading.Event()
        self._thread = None
        self._recv_buffer = bytearray()

    def start(self, name: str):
        self.name = name.strip()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._close_socket()

    def _run(self):
        self.status_changed.emit("Looking for a host on your WiFi…")
        while not self._stop.is_set():
            host = self._discover_host()
            if host is None:
                self.status_changed.emit("Waiting for host…")
                self._stop.wait(1.5)
                continue
            try:
                self._connect_and_register(*host)
                return
            except (OSError, ConnectionError, ValueError):
                if not self._stop.is_set():
                    self.status_changed.emit("Host found, reconnecting…")
                self._close_socket()
                self._stop.wait(1.0)
            except Exception as exc:
                if not self._stop.is_set():
                    self.error.emit(str(exc))
                self._close_socket()
                self._stop.wait(1.0)

    def _discover_host(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(DISCOVERY_TIMEOUT)
        try:
            sock.sendto(DISCOVERY_MESSAGE, ("255.255.255.255", DISCOVERY_PORT))
            while not self._stop.is_set():
                try:
                    data, addr = sock.recvfrom(1024)
                except socket.timeout:
                    return None
                try:
                    payload = json.loads(data.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    continue
                if payload.get("type") == "wifi_quiz_host":
                    return payload.get("ip") or addr[0], int(payload.get("port", DEFAULT_HOST_PORT))
        except OSError:
            return None
        finally:
            sock.close()
        return None

    def _connect_and_register(self, host_ip, host_port):
        sock = socket.create_connection((host_ip, host_port), timeout=CONNECT_TIMEOUT)
        sock.settimeout(None)
        self.sock = sock
        self.host_ip = host_ip
        self.host_port = host_port
        self._recv_buffer.clear()

        self._send_json({
            "type": "player_register",
            "version": 1,
            "player": {"id": self.player_id, "name": self.name, "ip": local_ip()},
        })

        response = self._recv_json()
        if response.get("type") != "player_registered":
            raise ConnectionError(response.get("message", "Host rejected registration."))

        self.connected.emit(response)
        self.status_changed.emit("Connected. Waiting for the host to start…")

        while not self._stop.is_set():
            message = self._recv_json()
            if not message:
                break
            message_type = message.get("type")
            if message_type == "quiz_start":
                self.quiz_id = message.get("quiz_id")
                self.quiz_received.emit(message)
            elif message_type == "server_shutdown":
                self.disconnected.emit("The host ended the quiz room.")
                return
            elif message_type == "result_received":
                self.result_received.emit(message)
                return
            elif message_type == "submission_rejected":
                self.submission_rejected.emit(message.get("message", "The host rejected the submission."))

    def submit_answers(self, answers: dict, time_taken: float) -> bool:
        if not self.sock or not self.quiz_id:
            return False
        payload = {
            "type": "quiz_submit",
            "version": 1,
            "quiz_id": self.quiz_id,
            "player": {"id": self.player_id, "name": self.name},
            "answers": answers,
            "time_taken": time_taken,
        }
        try:
            self._send_json(payload)
            return True
        except OSError:
            return False

    def _send_json(self, payload):
        if not self.sock:
            raise OSError("Not connected to host")
        self.sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))

    def _recv_json(self):
        while not self._stop.is_set():
            newline = self._recv_buffer.find(b"\n")
            if newline != -1:
                raw = bytes(self._recv_buffer[:newline])
                del self._recv_buffer[:newline + 1]
                return json.loads(raw.decode("utf-8"))
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Host disconnected.")
            self._recv_buffer.extend(chunk)
        return {}

    def _close_socket(self):
        sock, self.sock = self.sock, None
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass


class WaitingAnimation(QLabel):
    def __init__(self, parent=None):
        super().__init__("●  ○  ○", parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"color: {PRIMARY}; font-size: 22px;")
        self._index = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(350)

    def _animate(self):
        states = ["●  ○  ○", "○  ●  ○", "○  ○  ●", "○  ●  ○"]
        self.setText(states[self._index % len(states)])
        self._index += 1


class PlayerNamePage(QWidget):
    proceed = Signal(str)
    navigate_back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.addStretch()
        panel = QFrame()
        panel.setMaximumWidth(620)
        panel.setStyleSheet(f"QFrame {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:20px; }}")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(32, 30, 32, 30)
        layout.setSpacing(12)
        title = QLabel("Join as Player")
        title.setStyleSheet(f"color:{TEXT}; font-size:28px; font-weight:800;")
        subtitle = QLabel("Enter your name. You’ll be connected automatically when the host is available.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{MUTED}; font-size:14px;")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Your name")
        self.name_input.setMaxLength(80)
        self.name_input.returnPressed.connect(self._submit)
        self.name_input.setStyleSheet(f"QLineEdit {{background:{SURFACE};color:{TEXT};border:1px solid {BORDER};border-radius:10px;padding:12px;font-size:15px;}} QLineEdit:focus {{border:1px solid {PRIMARY};}}")
        join = QPushButton("Continue")
        join.setStyleSheet(f"QPushButton {{background:{PRIMARY};color:white;border:none;border-radius:10px;padding:12px;font-weight:700;}} QPushButton:hover {{background:{PRIMARY_HOVER};}}")
        join.clicked.connect(self._submit)
        back = QPushButton("← Back")
        back.setStyleSheet(f"background:transparent;color:{MUTED};border:none;padding:8px;")
        back.clicked.connect(self.navigate_back.emit)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(self.name_input)
        layout.addWidget(join)
        layout.addWidget(back)
        root.addWidget(panel, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addStretch()

    def _submit(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Please enter your player name.")
            self.name_input.setFocus()
            return
        self.proceed.emit(name)


class PlayerWaitingPage(QWidget):
    quiz_ready = Signal(dict)
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.network = PlayerNetwork(self)
        self._setup_ui()
        self.network.status_changed.connect(self.status_label_set)
        self.network.connected.connect(self._connected)
        self.network.quiz_received.connect(self.quiz_ready.emit)
        self.network.disconnected.connect(self._disconnected)
        self.network.error.connect(self._network_error)

    def _setup_ui(self):
        self.setStyleSheet(f"background:{BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.addStretch()
        panel = QFrame()
        panel.setMaximumWidth(620)
        panel.setStyleSheet(f"QFrame {{background:{SURFACE};border:1px solid {BORDER};border-radius:24px;}}")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(40, 40, 32, 32)
        title = QLabel("Waiting for host")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{TEXT};font-size:28px;font-weight:800;")
        self.player_label = QLabel()
        self.player_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.player_label.setStyleSheet(f"color:{MUTED};font-size:14px;")
        layout.addWidget(title)
        layout.addWidget(self.player_label)
        layout.addSpacing(18)
        layout.addWidget(WaitingAnimation())
        self.status_label = QLabel("Looking for a host on your WiFi…")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(f"color:{TEXT};font-size:15px;")
        layout.addWidget(self.status_label)
        quit_button = QPushButton("Quit")
        quit_button.clicked.connect(self._quit)
        quit_button.setStyleSheet(f"QPushButton {{background:transparent;color:{DANGER};border:1px solid #F0CACA;border-radius:10px;padding:10px 18px;font-weight:700;}} QPushButton:hover {{background:#FFF1F1;}}")
        layout.addWidget(quit_button, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(panel, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addStretch()

    def begin(self, name):
        self.player_label.setText(f"Playing as <b>{name}</b>")
        self.network.start(name)

    def status_label_set(self, text):
        self.status_label.setText(text)

    def _connected(self, payload):
        room = payload.get("room_name", "WiFi Quiz Room")
        self.status_label.setText(f"Connected to <b>{room}</b>. Waiting for host to start…")

    def _disconnected(self, message):
        self.status_label.setText(message)

    def _network_error(self, message):
        self.status_label.setText(f"Network error: {message}")

    def _quit(self):
        self.network.stop()
        self.quit_requested.emit()


class PlayerQuizPage(QWidget):
    submitted = Signal()
    quit_requested = Signal()

    def __init__(self, network: PlayerNetwork, parent=None):
        super().__init__(parent)
        self.network = network
        self.quiz = {}
        self.questions = []
        self.controls = []
        self.nav_buttons = []
        self.current_index = 0
        self.submitting = False
        self.start_time = None
        self._build_shell()
        self.network.result_received.connect(self._result_received)
        self.network.submission_rejected.connect(self._submission_rejected)

    def _build_shell(self):
        self.setStyleSheet(f"background:{BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(12)

        header = QHBoxLayout()
        self.title = QLabel("Quiz")
        self.title.setStyleSheet(f"color:{TEXT};font-size:24px;font-weight:800;")
        self.progress = QLabel()
        self.progress.setStyleSheet(f"color:{MUTED};font-size:13px;")
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.progress)
        root.addLayout(header)

        self.question_stack = QStackedWidget()
        self.question_stack.setStyleSheet("QStackedWidget { border: none; background: transparent; }")
        root.addWidget(self.question_stack, 1)

        self.nav_bar = QHBoxLayout()
        self.nav_bar.setSpacing(5)
        self.nav_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addLayout(self.nav_bar)

        bottom = QHBoxLayout()
        quit_btn = QPushButton("Quit")
        quit_btn.clicked.connect(self._quit)
        quit_btn.setStyleSheet(f"background:transparent;color:{DANGER};border:1px solid #F0CACA;border-radius:10px;padding:10px 18px;font-weight:700;")
        self.previous_btn = QPushButton("← Previous")
        self.next_btn = QPushButton("Next →")
        self.submit_btn = QPushButton("Submit Quiz")
        self.previous_btn.clicked.connect(lambda: self._show_question(self.current_index - 1))
        self.next_btn.clicked.connect(lambda: self.current_index + 1 and self._show_question(self.current_index + 1))
        self.next_btn.clicked.connect(lambda: self._show_question(self.current_index + 1))
        self.submit_btn.clicked.connect(self.submit_quiz)
        for btn in (self.previous_btn, self.next_btn):
            btn.setStyleSheet(f"background:#FFFFFF;color:{TEXT};border:1px solid {BORDER};border-radius:10px;padding:10px 18px;font-weight:700;")
        self.submit_btn.setStyleSheet(f"QPushButton {{background:{PRIMARY};color:white;border:none;border-radius:10px;padding:11px 20px;font-weight:700;}} QPushButton:hover {{background:{PRIMARY_HOVER};}}")
        bottom.addWidget(quit_btn)
        bottom.addStretch()
        bottom.addWidget(self.previous_btn)
        bottom.addWidget(self.next_btn)
        bottom.addWidget(self.submit_btn)
        root.addLayout(bottom)

    def load_quiz(self, payload):
        self.quiz = payload.get("quiz") or {}
        self.questions = self.quiz.get("questions") or []
        self.title.setText(self.quiz.get("title") or "Quiz")
        self._clear_questions()
        self.controls = []
        self.nav_buttons = []
        self.current_index = 0
        self.start_time = time.time()

        while self.nav_bar.count():
            item = self.nav_bar.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for index, question in enumerate(self.questions):
            card, control = self._make_question_card(index, question)
            self.question_stack.addWidget(card)
            self.controls.append(control)

            button = QPushButton(str(index + 1))
            button.setFixedSize(34, 34)
            button.clicked.connect(lambda checked=False, i=index: self._show_question(i))
            self.nav_bar.addWidget(button)
            self.nav_buttons.append(button)

        self.submitting = False
        self.submit_btn.setEnabled(True)
        self.submit_btn.setVisible(True)
        self.submit_btn.setText("Submit Quiz")
        self._show_question(0)

    def _clear_questions(self):
        while self.question_stack.count():
            widget = self.question_stack.widget(0)
            self.question_stack.removeWidget(widget)
            widget.deleteLater()

    def _show_question(self, index):
        if not self.questions:
            return
        index = max(0, min(index, len(self.questions) - 1))
        self.current_index = index
        self.question_stack.setCurrentIndex(index)
        self.progress.setText(f"Question {index + 1} / {len(self.questions)}")
        self.previous_btn.setEnabled(index > 0)
        self.next_btn.setEnabled(index < len(self.questions) - 1)
        for i, button in enumerate(self.nav_buttons):
            answered = self._is_answered(i)
            if i == index:
                button.setStyleSheet(f"background:{PRIMARY};color:white;border:none;border-radius:17px;font-weight:800;")
            elif answered:
                button.setStyleSheet(f"background:#E7F6EE;color:#16834B;border:1px solid #B9E5CB;border-radius:17px;font-weight:800;")
            else:
                button.setStyleSheet(f"background:#FFFFFF;color:{TEXT};border:1px solid {BORDER};border-radius:17px;font-weight:700;")

    def _is_answered(self, index):
        if index >= len(self.controls):
            return False
        qtype, widget = self.controls[index]
        if qtype == "mcq":
            return widget.checkedButton() is not None
        if qtype == "checkbox":
            return any(cb.isChecked() for cb in widget)
        if qtype == "drag_drop":
            return all(combo.currentText() != "Select target…" for _, combo in widget)
        if qtype == "match":
            return all(combo.currentText() != "Select match…" for _, combo in widget)
        return False

    def _make_question_card(self, index, q):
        card = QFrame()
        card.setStyleSheet(f"QFrame {{background:{SURFACE};border:1px solid {BORDER};border-radius:18px;}} QLabel {{border:none;}}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(44, 42, 44, 42)
        layout.setSpacing(16)

        number = QLabel(f"Question {index + 1}")
        number.setStyleSheet(f"color:{PRIMARY};font-size:13px;font-weight:800;")
        layout.addWidget(number)

        label = QLabel(q.get("question", ""))
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{TEXT};font-size:24px;font-weight:800;")
        layout.addWidget(label)

        if q.get("question_image"):
            image_label = self._image_label(q.get("question_image"), max_width=760, max_height=260)
            if image_label is not None:
                layout.addWidget(image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        qtype = q.get("type", "mcq")
        if qtype == "mcq":
            group = QButtonGroup(card)
            group.setExclusive(True)
            for option in q.get("options", []):
                row = QVBoxLayout()
                rb = QRadioButton(option.get("text") or "Option")
                rb.setStyleSheet(f"QRadioButton {{color:{TEXT};padding:8px;font-size:15px;}}")
                group.addButton(rb)
                row.addWidget(rb)
                if option.get("image"):
                    img = self._image_label(option.get("image"), max_width=450, max_height=150)
                    if img:
                        row.addWidget(img, alignment=Qt.AlignmentFlag.AlignLeft)
                layout.addLayout(row)
            return card, ("mcq", group)

        if qtype == "checkbox":
            checks = []
            for option in q.get("options", []):
                row = QVBoxLayout()
                cb = QCheckBox(option.get("text") or "Option")
                cb.setStyleSheet(f"QCheckBox {{color:{TEXT};padding:8px;font-size:15px;}}")
                checks.append(cb)
                row.addWidget(cb)
                if option.get("image"):
                    img = self._image_label(option.get("image"), max_width=450, max_height=150)
                    if img:
                        row.addWidget(img, alignment=Qt.AlignmentFlag.AlignLeft)
                layout.addLayout(row)
            return card, ("checkbox", checks)

        if qtype == "drag_drop":
            rows = []
            targets = q.get("targets", [])
            instruction = QLabel("Assign each item to its correct target category below:")
            instruction.setStyleSheet(f"color: {MUTED}; font-size: 13px; font-weight: 600;")
            layout.addWidget(instruction)

            for item in q.get("items", []):
                row_layout = QHBoxLayout()
                item_lbl = QLabel(item.get("text", "Item"))
                item_lbl.setStyleSheet(f"color: {TEXT}; font-size: 15px; font-weight: 700; background: #F8F9FC; padding: 8px 12px; border-radius: 8px; border: 1px solid {BORDER};")
                row_layout.addWidget(item_lbl, 1)

                if item.get("image"):
                    img = self._image_label(item.get("image"), max_width=120, max_height=80)
                    if img:
                        row_layout.addWidget(img)

                row_layout.addWidget(QLabel("➔"))
                combo = QComboBox()
                combo.setStyleSheet(f"QComboBox {{background: #FFFFFF; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px 30px 8px 12px; min-width: 180px; font-size: 14px;}}")
                combo.addItem("Select target…")
                combo.addItems(targets)
                row_layout.addWidget(combo, 1)
                layout.addLayout(row_layout)
                rows.append((str(item.get("id")), combo))
            return card, ("drag_drop", rows)

        if qtype == "match":
            rows = []
            right_choices = [x.get("text", "") for x in q.get("right", [])]
            instruction = QLabel("Match each left-side item with its corresponding right-side pair:")
            instruction.setStyleSheet(f"color: {MUTED}; font-size: 13px; font-weight: 600;")
            layout.addWidget(instruction)

            for item in q.get("left", []):
                row_layout = QHBoxLayout()
                left_lbl = QLabel(item.get("text", "Left Item"))
                left_lbl.setStyleSheet(f"color: {TEXT}; font-size: 15px; font-weight: 700; background: #F8F9FC; padding: 8px 12px; border-radius: 8px; border: 1px solid {BORDER};")
                row_layout.addWidget(left_lbl, 1)

                if item.get("image"):
                    img = self._image_label(item.get("image"), max_width=120, max_height=80)
                    if img:
                        row_layout.addWidget(img)

                row_layout.addWidget(QLabel("⟷"))
                combo = QComboBox()
                combo.setStyleSheet(f"QComboBox {{background: #FFFFFF; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px 30px 8px 12px; min-width: 180px; font-size: 14px;}}")
                combo.addItem("Select match…")
                combo.addItems(right_choices)
                row_layout.addWidget(combo, 1)
                layout.addLayout(row_layout)
                rows.append((str(item.get("id")), combo))
            return card, ("match", rows)

        fallback = QLabel("This question type is not supported yet.")
        fallback.setStyleSheet(f"color:{MUTED};")
        layout.addWidget(fallback)
        return card, ("unsupported", fallback)

    @staticmethod
    def _image_label(image_payload, max_width=760, max_height=260):
        if not isinstance(image_payload, dict):
            return None
        data = image_payload.get("data")
        if not data:
            return None
        try:
            raw = base64.b64decode(data, validate=True)
            pixmap = QPixmap()
            if not pixmap.loadFromData(raw):
                return None
            pixmap = pixmap.scaled(
                max_width,
                max_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            label = QLabel()
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(f"border:1px solid {BORDER};border-radius:10px;background:#FFFFFF;padding:6px;")
            return label
        except Exception:
            return None

    def _collect_answers(self):
        answers = {}
        for index, control in enumerate(self.controls):
            qid = str(self.questions[index].get("id", f"q{index + 1}"))
            qtype, widget = control
            if qtype == "mcq":
                checked = widget.checkedButton()
                answers[qid] = checked.text() if checked else None
            elif qtype == "checkbox":
                answers[qid] = [cb.text() for cb in widget if cb.isChecked()]
            elif qtype in ("drag_drop", "match"):
                answers[qid] = {str(item_id): combo.currentText() for item_id, combo in widget if combo.currentIndex() > 0}
            else:
                answers[qid] = None
        return answers

    def submit_quiz(self):
        if self.submitting:
            return
        self.submitting = True
        self.submit_btn.setEnabled(False)
        self.previous_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.submit_btn.setText("Submitting…")

        elapsed_time = time.time() - self.start_time if self.start_time else 0.0
        if not self.network.submit_answers(self._collect_answers(), elapsed_time):
            self.submitting = False
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("Submit Quiz")
            QMessageBox.warning(self, "Submission failed", "The host could not be reached.")
            return
        self.submitted.emit()

    def _result_received(self, result):
        self.submitting = False
        while self.question_stack.count():
            widget = self.question_stack.widget(0)
            self.question_stack.removeWidget(widget)
            widget.deleteLater()
        completed = QFrame()
        completed.setStyleSheet(f"QFrame {{background:{SURFACE};border:1px solid {BORDER};border-radius:18px;}}")
        layout = QVBoxLayout(completed)
        layout.setContentsMargins(40, 70, 40, 70)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message = QLabel("✓  Quiz Completed")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setStyleSheet(f"color:{TEXT};font-size:32px;font-weight:800;")
        layout.addWidget(message)
        score = QLabel(f"Your submission has been graded by the host.\n\nScore: {result.get('score', 0)} pts")
        score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score.setStyleSheet(f"color:{MUTED};font-size:16px;")
        layout.addWidget(score)
        self.question_stack.addWidget(completed)
        self.question_stack.setCurrentWidget(completed)
        self.progress.setText("Submitted")
        self.previous_btn.setVisible(False)
        self.next_btn.setVisible(False)
        self.submit_btn.setVisible(False)
        self.nav_bar.setEnabled(False)

    def _submission_rejected(self, message):
        self.submitting = False
        self.submit_btn.setEnabled(True)
        self.previous_btn.setEnabled(True)
        self.next_btn.setEnabled(True)
        self.submit_btn.setText("Submit Quiz")
        QMessageBox.warning(self, "Submission rejected", message)

    def _quit(self):
        self.network.stop()
        self.quit_requested.emit()


class PlayerDashboard(QWidget):
    navigate = Signal(str)

    def __init__(self, back_page="dashboard"):
        super().__init__()
        self.back_page = back_page
        self.name_page = PlayerNamePage()
        self.waiting_page = PlayerWaitingPage()
        self.quiz_page = PlayerQuizPage(self.waiting_page.network)

        self.stack = QVBoxLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.name_page)
        self.stack.addWidget(self.waiting_page)
        self.stack.addWidget(self.quiz_page)

        self.name_page.proceed.connect(self._start_waiting)
        self.name_page.navigate_back.connect(lambda: self.navigate.emit(self.back_page))
        self.waiting_page.quiz_ready.connect(self._start_quiz)
        self.waiting_page.quit_requested.connect(lambda: self.navigate.emit(self.back_page))
        self.quiz_page.quit_requested.connect(lambda: self.navigate.emit(self.back_page))
        self.on_enter()

    def _show_only(self, widget):
        for i in range(self.stack.count()):
            self.stack.itemAt(i).widget().setVisible(self.stack.itemAt(i).widget() is widget)

    def _start_waiting(self, name):
        self._show_only(self.waiting_page)
        self.waiting_page.begin(name)

    def _start_quiz(self, payload):
        self._show_only(self.quiz_page)
        self.quiz_page.load_quiz(payload)

    def on_enter(self):
        self._show_only(self.name_page)
        self.name_page.name_input.setFocus()

    def closeEvent(self, event):
        self.waiting_page.network.stop()
        event.accept()
