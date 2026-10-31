"""Audio Engine Interfaces (STT, TTS) and Offline Mock Engine."""

import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
from pydantic import BaseModel, Field

from jarvis.providers.base import CancellationToken


class AudioBuffer(BaseModel):
    """Raw PCM or WAV audio buffer."""
    data: bytes
    sample_rate: int = 24000
    channels: int = 1
    duration_ms: float = 0.0


class BaseSTT(ABC):
    """Abstract Speech-To-Text Recognizer."""

    @abstractmethod
    async def transcribe(self, audio: AudioBuffer, cancellation_token: Optional[CancellationToken] = None) -> str:
        """Transcribe an audio buffer into text."""
        pass


class BaseTTS(ABC):
    """Abstract Text-To-Speech Synthesizer."""

    @abstractmethod
    async def synthesize(self, text: str, cancellation_token: Optional[CancellationToken] = None) -> AudioBuffer:
        """Synthesize text into a single audio buffer."""
        pass

    @abstractmethod
    async def synthesize_stream(
        self, text: str, cancellation_token: Optional[CancellationToken] = None
    ) -> AsyncIterator[AudioBuffer]:
        """Stream synthesized audio chunks."""
        pass


class MockSTT(BaseSTT):
    """Deterministic Speech-To-Text simulator for automated tests."""

    def __init__(self, default_transcript: str = "Hello Jarvis, what is the weather today?") -> None:
        self.default_transcript = default_transcript
        self.transcriptions_performed = 0

    async def transcribe(self, audio: AudioBuffer, cancellation_token: Optional[CancellationToken] = None) -> str:
        if cancellation_token:
            cancellation_token.raise_if_cancelled()
        self.transcriptions_performed += 1
        # If explicitly prefixed with transcript:, use it
        if audio.data.startswith(b"transcript:"):
            return audio.data[11:].decode("utf-8", errors="replace").strip()
        return self.default_transcript


class MockTTS(BaseTTS):
    """Deterministic Text-To-Speech simulator for automated tests."""

    def __init__(self, sample_rate: int = 24000) -> None:
        self.sample_rate = sample_rate
        self.synthesis_calls = 0

    async def synthesize(self, text: str, cancellation_token: Optional[CancellationToken] = None) -> AudioBuffer:
        if cancellation_token:
            cancellation_token.raise_if_cancelled()
        self.synthesis_calls += 1
        # Create synthetic audio bytes (16-bit PCM silence/tone)
        pcm_data = b"\x00\x00" * int(self.sample_rate * 0.1)  # 100ms
        return AudioBuffer(
            data=pcm_data,
            sample_rate=self.sample_rate,
            channels=1,
            duration_ms=100.0,
        )

    async def synthesize_stream(
        self, text: str, cancellation_token: Optional[CancellationToken] = None
    ) -> AsyncIterator[AudioBuffer]:
        if cancellation_token:
            cancellation_token.raise_if_cancelled()

        # Split text into small chunks and yield simulated audio
        words = text.split()
        for word in words:
            if cancellation_token:
                cancellation_token.raise_if_cancelled()
            await asyncio.sleep(0.01)  # simulate rendering time
            pcm_data = word.encode("utf-8")
            yield AudioBuffer(
                data=pcm_data,
                sample_rate=self.sample_rate,
                channels=1,
                duration_ms=50.0,
            )


class KokoroTTS(BaseTTS):
    """Local, lightweight Kokoro 82M Text-To-Speech engine."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        voices_path: Optional[str] = None,
        voice: str = "af_sarah",
        sample_rate: int = 24000,
    ) -> None:
        from pathlib import Path
        self.sample_rate = sample_rate
        self.voice = voice
        self.model_path = Path(model_path) if model_path else Path("data/models/kokoro/kokoro-v0_19.onnx")
        self.voices_path = Path(voices_path) if voices_path else Path("data/models/kokoro/voices-v1.0.bin")
        self._kokoro = None
        self._load_engine()

    def _load_engine(self) -> None:
        """Attempt to load the Kokoro ONNX model session if weights are present."""
        if not self.model_path.exists():
            return
        if not self.voices_path.exists():
            alt_voices = self.voices_path.parent / "voices.bin"
            if alt_voices.exists():
                self.voices_path = alt_voices
            else:
                return
        try:
            import kokoro_onnx
            self._kokoro = kokoro_onnx.Kokoro(
                model_path=str(self.model_path),
                voices_path=str(self.voices_path),
            )
        except Exception:
            self._kokoro = None

    @property
    def is_model_available(self) -> bool:
        """Check if local 82M weights are loaded and ready."""
        return self._kokoro is not None

    async def synthesize(self, text: str, cancellation_token: Optional[CancellationToken] = None) -> AudioBuffer:
        if cancellation_token:
            cancellation_token.raise_if_cancelled()

        if self._kokoro is not None:
            try:
                import io
                import soundfile as sf
                loop = asyncio.get_event_loop()
                samples, sample_rate = await loop.run_in_executor(
                    None, lambda: self._kokoro.create(text=text, voice=self.voice, speed=1.0)
                )
                buf = io.BytesIO()
                sf.write(buf, samples, sample_rate, format="WAV")
                wav_bytes = buf.getvalue()
                return AudioBuffer(
                    data=wav_bytes,
                    sample_rate=sample_rate,
                    channels=1,
                    duration_ms=len(samples) / sample_rate * 1000.0,
                )
            except Exception:
                pass

        # Fallback synthetic WAV generator when offline/un-downloaded
        return await self._synthesize_fallback(text, cancellation_token)

    async def _synthesize_fallback(self, text: str, cancellation_token: Optional[CancellationToken] = None) -> AudioBuffer:
        """Generate audible WAV container audio buffer as fallback."""
        import io
        import sys
        if sys.platform == "darwin":
            try:
                import os
                import tempfile
                import subprocess
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    tmp_wav = tf.name
                res = subprocess.run(
                    ["say", "-o", tmp_wav, "--data-format=LEI16@24000", text[:300]],
                    timeout=5,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if res.returncode == 0 and os.path.exists(tmp_wav):
                    data = Path(tmp_wav).read_bytes()
                    try:
                        os.unlink(tmp_wav)
                    except OSError:
                        pass
                    if len(data) > 44:
                        return AudioBuffer(
                            data=data,
                            sample_rate=24000,
                            channels=1,
                            duration_ms=(len(data) - 44) / 48.0,
                        )
            except Exception:
                pass

        import wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            # Generate short audio frame buffer
            samples_count = int(self.sample_rate * 0.15)
            wav_file.writeframes(b"\x00\x00" * samples_count)
        return AudioBuffer(
            data=buf.getvalue(),
            sample_rate=self.sample_rate,
            channels=1,
            duration_ms=150.0,
        )

    async def synthesize_stream(
        self, text: str, cancellation_token: Optional[CancellationToken] = None
    ) -> AsyncIterator[AudioBuffer]:
        if cancellation_token:
            cancellation_token.raise_if_cancelled()

        # Generate audio buffer for the given sentence
        chunk = await self.synthesize(text, cancellation_token=cancellation_token)
        yield chunk
