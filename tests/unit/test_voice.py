"""Unit tests for Phase 7 Personality and Voice Pipeline.

Verifies PersonalityProfile, prompt compilation, SentenceSegmenter,
MockSTT/MockTTS, VoicePipeline streaming, barge-in interruption, and REST endpoints.
"""

import asyncio
import pytest

from jarvis.config import FormalityLevel, Settings, VerbosityLevel
from jarvis.core.orchestrator import TaskOrchestrator
from jarvis.core.session import SessionManager
from jarvis.providers.mock import MockProvider
from jarvis.voice.audio import AudioBuffer, MockSTT, MockTTS
from jarvis.voice.personality import PersonalityManager, PersonalityProfile
from jarvis.voice.pipeline import VoicePipeline, VoiceState
from jarvis.voice.segmenter import SentenceSegmenter


def test_personality_manager_and_prompt_compilation():
    """Verify personality profile customization and system prompt compilation."""
    mgr = PersonalityManager()
    profile = mgr.get_profile()
    assert profile.name == "Jarvis"

    # Update profile
    mgr.update_profile(
        name="Athena",
        tone="sharp and witty",
        formality=FormalityLevel.FORMAL,
        verbosity=VerbosityLevel.DETAILED,
        humor=0.7,
        custom_instructions="Always cite ISO dates."
    )
    updated = mgr.get_profile()
    assert updated.name == "Athena"
    assert updated.humor == 0.7

    # Compile prompt
    prompt = mgr.compile_system_prompt(skill_guidelines="Guideline: analyze code before writing.")
    assert "Athena" in prompt
    assert "sharp and witty" in prompt
    assert "Always cite ISO dates." in prompt
    assert "Guideline: analyze code before writing." in prompt


def test_sentence_segmenter():
    """Verify streaming token chunking into complete sentences."""
    segmenter = SentenceSegmenter()

    # Feed fragment
    s1 = segmenter.feed("Hello there! ")
    assert s1 == ["Hello there!"]

    # Incomplete sentence
    s2 = segmenter.feed("I am currently processing ")
    assert s2 == []

    # Completing sentence
    s3 = segmenter.feed("your data. How can ")
    assert s3 == ["I am currently processing your data."]

    # Final sentence and flush
    s4 = segmenter.feed("I assist?")
    assert s4 == ["How can I assist?"]
    assert segmenter.flush() == []

    # Unpunctuated trailing text flush
    segmenter.feed("Trailing fragment without punctuation")
    flushed = segmenter.flush()
    assert flushed == ["Trailing fragment without punctuation"]


@pytest.mark.asyncio
async def test_mock_audio_engines():
    """Verify MockSTT transcription and MockTTS synthesis."""
    stt = MockSTT(default_transcript="Transcribed user voice.")
    audio = AudioBuffer(data=b"dummy audio pcm data", sample_rate=24000)

    transcript = await stt.transcribe(audio)
    assert transcript == "Transcribed user voice."

    tts = MockTTS()
    single_buf = await tts.synthesize("Synthesize this.")
    assert len(single_buf.data) > 0

    chunks = []
    async for chunk in tts.synthesize_stream("One two three"):
        chunks.append(chunk)
    assert len(chunks) == 3


@pytest.mark.asyncio
async def test_voice_pipeline_flow_and_barge_in(session_manager: SessionManager):
    """Verify VoicePipeline streaming audio output and barge-in cancellation."""
    mock_provider = MockProvider(default_response="First sentence. Second sentence! Third sentence.")
    orchestrator = TaskOrchestrator(session_manager=session_manager, provider=mock_provider)

    pipeline = VoicePipeline(
        orchestrator=orchestrator,
        stt=MockSTT(default_transcript="Run voice query"),
        tts=MockTTS(),
    )
    session = session_manager.create_session()

    audio_input = AudioBuffer(data=b"user_speech_bytes")

    # 1. Successful speech processing flow
    audio_output_chunks = []
    async for chunk in pipeline.process_speech(audio_input, session_id=session.session_id):
        audio_output_chunks.append(chunk)

    assert len(audio_output_chunks) > 0
    assert pipeline.state == VoiceState.IDLE

    # 2. Barge-in Interruption test
    interrupted_pipeline = VoicePipeline(
        orchestrator=orchestrator,
        stt=MockSTT(default_transcript="Long voice response prompt"),
        tts=MockTTS(),
    )

    async def run_and_interrupt():
        # Schedule immediate interruption after a slight yield
        async def interrupt_soon():
            await asyncio.sleep(0.01)
            interrupted_pipeline.interrupt()

        asyncio.create_task(interrupt_soon())

        chunks_received = 0
        async for _ in interrupted_pipeline.process_speech(audio_input, session_id=session.session_id):
            chunks_received += 1
        return chunks_received

    await run_and_interrupt()
    assert interrupted_pipeline.state == VoiceState.INTERRUPTED


@pytest.mark.asyncio
async def test_personality_api_endpoints(async_client):
    """Verify /api/personality and /api/voice/interrupt REST endpoints."""
    # 1. Get personality
    res = await async_client.get("/api/personality")
    assert res.status_code == 200
    profile = res.json()
    assert "name" in profile
    assert "tone" in profile

    # 2. Update personality
    update_res = await async_client.put("/api/personality", json={
        "name": "CustomJarvis",
        "tone": "hyper-focused"
    })
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "CustomJarvis"

    # 3. Trigger barge-in interrupt
    int_res = await async_client.post("/api/voice/interrupt")
    assert int_res.status_code == 200
    assert int_res.json()["status"] == "interrupted"

    # 4. Kokoro 82M TTS Synthesize endpoint
    synth_res = await async_client.post("/api/voice/synthesize", json={"text": "Hello world from Kokoro"})
    assert synth_res.status_code == 200
    assert synth_res.headers["content-type"] == "audio/wav"
    assert len(synth_res.content) > 44  # Valid WAV header + frames
