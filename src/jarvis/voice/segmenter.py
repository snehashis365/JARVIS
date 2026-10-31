"""Sentence Segmenter for Low-Latency Streaming Audio Synthesis."""

import re
from typing import AsyncIterator, List


# Regex matching sentence terminal punctuation followed by whitespace or end of string
SENTENCE_TERMINATORS = re.compile(r"([.!?]+(?:\s+|\n+|$))")


class SentenceSegmenter:
    """Accumulates text tokens and emits completed sentences for incremental TTS."""

    def __init__(self) -> None:
        self.buffer = ""

    def feed(self, text_chunk: str) -> List[str]:
        """Feed a new text chunk and return any completed sentences."""
        self.buffer += text_chunk
        sentences = []

        parts = SENTENCE_TERMINATORS.split(self.buffer)
        if len(parts) > 1:
            # Pair sentence text with its punctuation
            i = 0
            while i < len(parts) - 1:
                sentence_text = parts[i] + parts[i + 1]
                sentence_clean = sentence_text.strip()
                if sentence_clean:
                    sentences.append(sentence_clean)
                i += 2
            # Remaining incomplete fragment stays in buffer
            self.buffer = parts[-1]

        return sentences

    def flush(self) -> List[str]:
        """Flush remaining buffered text as a final sentence."""
        remaining = self.buffer.strip()
        self.buffer = ""
        if remaining:
            return [remaining]
        return []
