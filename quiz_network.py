import base64
import json
import mimetypes
import socket
import sqlite3
import threading
import uuid
import random
from datetime import datetime, timezone
from pathlib import Path

DISCOVERY_PORT = 5051
DEFAULT_TCP_PORT = 5050
DISCOVERY_MESSAGE = b"WIFI_QUIZ_DISCOVER_V1"


def detect_lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class HostDatabase:
    def __init__(self, path="wifi_quiz.db"):
        self.path = path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS players (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    joined_at TEXT NOT NULL,
                    connected INTEGER NOT NULL DEFAULT 1,
                    score REAL NOT NULL DEFAULT 0,
                    total INTEGER NOT NULL DEFAULT 0,
                    completed INTEGER NOT NULL DEFAULT 0,
                    score_time REAL NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS quiz_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id TEXT NOT NULL,
                    quiz_id TEXT NOT NULL,
                    score REAL NOT NULL,
                    total INTEGER NOT NULL,
                    answers_json TEXT,
                    completed_at TEXT NOT NULL,
                    UNIQUE(player_id, quiz_id),
                    FOREIGN KEY(player_id) REFERENCES players(id)
                );
            """)

    def upsert_player(self, player_id, name, ip):
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO players (id, name, ip, joined_at, connected, completed)
                VALUES (?, ?, ?, ?, 1, 0)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    ip=excluded.ip,
                    connected=1
            """,
                (player_id, name, ip, now_iso()),
            )

    def reset_database(self):
        with self._lock, self._connect() as db:
            db.execute("DROP TABLE IF EXISTS quiz_results")
            db.execute("DROP TABLE IF EXISTS players")
        self._init_db()

    def remove_player(self, player_id):
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM quiz_results WHERE player_id=?", (player_id,))
            db.execute("DELETE FROM players WHERE id=?", (player_id,))

    def reset_for_quiz(self):
        with self._lock, self._connect() as db:
            db.execute("""
                UPDATE players
                SET completed=0, score=0, total=0, score_time=0
            """)

    def mark_disconnected(self, player_id):
        with self._lock, self._connect() as db:
            db.execute("UPDATE players SET connected=0 WHERE id=?", (player_id,))

    def save_result(self, player_id, quiz_id, score, total, answers, elapsed_seconds=0):
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO quiz_results
                    (player_id, quiz_id, score, total, answers_json, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id, quiz_id) DO UPDATE SET
                    score=excluded.score,
                    total=excluded.total,
                    answers_json=excluded.answers_json,
                    completed_at=excluded.completed_at
            """,
                (
                    player_id,
                    quiz_id,
                    score,
                    total,
                    json.dumps(answers, ensure_ascii=False),
                    now_iso(),
                ),
            )
            db.execute(
                """
                UPDATE players
                SET score=?, total=?, completed=1, score_time=?
                WHERE id=?
            """,
                (score, total, float(elapsed_seconds), player_id),
            )

    def ranking(self):
        with self._lock, self._connect() as db:
            rows = db.execute("""
                SELECT id, name, ip, connected, score, total, completed, score_time
                FROM players
                ORDER BY completed DESC, score DESC,
                         CASE WHEN completed=1 THEN score_time ELSE 999999999 END ASC,
                         name COLLATE NOCASE ASC
            """).fetchall()
            return [dict(row) for row in rows]


class HostNetworkService:
    def __init__(self, room_name="WiFi Quiz Room", port=DEFAULT_TCP_PORT, db_path="wifi_quiz.db"):
        self.room_name = room_name
        self.port = port
        self.ip = detect_lan_ip()
        self.db = HostDatabase(db_path)
        self._stop = threading.Event()
        self._discovery_socket = None
        self._tcp_socket = None
        self._clients = {}
        self._clients_lock = threading.Lock()
        self._quiz_lock = threading.Lock()
        self.active_quiz = None
        self.quiz_started_at = None
        self.player_registered_callback = None
        self.quiz_complete_callback = None
        self.error_callback = None

    def start(self):
        self._stop.clear()
        threading.Thread(target=self._discovery_loop, daemon=True).start()
        threading.Thread(target=self._tcp_loop, daemon=True).start()

    def stop(self):
        self._stop.set()
        for sock in (self._tcp_socket, self._discovery_socket):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
        with self._clients_lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for sock in clients:
            try:
                self._send(
                    sock, {"type": "server_shutdown", "message": "Host ended the quiz room."}
                )
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def start_quiz(self, quiz_data: dict, quiz_id=None):
        quiz_id = quiz_id or str(uuid.uuid4())
        full_quiz = json.loads(json.dumps(quiz_data, ensure_ascii=False))
        self.db.reset_for_quiz()
        with self._quiz_lock:
            self.quiz_started_at = datetime.now(timezone.utc)
            self.active_quiz = {"quiz_id": quiz_id, "quiz": full_quiz}

        public_quiz = sanitize_quiz(full_quiz)
        message = {
            "type": "quiz_start",
            "version": 1,
            "quiz_id": quiz_id,
            "quiz": public_quiz,
        }

        dead = []
        with self._clients_lock:
            clients = list(self._clients.items())
        for player_id, sock in clients:
            try:
                self._send(sock, message)
            except OSError:
                dead.append(player_id)
        for player_id in dead:
            self._remove_client(player_id)
        return quiz_id

    def ranking(self):
        return self.db.ranking()

    def reset_database(self):
        self.db.reset_database()

    def remove_player(self, player_id):
        self.db.remove_player(player_id)

    def _discovery_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._discovery_socket = sock
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", DISCOVERY_PORT))
            sock.settimeout(1.0)
            while not self._stop.is_set():
                try:
                    data, addr = sock.recvfrom(1024)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if data != DISCOVERY_MESSAGE:
                    continue
                response = {
                    "type": "wifi_quiz_host",
                    "version": 1,
                    "ip": self.ip,
                    "port": self.port,
                    "room_name": self.room_name,
                }
                try:
                    sock.sendto(json.dumps(response).encode("utf-8"), addr)
                except OSError:
                    pass
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def _tcp_loop(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp_socket = server
        try:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", self.port))
            server.listen(50)
            server.settimeout(1.0)
            while not self._stop.is_set():
                try:
                    client, addr = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                threading.Thread(
                    target=self._handle_client, args=(client, addr), daemon=True
                ).start()
        except OSError as exc:
            self._notify_error(f"Could not start host network server: {exc}")
        finally:
            try:
                server.close()
            except OSError:
                pass

    def _handle_client(self, client, addr):
        player_id = None
        buffer = bytearray()
        try:
            while not self._stop.is_set():
                chunk = client.recv(4096)
                if not chunk:
                    break
                buffer.extend(chunk)
                while b"\n" in buffer:
                    index = buffer.index(b"\n")
                    raw = bytes(buffer[:index])
                    del buffer[: index + 1]
                    if not raw.strip():
                        continue
                    message = json.loads(raw.decode("utf-8"))
                    message_type = message.get("type")

                    if message_type == "player_register":
                        player = message.get("player") or {}
                        player_id = str(player.get("id") or uuid.uuid4())
                        name = str(player.get("name") or "Player").strip()[:80]
                        ip = str(player.get("ip") or addr[0])
                        self.db.upsert_player(player_id, name, ip)
                        with self._clients_lock:
                            self._clients[player_id] = client
                        self._send(
                            client,
                            {
                                "type": "player_registered",
                                "player_id": player_id,
                                "room_name": self.room_name,
                                "message": "Registration accepted.",
                            },
                        )
                        if self.player_registered_callback:
                            self.player_registered_callback(self.db.ranking())

                        with self._quiz_lock:
                            active = self.active_quiz
                        if active:
                            self._send(
                                client,
                                {
                                    "type": "quiz_start",
                                    "version": 1,
                                    "quiz_id": active["quiz_id"],
                                    "quiz": sanitize_quiz(active["quiz"]),
                                },
                            )

                    elif message_type == "quiz_submit":
                        self._handle_submission(client, player_id, message)

        except Exception as exc:
            print(f"[NETWORK] Client handler error: {exc!r}")
            self._notify_error(f"Client error: {exc}")
        finally:
            if player_id:
                self.db.mark_disconnected(player_id)
                self._remove_client(player_id)
                if self.player_registered_callback:
                    self.player_registered_callback(self.db.ranking())
            try:
                client.close()
            except OSError:
                pass

    def _handle_submission(self, client, player_id, message):
        pid = str((message.get("player") or {}).get("id") or player_id or "")
        quiz_id = str(message.get("quiz_id") or "")
        answers = message.get("answers") or {}
        elapsed_seconds = float(message.get("time_taken") or 0.0)

        with self._quiz_lock:
            active = self.active_quiz

        if not active or quiz_id != active["quiz_id"]:
            self._send(
                client,
                {
                    "type": "submission_rejected",
                    "message": "This quiz is no longer active.",
                },
            )
            return

        if not pid or pid != player_id:
            self._send(
                client, {"type": "submission_rejected", "message": "Player identity mismatch."}
            )
            return

        # Grade directly using the host's private active quiz data
        score, total = grade_quiz(active["quiz"], answers)
        self.db.save_result(pid, quiz_id, score, total, answers, elapsed_seconds)

        self._send(
            client,
            {
                "type": "result_received",
                "message": "Your quiz submission was received and graded by the host.",
                "score": score,
                "total": total,
            },
        )

        if self.quiz_complete_callback:
            self.quiz_complete_callback(self.db.ranking())

    def _remove_client(self, player_id):
        with self._clients_lock:
            sock = self._clients.pop(player_id, None)
        if sock:
            try:
                sock.close()
            except OSError:
                pass

    @staticmethod
    def _send(sock, payload):
        sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))

    def _notify_error(self, message):
        if self.error_callback:
            self.error_callback(message)


def _embed_image(path):
    if not path:
        return None
    try:
        raw = open(path, "rb").read()
    except (OSError, TypeError):
        return None
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return {
        "mime": mime,
        "data": base64.b64encode(raw).decode("ascii"),
        "name": str(path).rsplit("/", 1)[-1],
    }


def sanitize_quiz(quiz: dict) -> dict:
    public = {
        "title": quiz.get("title", "Untitled quiz"),
        "questions": [],
    }
    for index, source in enumerate(quiz.get("questions", [])):
        q = {
            "id": str(source.get("id", f"q{index + 1}")),
            "type": source.get("type", "mcq"),
            "question": source.get("question", ""),
            "question_image": _embed_image(source.get("question_image")),
            "points": 100,
        }
        qtype = q["type"]
        if qtype in ("mcq", "checkbox"):
            q["options"] = [
                {
                    "text": o.get("text", ""),
                    "image": _embed_image(o.get("image")),
                }
                for o in source.get("options", [])
            ]
        elif qtype == "drag_drop":
            q["items"] = [
                {
                    "id": str(i),
                    "text": item.get("text", ""),
                    "image": _embed_image(item.get("image")),
                }
                for i, item in enumerate(source.get("items", []))
            ]
            q["targets"] = sorted(
                {item.get("target", "") for item in source.get("items", []) if item.get("target")}
            )
        elif qtype == "match":
            pairs = source.get("pairs_list") or source.get("pairs", [])
            left = []
            right = []
            for i, p in enumerate(pairs):
                if isinstance(p, dict):
                    l_item = p.get("left", {})
                    r_item = p.get("right", {})
                elif isinstance(p, list) and len(p) >= 2:
                    l_item, r_item = p[0], p[1]
                else:
                    continue
                left.append(
                    {
                        "id": str(i),
                        "text": l_item.get("text", ""),
                        "image": _embed_image(l_item.get("image")),
                    }
                )
                right.append(
                    {"text": r_item.get("text", ""), "image": _embed_image(r_item.get("image"))}
                )
            random.shuffle(right)
            q["left"] = left
            q["right"] = right
        public["questions"].append(q)
    return public


def _norm(value):
    if isinstance(value, str):
        return " ".join(value.strip().casefold().split())
    return value


def grade_quiz(quiz: dict, submitted: dict):
    """Grade quiz using the host's private full quiz data against submitted answers."""
    total_score = 0.0
    total_questions = 0
    submitted = submitted or {}

    for index, q in enumerate(quiz.get("questions", [])):
        qid = str(q.get("id", f"q{index + 1}"))
        qtype = q.get("type", "mcq")
        total_questions += 1
        given = submitted.get(qid)
        question_score = 0.0

        if qtype == "mcq":
            key = next((o.get("text", "") for o in q.get("options", []) if o.get("correct")), None)
            if key is not None and _norm(given) == _norm(key):
                question_score = 100.0

        elif qtype == "checkbox":
            correct_options = [o for o in q.get("options", []) if o.get("correct")]
            total_correct_count = len(correct_options)
            if total_correct_count > 0:
                points_per_item = 100.0 / total_correct_count
                key_set = {_norm(o.get("text", "")) for o in correct_options}
                got_list = [_norm(x) for x in (given or []) if isinstance(x, str)]
                correct_hits = sum(1 for item in got_list if item in key_set)
                wrong_hits = sum(1 for item in got_list if item not in key_set)
                earned_hits = max(0, correct_hits - wrong_hits)
                question_score = round(earned_hits * points_per_item, 2)

        elif qtype == "drag_drop":
            items = q.get("items", [])
            total_items = len(items)
            if total_items > 0:
                points_per_item = 100.0 / total_items
                expected = {
                    str(item.get("id", i)): _norm(item.get("target", ""))
                    for i, item in enumerate(items)
                    if str(item.get("target", "")).strip()
                }
                got = {str(k): _norm(v) for k, v in (given or {}).items()}
                # Blank targets are invalid quiz data and must not count as scorable items.
                if expected:
                    points_per_item = 100.0 / len(expected)
                    correct_count = sum(
                        1
                        for key, expected_value in expected.items()
                        if got.get(key) == expected_value
                    )
                    question_score = round(correct_count * points_per_item, 2)

        elif qtype == "match":
            pairs = q.get("pairs_list") or q.get("pairs", [])
            expected = {}
            for i, p in enumerate(pairs):
                if isinstance(p, dict):
                    r_text = p.get("right", {}).get("text", "")
                elif isinstance(p, list) and len(p) >= 2:
                    r_text = p[1].get("text", "")
                else:
                    continue
                left_item = p.get("left", {}) if isinstance(p, dict) else p[0]
                pair_id = str(left_item.get("id", i)) if isinstance(left_item, dict) else str(i)
                expected[pair_id] = _norm(r_text)

            total_pairs = len(expected)
            if total_pairs > 0:
                points_per_pair = 100.0 / total_pairs
                got = {str(k): _norm(v) for k, v in (given or {}).items()}
                correct_count = sum(1 for k, exp_val in expected.items() if got.get(k) == exp_val)
                question_score = round(correct_count * points_per_pair, 2)

        total_score += question_score

    return round(total_score, 2), total_questions
