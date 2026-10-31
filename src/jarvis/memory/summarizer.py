"""Context Budgeting and Conversation History Summarizer."""

from typing import List, Tuple
from jarvis.models.messages import ChatMessage, MessageRole


def estimate_tokens(text: str) -> int:
    """Fast character-to-token heuristic (approximately 4 characters per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: List[ChatMessage]) -> int:
    """Estimate total tokens across a list of ChatMessages."""
    total = 0
    for m in messages:
        total += estimate_tokens(m.content)
        if m.tool_calls:
            for tc in m.tool_calls:
                total += estimate_tokens(str(tc.arguments))
    return total


class ContextBudgetManager:
    """Manages context window budgeting and automatic historical summarization."""

    def __init__(self, max_context_tokens: int = 4096, target_budget_ratio: float = 0.75) -> None:
        self.max_context_tokens = max_context_tokens
        self.target_budget = int(max_context_tokens * target_budget_ratio)

    def prune_and_summarize(
        self, messages: List[ChatMessage], preserve_recent: int = 4
    ) -> List[ChatMessage]:
        """Prune and summarize older messages if total tokens exceed target budget."""
        current_tokens = estimate_messages_tokens(messages)
        if current_tokens <= self.target_budget or len(messages) <= preserve_recent + 1:
            return messages

        # Separate system message if first
        system_msg: Optional[ChatMessage] = None
        work_messages = list(messages)
        if work_messages and work_messages[0].role == MessageRole.SYSTEM:
            system_msg = work_messages.pop(0)

        # Split into older messages to summarize and recent messages to keep intact
        split_idx = max(1, len(work_messages) - preserve_recent)
        older_messages = work_messages[:split_idx]
        recent_messages = work_messages[split_idx:]

        # Create structured summary of older turns
        summary_lines = []
        for m in older_messages:
            preview = m.content[:80].replace("\n", " ")
            summary_lines.append(f"- {m.role.value}: {preview}...")

        summary_content = (
            "[Executive Summary of Prior Context]\n"
            + "\n".join(summary_lines)
            + "\n[End of Prior Context Summary]"
        )
        summary_msg = ChatMessage(
            role=MessageRole.SYSTEM,
            content=summary_content,
        )

        result: List[ChatMessage] = []
        if system_msg:
            result.append(system_msg)
        result.append(summary_msg)
        result.extend(recent_messages)

        return result
