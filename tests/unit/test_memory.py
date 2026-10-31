"""Unit tests for Phase 6 Memory and Continuity Management.

Verifies SQLite persistence, FTS5 full-text search, memory categories,
editing/deletion controls, context budgeting/summarization, and REST APIs.
"""

from pathlib import Path
import pytest

from jarvis.memory.database import Database
from jarvis.memory.manager import MemoryManager
from jarvis.memory.models import MemoryCategory, MemoryItem
from jarvis.memory.summarizer import ContextBudgetManager, estimate_messages_tokens, estimate_tokens
from jarvis.models.messages import ChatMessage, MessageRole
from jarvis.models.session import SessionState


def test_database_initialization():
    """Verify SQLite database initialization and schema migrations in memory."""
    db = Database(db_path=None)
    conn = db.get_connection()
    tables = [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    assert "memories" in tables
    assert "memories_fts" in tables
    assert "persistent_sessions" in tables
    assert "persistent_messages" in tables
    db.close()


def test_memory_crud_and_fts_search():
    """Verify memory creation, full-text retrieval, updating, and deletion."""
    db = Database(db_path=None)
    mm = MemoryManager(database=db)

    # 1. Store memories in different categories
    mem1 = mm.store(
        category=MemoryCategory.PREFERENCE,
        title="Coding Style",
        content="User prefers Python 3.12 with strict type hinting and PEP 8 formatting.",
        tags=["python", "style"]
    )
    assert mem1.id is not None

    mem2 = mm.store(
        category=MemoryCategory.FACT,
        title="Project Name",
        content="Jarvis is a modular desktop personal assistant.",
        tags=["jarvis", "project"]
    )

    mem3 = mm.store(
        category=MemoryCategory.EPISODIC,
        title="Refactoring Completed",
        content="Successfully refactored provider adapters into modular monolith.",
        tags=["refactor"]
    )

    # 2. Retrieval by ID
    fetched = mm.get(mem1.id)
    assert fetched is not None
    assert fetched.title == "Coding Style"

    # 3. Full-text search via FTS5
    results_python = mm.search("Python")
    assert len(results_python) >= 1
    assert any("Python" in r.content for r in results_python)

    results_assistant = mm.search("modular desktop")
    assert len(results_assistant) >= 1
    assert results_assistant[0].id == mem2.id

    # Filtered search by category
    results_pref = mm.search("Python", category=MemoryCategory.PREFERENCE)
    assert len(results_pref) == 1
    assert results_pref[0].category == MemoryCategory.PREFERENCE

    # 4. Update memory
    updated = mm.update(mem1.id, content="User prefers Python 3.12, strict types, and Ruff linter.")
    assert updated is not None
    assert "Ruff linter" in updated.content

    # Verify FTS5 updated accordingly
    results_ruff = mm.search("Ruff")
    assert len(results_ruff) == 1
    assert results_ruff[0].id == mem1.id

    # 5. Delete memory
    assert mm.delete(mem3.id) is True
    assert mm.get(mem3.id) is None
    # FTS5 search should no longer find it
    assert len(mm.search("Refactoring")) == 0

    # 6. Clear category
    cleared_count = mm.clear_category(MemoryCategory.FACT)
    assert cleared_count == 1
    assert len(mm.list_memories(category=MemoryCategory.FACT)) == 0

    db.close()


def test_session_continuity_persistence():
    """Verify storing and restoring conversation sessions and message history."""
    db = Database(db_path=None)
    mm = MemoryManager(database=db)

    session = SessionState(title="Persistent Chat")
    session.messages.append(ChatMessage(role=MessageRole.USER, content="Hello persistence!"))
    session.messages.append(ChatMessage(role=MessageRole.ASSISTANT, content="Hello! I am persisted in SQLite."))

    # Persist session
    mm.persist_session(session)

    # Restore session
    restored = mm.load_session(session.session_id)
    assert restored is not None
    assert restored.title == "Persistent Chat"
    assert len(restored.messages) == 2
    assert restored.messages[0].content == "Hello persistence!"
    assert restored.messages[1].content == "Hello! I am persisted in SQLite."

    db.close()


def test_context_budget_summarization():
    """Verify ContextBudgetManager estimates tokens and prunes history with summary."""
    budget_mgr = ContextBudgetManager(max_context_tokens=100, target_budget_ratio=0.7)

    system_msg = ChatMessage(role=MessageRole.SYSTEM, content="You are Jarvis.")
    messages = [system_msg]

    # Generate 15 conversational turns
    for i in range(15):
        messages.append(ChatMessage(role=MessageRole.USER, content=f"User question turn number {i} with some extra padding text"))
        messages.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"Assistant answer turn number {i} providing detailed helpful response"))

    initial_tokens = estimate_messages_tokens(messages)
    assert initial_tokens > budget_mgr.target_budget

    # Prune and summarize
    budgeted = budget_mgr.prune_and_summarize(messages, preserve_recent=4)
    assert len(budgeted) < len(messages)
    assert budgeted[0].content == "You are Jarvis."  # System message preserved
    assert "[Executive Summary of Prior Context]" in budgeted[1].content  # Summary inserted
    assert budgeted[-1].content == messages[-1].content  # Most recent message preserved


@pytest.mark.asyncio
async def test_memories_api_endpoints(async_client):
    """Verify /api/memories REST endpoints for CRUD and search."""
    # 1. Create memory
    create_res = await async_client.post("/api/memories", json={
        "category": "fact",
        "title": "API Test Fact",
        "content": "Testing memory persistence via HTTP API",
        "tags": ["api", "test"]
    })
    assert create_res.status_code == 200
    created = create_res.json()
    mem_id = created["id"]
    assert created["title"] == "API Test Fact"

    # 2. Get by ID
    get_res = await async_client.get(f"/api/memories/{mem_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "API Test Fact"

    # 3. Search memories
    search_res = await async_client.get("/api/memories?query=HTTP")
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data) >= 1

    # 4. Update memory
    update_res = await async_client.put(f"/api/memories/{mem_id}", json={
        "title": "Updated API Test Fact",
        "content": "Updated content here."
    })
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Updated API Test Fact"

    # 5. Delete memory
    del_res = await async_client.delete(f"/api/memories/{mem_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True
