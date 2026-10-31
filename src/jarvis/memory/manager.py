"""Structured Memory Manager with FTS5 Full-Text Retrieval."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from jarvis.memory.database import Database
from jarvis.memory.models import MemoryCategory, MemoryItem
from jarvis.models.messages import ChatMessage, MessageRole, ToolCall
from jarvis.models.session import SessionState, TaskState, TaskStatus


class MemoryManager:
    """Coordinates memory persistence, FTS5 retrieval, editing, and deletion."""

    def __init__(self, database: Optional[Database] = None) -> None:
        self.db = database or Database()

    def store(
        self,
        category: MemoryCategory,
        title: str,
        content: str,
        confidence: float = 1.0,
        tags: Optional[List[str]] = None,
    ) -> MemoryItem:
        """Store a new structured memory item."""
        item = MemoryItem(
            category=category,
            title=title,
            content=content,
            confidence=confidence,
            tags=tags or [],
        )
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO memories (id, category, title, content, confidence, tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.category.value,
                    item.title,
                    item.content,
                    item.confidence,
                    json.dumps(item.tags),
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                ),
            )
        return item

    def get(self, memory_id: str) -> Optional[MemoryItem]:
        """Retrieve a specific memory item by ID."""
        conn = self.db.get_connection()
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if not row:
            return None
        return self._row_to_memory(row)

    def search(
        self,
        query: str,
        category: Optional[MemoryCategory] = None,
        limit: int = 5,
    ) -> List[MemoryItem]:
        """Perform full-text search across memories using FTS5 ranking."""
        conn = self.db.get_connection()
        clean_query = query.replace("'", " ").replace('"', " ").strip()
        if not clean_query:
            return self.list_memories(category=category, limit=limit)

        sql = """
            SELECT m.* FROM memories m
            JOIN memories_fts fts ON m.id = fts.id
            WHERE memories_fts MATCH ?
        """
        params = [clean_query]

        if category:
            sql += " AND m.category = ?"
            params.append(category.value)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        try:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_memory(r) for r in rows]
        except Exception:
            # Fallback to LIKE if FTS query syntax error
            fallback_sql = "SELECT * FROM memories WHERE (title LIKE ? OR content LIKE ?)"
            f_params = [f"%{clean_query}%", f"%{clean_query}%"]
            if category:
                fallback_sql += " AND category = ?"
                f_params.append(category.value)
            fallback_sql += " ORDER BY updated_at DESC LIMIT ?"
            f_params.append(limit)
            rows = conn.execute(fallback_sql, f_params).fetchall()
            return [self._row_to_memory(r) for r in rows]

    def list_memories(
        self, category: Optional[MemoryCategory] = None, limit: int = 50
    ) -> List[MemoryItem]:
        """List recent memories, optionally filtered by category."""
        conn = self.db.get_connection()
        if category:
            rows = conn.execute(
                "SELECT * FROM memories WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
                (category.value, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def update(
        self,
        memory_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        confidence: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[MemoryItem]:
        """Update an existing memory item."""
        current = self.get(memory_id)
        if not current:
            return None

        new_title = title if title is not None else current.title
        new_content = content if content is not None else current.content
        new_confidence = confidence if confidence is not None else current.confidence
        new_tags = tags if tags is not None else current.tags
        now = datetime.now(timezone.utc)

        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                UPDATE memories
                SET title = ?, content = ?, confidence = ?, tags_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    new_title,
                    new_content,
                    new_confidence,
                    json.dumps(new_tags),
                    now.isoformat(),
                    memory_id,
                ),
            )
        return self.get(memory_id)

    def delete(self, memory_id: str) -> bool:
        """Delete a memory item."""
        conn = self.db.get_connection()
        with conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cursor.rowcount > 0

    def clear_category(self, category: MemoryCategory) -> int:
        """Delete all memories in a given category."""
        conn = self.db.get_connection()
        with conn:
            cursor = conn.execute("DELETE FROM memories WHERE category = ?", (category.value,))
            return cursor.rowcount

    def _row_to_memory(self, row: Any) -> MemoryItem:
        tags = []
        try:
            tags = json.loads(row["tags_json"])
        except Exception:
            pass

        return MemoryItem(
            id=row["id"],
            category=MemoryCategory(row["category"]),
            title=row["title"],
            content=row["content"],
            confidence=row["confidence"],
            tags=tags,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # Session & Conversation Continuity Hooks
    def persist_session(self, session: SessionState) -> None:
        """Persist conversation session and messages to SQLite."""
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO persistent_sessions (session_id, title, created_at, updated_at, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.title,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    json.dumps(session.metadata),
                ),
            )
            for msg in session.messages:
                tool_calls_json = None
                if msg.tool_calls:
                    tool_calls_json = json.dumps([tc.model_dump() for tc in msg.tool_calls])

                conn.execute(
                    """
                    INSERT OR REPLACE INTO persistent_messages (id, session_id, role, content, name, tool_calls_json, tool_call_id, timestamp, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        msg.id,
                        session.session_id,
                        msg.role.value,
                        msg.content,
                        msg.name,
                        tool_calls_json,
                        msg.tool_call_id,
                        msg.timestamp.isoformat(),
                        json.dumps(msg.metadata),
                    ),
                )

    def load_session(self, session_id: str) -> Optional[SessionState]:
        """Restore a session and its message history from SQLite."""
        conn = self.db.get_connection()
        sess_row = conn.execute(
            "SELECT * FROM persistent_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not sess_row:
            return None

        msg_rows = conn.execute(
            "SELECT * FROM persistent_messages WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,),
        ).fetchall()

        messages = []
        for mr in msg_rows:
            tool_calls = None
            if mr["tool_calls_json"]:
                try:
                    tool_calls = [ToolCall(**tc) for tc in json.loads(mr["tool_calls_json"])]
                except Exception:
                    pass

            messages.append(
                ChatMessage(
                    id=mr["id"],
                    role=MessageRole(mr["role"]),
                    content=mr["content"],
                    name=mr["name"],
                    tool_calls=tool_calls,
                    tool_call_id=mr["tool_call_id"],
                    timestamp=datetime.fromisoformat(mr["timestamp"]),
                    metadata=json.loads(mr["metadata_json"] or "{}"),
                )
            )

        return SessionState(
            session_id=sess_row["session_id"],
            title=sess_row["title"],
            created_at=datetime.fromisoformat(sess_row["created_at"]),
            updated_at=datetime.fromisoformat(sess_row["updated_at"]),
            messages=messages,
            metadata=json.loads(sess_row["metadata_json"] or "{}"),
        )
