"""Session and Task state manager.

Coordinates active sessions, chat histories, and task lifecycles in memory,
with persistence integration hooks.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from jarvis.models import ChatMessage, SessionState, TaskProgress, TaskState, TaskStatus


class SessionManager:
    """Manages active conversation sessions and tasks."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionState] = {}
        self._tasks: Dict[str, TaskState] = {}

    def create_session(self, title: str = "New Conversation") -> SessionState:
        """Create and store a new conversation session."""
        session = SessionState(title=title)
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Retrieve a session by its ID."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[SessionState]:
        """List all known sessions sorted by last updated descending."""
        return sorted(
            self._sessions.values(),
            key=lambda s: s.updated_at,
            reverse=True
        )

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and associated tasks."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            # Remove associated tasks
            tasks_to_remove = [
                tid for tid, task in self._tasks.items() if task.session_id == session_id
            ]
            for tid in tasks_to_remove:
                del self._tasks[tid]
            return True
        return False

    def add_message(self, session_id: str, message: ChatMessage) -> SessionState:
        """Append a message to a session history."""
        session = self.get_session(session_id)
        if not session:
            session = self.create_session()
            session.session_id = session_id
            self._sessions[session_id] = session

        session.messages.append(message)
        session.updated_at = datetime.now(timezone.utc)
        return session

    def get_messages(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """Retrieve messages for a session, optionally limited to the most recent."""
        session = self.get_session(session_id)
        if not session:
            return []
        if limit and limit > 0:
            return session.messages[-limit:]
        return session.messages

    def create_task(
        self, session_id: str, goal: str, max_steps: int = 10
    ) -> TaskState:
        """Create and register a bounded execution task."""
        session = self.get_session(session_id)
        if not session:
            session = self.create_session()
            session.session_id = session_id
            self._sessions[session_id] = session

        task = TaskState(
            session_id=session_id,
            goal=goal,
            max_steps=max_steps,
            status=TaskStatus.PENDING,
        )
        self._tasks[task.task_id] = task
        session.active_task_id = task.task_id
        session.updated_at = datetime.now(timezone.utc)
        return task

    def get_task(self, task_id: str) -> Optional[TaskState]:
        """Retrieve a task by ID."""
        return self._tasks.get(task_id)

    def update_task_progress(
        self, task_id: str, step: int, current_action: str, status: TaskStatus, message: str = ""
    ) -> TaskProgress:
        """Update step progress for a task and return a progress event."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task with id {task_id} not found.")

        task.current_step = step
        task.status = status
        task.updated_at = datetime.now(timezone.utc)

        return TaskProgress(
            task_id=task_id,
            step=step,
            max_steps=task.max_steps,
            current_action=current_action,
            status=status,
            message=message,
        )

    def complete_task(self, task_id: str) -> TaskState:
        """Mark a task as completed."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task with id {task_id} not found.")
        task.status = TaskStatus.COMPLETED
        task.updated_at = datetime.now(timezone.utc)
        session = self.get_session(task.session_id)
        if session and session.active_task_id == task_id:
            session.active_task_id = None
        return task

    def fail_task(self, task_id: str, error_message: str) -> TaskState:
        """Mark a task as failed with an error message."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task with id {task_id} not found.")
        task.status = TaskStatus.FAILED
        task.error_message = error_message
        task.updated_at = datetime.now(timezone.utc)
        session = self.get_session(task.session_id)
        if session and session.active_task_id == task_id:
            session.active_task_id = None
        return task

    def cancel_task(self, task_id: str) -> TaskState:
        """Mark a task as cancelled by user request."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task with id {task_id} not found.")
        task.status = TaskStatus.CANCELLED
        task.updated_at = datetime.now(timezone.utc)
        session = self.get_session(task.session_id)
        if session and session.active_task_id == task_id:
            session.active_task_id = None
        return task
