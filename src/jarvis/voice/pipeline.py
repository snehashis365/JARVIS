"""Real-Time Voice Pipeline with Low-Latency Streaming and Barge-in Interruption."""

import asyncio
from enum import Enum
from typing import AsyncIterator, Optional
from pydantic import BaseModel

from jarvis.core.orchestrator import TaskOrchestrator
from jarvis.providers.base import CancellationToken
from jarvis.voice.audio import AudioBuffer, BaseSTT, BaseTTS, KokoroTTS, MockSTT, MockTTS
from jarvis.voice.segmenter import SentenceSegmenter


class VoiceState(str, Enum):
    """Voice pipeline state machine."""
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


class VoicePipeline:
    """Coordinates speech transcription, orchestration, sentence-segmented TTS, and barge-in."""

    def __init__(
        self,
        orchestrator: TaskOrchestrator,
        stt: Optional[BaseSTT] = None,
        tts: Optional[BaseTTS] = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.stt = stt or MockSTT()
        self.tts = tts or KokoroTTS()
        self.state = VoiceState.IDLE
        self.active_cancellation_token: Optional[CancellationToken] = None

    def interrupt(self) -> None:
        """Immediate barge-in cancellation: aborts active TTS playback and LLM generation."""
        if self.active_cancellation_token and not self.active_cancellation_token.is_cancelled:
            self.active_cancellation_token.cancel()
        self.state = VoiceState.INTERRUPTED

    async def process_speech(
        self, audio: AudioBuffer, session_id: str
    ) -> AsyncIterator[AudioBuffer]:
        """Transcribe speech, orchestrate response, and stream audio chunks."""
        token = CancellationToken()
        self.active_cancellation_token = token
        self.state = VoiceState.TRANSCRIBING

        try:
            # 1. Transcribe speech
            transcript = await self.stt.transcribe(audio, cancellation_token=token)
            if not transcript.strip() or token.is_cancelled:
                self.state = VoiceState.IDLE
                return

            # 2. Orchestrate and Segment
            self.state = VoiceState.THINKING
            segmenter = SentenceSegmenter()

            async for event in self.orchestrator.execute(
                session_id=session_id,
                user_prompt=transcript,
                cancellation_token=token,
            ):
                if token.is_cancelled:
                    break

                if event.event_type == "token":
                    delta = event.data.get("delta", "")
                    sentences = segmenter.feed(delta)
                    for sent in sentences:
                        token.raise_if_cancelled()
                        self.state = VoiceState.SPEAKING
                        async for audio_chunk in self.tts.synthesize_stream(sent, cancellation_token=token):
                            yield audio_chunk

            # Flush any remaining sentence fragment
            remaining_sentences = segmenter.flush()
            for sent in remaining_sentences:
                token.raise_if_cancelled()
                self.state = VoiceState.SPEAKING
                async for audio_chunk in self.tts.synthesize_stream(sent, cancellation_token=token):
                    yield audio_chunk

        except asyncio.CancelledError:
            self.state = VoiceState.INTERRUPTED
        finally:
            if self.state != VoiceState.INTERRUPTED:
                self.state = VoiceState.IDLE
            self.active_cancellation_token = None
