"""SQLite Database Persistence Layer with WAL Mode and Schema Migrations."""

import sqlite3
from pathlib import Path
from typing import Optional


INITIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS persistent_sessions (
    session_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS persistent_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    name TEXT,
    tool_calls_json TEXT,
    tool_call_id TEXT,
    timestamp TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}',
    FOREIGN KEY(session_id) REFERENCES persistent_sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS persistent_tasks (
    task_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    current_step INTEGER DEFAULT 0,
    max_steps INTEGER DEFAULT 10,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_message TEXT,
    metadata_json TEXT DEFAULT '{}',
    FOREIGN KEY(session_id) REFERENCES persistent_sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    tags_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Full-Text Search FTS5 Virtual Table for Fast Memory Retrieval
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    id UNINDEXED,
    category,
    title,
    content,
    tokenize='unicode61'
);

-- Triggers keeping memories_fts synchronized
CREATE TRIGGER IF NOT EXISTS trg_memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(id, category, title, content)
    VALUES (new.id, new.category, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS trg_memories_ad AFTER DELETE ON memories BEGIN
    DELETE FROM memories_fts WHERE id = old.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_memories_au AFTER UPDATE ON memories BEGIN
    DELETE FROM memories_fts WHERE id = old.id;
    INSERT INTO memories_fts(id, category, title, content)
    VALUES (new.id, new.category, new.title, new.content);
END;
"""


class Database:
    """Manages SQLite database connections, WAL mode, and migrations."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None or str(db_path) == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = str(db_path)
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Retrieve connection or create new one with WAL mode."""
        if self._conn is None:
            try:
                conn = sqlite3.connect(
                    self.db_path,
                    check_same_thread=False,
                    timeout=10.0
                )
            except sqlite3.OperationalError:
                if self.db_path != ":memory:":
                    self.db_path = ":memory:"
                    conn = sqlite3.connect(":memory:", check_same_thread=False, timeout=10.0)
                else:
                    raise
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for high concurrent throughput if not in-memory
            if self.db_path != ":memory:":
                try:
                    conn.execute("PRAGMA journal_mode=WAL;")
                except sqlite3.OperationalError:
                    pass
            conn.execute("PRAGMA foreign_keys=ON;")
            self._conn = conn
        return self._conn

    def _init_db(self) -> None:
        """Run schema migrations."""
        try:
            conn = self.get_connection()
            with conn:
                conn.executescript(INITIAL_SCHEMA)
                # Record migration version 1
                conn.execute("INSERT OR IGNORE INTO schema_migrations (version) VALUES (1);")
        except sqlite3.OperationalError:
            # Fall back to in-memory database if filesystem is read-only
            if self.db_path != ":memory:":
                self.close()
                self.db_path = ":memory:"
                conn = self.get_connection()
                with conn:
                    conn.executescript(INITIAL_SCHEMA)
                    conn.execute("INSERT OR IGNORE INTO schema_migrations (version) VALUES (1);")

    def close(self) -> None:
        """Close active database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
