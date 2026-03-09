import sqlite3
import json
import threading
from datetime import datetime


class Database:
    """Потокобезопасная обёртка над SQLite"""

    def __init__(self, path: str = "bot_data.db"):
        self._path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    # ── DDL ──────────────────────────────────────

    def _create_tables(self):
        c = self._conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id     INTEGER PRIMARY KEY,
                antimat     INTEGER DEFAULT 1,
                antilinks   INTEGER DEFAULT 1,
                antiflood   INTEGER DEFAULT 1,
                welcome     INTEGER DEFAULT 1,
                captcha     INTEGER DEFAULT 1,
                rules       TEXT    DEFAULT ''
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id  INTEGER,
                chat_id  INTEGER,
                added_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, chat_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                user_id  INTEGER,
                chat_id  INTEGER,
                count    INTEGER DEFAULT 0,
                reasons  TEXT    DEFAULT '[]',
                PRIMARY KEY (user_id, chat_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS banned_words (
                word TEXT PRIMARY KEY
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                chat_id        INTEGER PRIMARY KEY,
                banned_count   INTEGER DEFAULT 0,
                deleted_count  INTEGER DEFAULT 0,
                new_users      INTEGER DEFAULT 0,
                warnings_count INTEGER DEFAULT 0
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id   INTEGER,
                user_id   INTEGER,
                action    TEXT,
                details   TEXT,
                ts        TEXT DEFAULT (datetime('now'))
            )
        """)

        self._conn.commit()
        self._seed_words()

    def _seed_words(self):
        """Базовый набор запрещённых корней"""
        roots = [
            "хуй", "хуе", "хуё", "пизд", "блят", "бляд",
            "ебат", "ёбан", "сука", "нахуй", "залуп",
            "шлюх", "мудак", "мудил", "пидор", "пидар",
            "гандон", "ублюд", "дебил",
            "fuck", "shit", "bitch", "asshole", "dick",
        ]
        with self._lock:
            c = self._conn.cursor()
            for w in roots:
                c.execute(
                    "INSERT OR IGNORE INTO banned_words(word) VALUES(?)", (w,)
                )
            self._conn.commit()

    # ── Chat settings ────────────────────────────

    def get_settings(self, chat_id: int) -> dict:
        with self._lock:
            c = self._conn.cursor()
            c.execute(
                "SELECT * FROM chat_settings WHERE chat_id=?", (chat_id,)
            )
            row = c.fetchone()
            if row:
                return dict(row)
            c.execute(
                "INSERT INTO chat_settings(chat_id) VALUES(?)", (chat_id,)
            )
            self._conn.commit()
            return self.get_settings(chat_id)

    def toggle_setting(self, chat_id: int, col: str) -> int:
        s = self.get_settings(chat_id)
        new = 0 if s[col] else 1
        with self._lock:
            self._conn.execute(
                f"UPDATE chat_settings SET {col}=? WHERE chat_id=?",
                (new, chat_id),
            )
            self._conn.commit()
        return new

    def set_rules(self, chat_id: int, text: str):
        self.get_settings(chat_id)
        with self._lock:
            self._conn.execute(
                "UPDATE chat_settings SET rules=? WHERE chat_id=?",
                (text, chat_id),
            )
            self._conn.commit()

    def get_all_chat_ids(self) -> list[int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT chat_id FROM chat_settings"
            ).fetchall()
            return [r["chat_id"] for r in rows]

    # ── Admins ───────────────────────────────────

    def add_admin(self, uid: int, cid: int):
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO admins(user_id,chat_id) VALUES(?,?)",
                (uid, cid),
            )
            self._conn.commit()

    def del_admin(self, uid: int, cid: int):
        with self._lock:
            self._conn.execute(
                "DELETE FROM admins WHERE user_id=? AND chat_id=?",
                (uid, cid),
            )
            self._conn.commit()

    def get_admins(self, cid: int) -> list[int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT user_id FROM admins WHERE chat_id=?", (cid,)
            ).fetchall()
            return [r["user_id"] for r in rows]

    def is_admin(self, uid: int, cid: int) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM admins WHERE user_id=? AND chat_id=?",
                (uid, cid),
            ).fetchone()
            return row is not None

    # ── Warnings ─────────────────────────────────

    def get_warns(self, uid: int, cid: int) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM warnings WHERE user_id=? AND chat_id=?",
                (uid, cid),
            ).fetchone()
        if not row:
            return {"count": 0, "reasons": []}
        d = dict(row)
        d["reasons"] = json.loads(d["reasons"])
        return d

    def add_warn(self, uid: int, cid: int, reason: str = "") -> int:
        w = self.get_warns(uid, cid)
        n = w["count"] + 1
        reasons = w["reasons"]
        reasons.append(reason)
        jr = json.dumps(reasons, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                """INSERT INTO warnings(user_id,chat_id,count,reasons)
                   VALUES(?,?,?,?)
                   ON CONFLICT(user_id,chat_id)
                   DO UPDATE SET count=?, reasons=?""",
                (uid, cid, n, jr, n, jr),
            )
            self._conn.commit()
        self.inc_stat(cid, "warnings_count")
        return n

    def reset_warns(self, uid: int, cid: int):
        with self._lock:
            self._conn.execute(
                "DELETE FROM warnings WHERE user_id=? AND chat_id=?",
                (uid, cid),
            )
            self._conn.commit()

    # ── Banned words ─────────────────────────────

    def get_banned_words(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT word FROM banned_words"
            ).fetchall()
            return [r["word"] for r in rows]

    def add_word(self, w: str):
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO banned_words(word) VALUES(?)",
                (w.lower(),),
            )
            self._conn.commit()

    def del_word(self, w: str):
        with self._lock:
            self._conn.execute(
                "DELETE FROM banned_words WHERE word=?", (w.lower(),)
            )
            self._conn.commit()

    # ── Stats ────────────────────────────────────

    def get_stats(self, cid: int) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM stats WHERE chat_id=?", (cid,)
            ).fetchone()
            if row:
                return dict(row)
            self._conn.execute(
                "INSERT INTO stats(chat_id) VALUES(?)", (cid,)
            )
            self._conn.commit()
        return self.get_stats(cid)

    def inc_stat(self, cid: int, col: str):
        self.get_stats(cid)
        with self._lock:
            self._conn.execute(
                f"UPDATE stats SET {col}={col}+1 WHERE chat_id=?",
                (cid,),
            )
            self._conn.commit()

    # ── Log ──────────────────────────────────────

    def log(self, cid: int, uid: int, action: str, details: str = ""):
        with self._lock:
            self._conn.execute(
                "INSERT INTO action_log(chat_id,user_id,action,details)"
                " VALUES(?,?,?,?)",
                (cid, uid, action, details),
            )
            self._conn.commit()

    # ── Lifecycle ────────────────────────────────

    def close(self):
        self._conn.close()
