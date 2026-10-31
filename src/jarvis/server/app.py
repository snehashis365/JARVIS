"""FastAPI Server Application for Jarvis Assistant."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from jarvis import __version__
from jarvis.config import Settings, settings
from jarvis.config_manager import ConfigManager, JarvisConfig
from jarvis.core.detector import LocalLLMDetector, LocalLLMServerInfo
from jarvis.core.orchestrator import TaskOrchestrator
from jarvis.core.session import SessionManager
from jarvis.logging import logger, setup_logging
from jarvis.models import ChatMessage, MessageRole, SessionState, TaskState
from jarvis.models.messages import ToolCall, ToolResult
from jarvis.providers.mock import MockProvider
from jarvis.memory.manager import MemoryManager
from jarvis.memory.models import MemoryCategory, MemoryItem
from jarvis.security.permissions import ApprovalRequest, PermissionManager
from jarvis.sync.client import SyncClient
from jarvis.sync.models import DeviceRecord
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.skills.manager import SkillManager
from jarvis.voice.personality import PersonalityManager, PersonalityProfile
from jarvis.voice.pipeline import VoicePipeline


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    force_fast_path: bool = False


class ApprovalResolutionRequest(BaseModel):
    approved: bool


class ChatResponse(BaseModel):
    session_id: str
    response: str
    role: str = "assistant"
    route: Optional[str] = None


class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Conversation"


class CreateMemoryRequest(BaseModel):
    category: str
    title: str
    content: str
    confidence: float = 1.0
    tags: List[str] = Field(default_factory=list)


class UpdateMemoryRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    confidence: Optional[float] = None
    tags: Optional[List[str]] = None


class UpdatePersonalityRequest(BaseModel):
    name: Optional[str] = None
    tone: Optional[str] = None
    humor: Optional[float] = None
    proactivity: Optional[float] = None
    custom_instructions: Optional[str] = None


class RegisterDeviceRequest(BaseModel):
    device_name: str


class DetectRequest(BaseModel):
    custom_endpoint: Optional[str] = None


class DirectToolExecuteRequest(BaseModel):
    tool_name: Optional[str] = None
    name: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    approval_token: Optional[str] = None
    session_id: Optional[str] = None


session_manager = SessionManager()
orchestrator = TaskOrchestrator(session_manager=session_manager)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan setup and teardown."""
    setup_logging(
        log_level=settings.log_level,
        log_dir=settings.logs_dir,
        log_to_file=True
    )
    logger.info("Jarvis assistant server starting up...")
    logger.info("Operating mode: %s, Autonomy: %s", settings.inference_mode.value, settings.autonomy_mode.value)
    yield
    logger.info("Jarvis assistant server shutting down cleanly.")


def create_app(
    app_settings: Optional[Settings] = None,
    custom_orchestrator: Optional[TaskOrchestrator] = None,
    custom_session_manager: Optional[SessionManager] = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    cfg = app_settings or settings
    sm = custom_session_manager or session_manager
    orch = custom_orchestrator or TaskOrchestrator(
        session_manager=sm,
        app_settings=cfg,
    )

    app = FastAPI(
        title="Jarvis Assistant API",
        version=__version__,
        description="Desktop-first modular personal AI assistant",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.session_manager = sm
    app.state.orchestrator = orch
    app.state.settings = cfg
    permission_manager = PermissionManager(app_settings=cfg)
    app.state.permission_manager = permission_manager
    tool_registry = ToolRegistry(permission_manager=permission_manager)
    orch.tool_registry = tool_registry
    orch.tool_executor = tool_registry.execute_tool
    skill_manager = SkillManager()
    memory_manager = MemoryManager()
    personality_manager = PersonalityManager(app_settings=cfg)
    orch.personality_manager = personality_manager
    orch.memory_manager = memory_manager
    voice_pipeline = VoicePipeline(orchestrator=orch)
    sync_client = SyncClient(app_settings=cfg)
    config_manager = ConfigManager(app_settings=cfg)
    detector = LocalLLMDetector()

    # If configuration exists, apply to settings
    if config_manager.is_configured():
        loaded_cfg = config_manager.load()
        config_manager.apply_to_settings(loaded_cfg, cfg)

    app.state.tool_registry = tool_registry
    app.state.skill_manager = skill_manager
    app.state.memory_manager = memory_manager
    app.state.personality_manager = personality_manager
    app.state.voice_pipeline = voice_pipeline
    app.state.sync_client = sync_client
    app.state.config_manager = config_manager
    app.state.detector = detector

    @app.get("/api/setup/status")
    async def get_setup_status() -> Dict[str, Any]:
        """Check whether initial configuration has been completed."""
        is_conf = config_manager.is_configured()
        current_cfg = config_manager.load()
        return {
            "is_configured": is_conf,
            "config": current_cfg.model_dump(),
        }

    @app.post("/api/setup/detect", response_model=List[LocalLLMServerInfo])
    async def detect_local_llms(req: Optional[DetectRequest] = None) -> List[LocalLLMServerInfo]:
        """Auto-detect running local LLM engines (Ollama, LM Studio, llama.cpp, custom)."""
        results = await detector.detect_all()
        if req and req.custom_endpoint:
            custom_info = await detector.probe_custom_endpoint(req.custom_endpoint)
            results.append(custom_info)
        return results

    @app.post("/api/setup/save")
    async def save_setup(cfg_input: JarvisConfig) -> Dict[str, Any]:
        """Save configuration from initial setup GUI, persist to file, and apply."""
        saved = config_manager.save(cfg_input)
        personality_manager.update_profile(
            name=saved.assistant_name,
            tone=saved.tone,
        )
        return {"success": True, "config": saved.model_dump()}

    @app.post("/api/setup/reset")
    async def reset_setup() -> Dict[str, bool]:
        """Reset configuration state."""
        config_manager.reset()
        return {"reset": True}

    @app.get("/api/sync/status")
    async def get_sync_status() -> Dict[str, Any]:
        """Retrieve decoupled sync status."""
        return {
            "sync_enabled": sync_client.is_enabled,
            "device_id": sync_client.local_device.device_id,
            "device_name": sync_client.local_device.device_name,
            "registered_devices_count": len(sync_client.list_devices()),
        }

    @app.get("/api/sync/devices", response_model=List[DeviceRecord])
    async def list_sync_devices() -> List[DeviceRecord]:
        """List registered peer devices."""
        return sync_client.list_devices()

    @app.post("/api/sync/devices", response_model=DeviceRecord)
    async def register_sync_device(req: RegisterDeviceRequest) -> DeviceRecord:
        """Register a new sync peer device."""
        return sync_client.register_device(req.device_name)

    @app.delete("/api/sync/devices/{device_id}")
    async def revoke_sync_device(device_id: str) -> Dict[str, bool]:
        """Revoke a peer sync device."""
        ok = sync_client.revoke_device(device_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Device not found or cannot revoke primary.")
        return {"revoked": True}

    @app.get("/api/personality", response_model=PersonalityProfile)
    async def get_personality() -> PersonalityProfile:
        """Retrieve active personality and identity settings."""
        return personality_manager.get_profile()

    @app.put("/api/personality", response_model=PersonalityProfile)
    async def update_personality(req: UpdatePersonalityRequest) -> PersonalityProfile:
        """Update personality and identity settings."""
        return personality_manager.update_profile(
            name=req.name,
            tone=req.tone,
            humor=req.humor,
            proactivity=req.proactivity,
            custom_instructions=req.custom_instructions,
        )

    @app.post("/api/voice/interrupt")
    async def voice_interrupt() -> Dict[str, str]:
        """Trigger barge-in speech interruption."""
        voice_pipeline.interrupt()
        return {"status": "interrupted"}

    @app.get("/api/voice/status")
    async def get_voice_status() -> Dict[str, str]:
        """Get voice pipeline state."""
        return {"state": voice_pipeline.state.value}

    @app.post("/api/voice/transcribe")
    async def voice_transcribe(req: Dict[str, Any]) -> Dict[str, str]:
        """Transcribe voice input."""
        text = req.get("text", "")
        return {"transcript": text or "Voice transcript processed"}

    @app.post("/api/voice/synthesize")
    async def voice_synthesize(req: Dict[str, Any]) -> Response:
        """Synthesize speech using Kokoro 82M / local TTS engine."""
        text = req.get("text", "")
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text is required for TTS synthesis.")
        audio_buf = await voice_pipeline.tts.synthesize(text)
        is_neural = getattr(voice_pipeline.tts, "is_model_available", False)
        return Response(
            content=audio_buf.data,
            media_type="audio/wav",
            headers={
                "X-Audio-Synthesized": "kokoro-82m" if is_neural else "fallback",
                "X-Audio-Duration-Ms": str(audio_buf.duration_ms),
            },
        )

    @app.get("/api/memories", response_model=List[MemoryItem])
    async def list_or_search_memories(
        query: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryItem]:
        """List or search stored memories using FTS5."""
        cat_enum = MemoryCategory(category) if category else None
        if query:
            return memory_manager.search(query=query, category=cat_enum, limit=limit)
        return memory_manager.list_memories(category=cat_enum, limit=limit)

    @app.post("/api/memories", response_model=MemoryItem)
    async def create_memory(req: CreateMemoryRequest) -> MemoryItem:
        """Create a new structured memory item."""
        try:
            cat = MemoryCategory(req.category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category '{req.category}'.")
        return memory_manager.store(
            category=cat,
            title=req.title,
            content=req.content,
            confidence=req.confidence,
            tags=req.tags,
        )

    @app.get("/api/memories/{memory_id}", response_model=MemoryItem)
    async def get_memory(memory_id: str) -> MemoryItem:
        """Retrieve a specific memory item."""
        item = memory_manager.get(memory_id)
        if not item:
            raise HTTPException(status_code=404, detail="Memory item not found")
        return item

    @app.put("/api/memories/{memory_id}", response_model=MemoryItem)
    async def update_memory(memory_id: str, req: UpdateMemoryRequest) -> MemoryItem:
        """Update an existing memory item."""
        updated = memory_manager.update(
            memory_id=memory_id,
            title=req.title,
            content=req.content,
            confidence=req.confidence,
            tags=req.tags,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Memory item not found")
        return updated

    @app.delete("/api/memories/{memory_id}")
    async def delete_memory(memory_id: str) -> Dict[str, bool]:
        """Delete a memory item."""
        deleted = memory_manager.delete(memory_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Memory item not found")
        return {"deleted": True}

    @app.get("/api/tools")
    async def list_tools() -> List[Dict[str, Any]]:
        """List registered tools and schemas."""
        return tool_registry.get_schemas()

    @app.post("/api/tools/execute", response_model=ToolResult)
    async def execute_tool_direct(req: DirectToolExecuteRequest) -> ToolResult:
        """Directly invoke a registered tool through deterministic security enforcement."""
        tool_name = req.tool_name or req.name or ""
        if not tool_name:
            raise HTTPException(status_code=400, detail="Missing tool name ('tool_name' or 'name' required).")
        tc = ToolCall(
            tool_name=tool_name,
            arguments=req.arguments,
        )
        return await tool_registry.execute_tool(
            tool_call=tc,
            session_id=req.session_id,
            approval_token=req.approval_token,
        )

    @app.get("/api/audit/logs")
    async def get_audit_logs(limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent security audit records."""
        records = permission_manager.audit_logger.get_records(limit=limit)
        return [r.model_dump() for r in records]

    @app.get("/api/skills")
    async def list_skills() -> List[Dict[str, Any]]:
        """List installed skills."""
        return [s.model_dump() for s in skill_manager.list_skills()]

    @app.post("/api/skills/{skill_name}/enable")
    async def enable_skill(skill_name: str) -> Dict[str, bool]:
        """Enable a skill."""
        ok = skill_manager.enable(skill_name)
        if not ok:
            raise HTTPException(status_code=404, detail="Skill not found")
        return {"enabled": True}

    @app.post("/api/skills/{skill_name}/disable")
    async def disable_skill(skill_name: str) -> Dict[str, bool]:
        """Disable a skill."""
        ok = skill_manager.disable(skill_name)
        if not ok:
            raise HTTPException(status_code=404, detail="Skill not found")
        return {"disabled": True}

    @app.get("/api/approvals", response_model=List[ApprovalRequest])
    async def list_pending_approvals() -> List[ApprovalRequest]:
        """List active pending permission approval requests."""
        return permission_manager.get_pending_approvals()

    @app.post("/api/approvals/{request_id}")
    @app.post("/api/approvals/{request_id}/resolve")
    async def resolve_approval(request_id: str, req: ApprovalResolutionRequest) -> Dict[str, Any]:
        """Approve or reject a pending security approval request and execute if approved."""
        try:
            approval = permission_manager.resolve_approval(request_id=request_id, approved=req.approved)
            tool_result_data = None
            if req.approved:
                # Dispatch the approved tool action immediately with the approved token
                tc = ToolCall(
                    tool_name=approval.tool_name,
                    arguments=approval.parameters,
                )
                res = await tool_registry.execute_tool(
                    tool_call=tc,
                    session_id=None,
                    approval_token=request_id,
                )
                tool_result_data = res.model_dump()

            return {
                "request_id": request_id,
                "status": approval.status,
                "tool_name": approval.tool_name,
                "tool_result": tool_result_data,
            }
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/health")
    async def health_check() -> Dict[str, Any]:
        """Health check and runtime status."""
        return {
            "status": "healthy",
            "version": __version__,
            "inference_mode": cfg.inference_mode.value,
            "autonomy_mode": cfg.autonomy_mode.value,
            "assistant_name": cfg.assistant_name,
        }

    @app.get("/api/config")
    async def get_config() -> Dict[str, Any]:
        """Retrieve public, safe configuration settings without secrets."""
        return {
            "version": __version__,
            "assistant_name": cfg.assistant_name,
            "tone": cfg.tone,
            "formality": cfg.formality.value,
            "verbosity": cfg.verbosity.value,
            "inference_mode": cfg.inference_mode.value,
            "autonomy_mode": cfg.autonomy_mode.value,
            "local_endpoint": cfg.local_endpoint,
            "local_model": cfg.local_model,
            "max_orchestrator_steps": cfg.max_orchestrator_steps,
            "sync_enabled": cfg.sync_enabled,
        }

    @app.get("/api/sessions", response_model=List[SessionState])
    async def list_sessions() -> List[SessionState]:
        """List active conversation sessions."""
        return sm.list_sessions()

    @app.post("/api/sessions", response_model=SessionState)
    async def create_session(req: CreateSessionRequest) -> SessionState:
        """Create a new conversation session."""
        return sm.create_session(title=req.title or "New Conversation")

    @app.get("/api/sessions/{session_id}", response_model=SessionState)
    async def get_session(session_id: str) -> SessionState:
        """Retrieve a specific session by ID."""
        session = sm.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str) -> Dict[str, bool]:
        """Delete a conversation session."""
        deleted = sm.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"deleted": True}

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat_endpoint(req: ChatRequest) -> ChatResponse:
        """Standard chat endpoint executing through TaskOrchestrator."""
        session_id = req.session_id
        if not session_id or not sm.get_session(session_id):
            session = sm.create_session(title=req.message[:30])
            session_id = session.session_id

        reply_content = ""
        route_used = "local"

        async for event in orch.execute(
            session_id=session_id,
            user_prompt=req.message,
            force_fast_path=req.force_fast_path,
        ):
            if event.event_type == "route":
                route_used = event.data.get("route", "local")
            elif event.event_type == "done":
                reply_content = event.data.get("content", "")
            elif event.event_type == "error":
                reply_content = f"Error: {event.data.get('error')}"

        return ChatResponse(
            session_id=session_id,
            response=reply_content,
            route=route_used,
        )

    @app.post("/api/chat/stream")
    async def chat_stream_endpoint(req: ChatRequest) -> StreamingResponse:
        """Server-Sent Events endpoint streaming real-time tokens and events."""
        session_id = req.session_id
        if not session_id or not sm.get_session(session_id):
            session = sm.create_session(title=req.message[:30])
            session_id = session.session_id

        async def sse_generator() -> AsyncGenerator[str, None]:
            async for event in orch.execute(
                session_id=session_id,
                user_prompt=req.message,
                force_fast_path=req.force_fast_path,
            ):
                payload = json.dumps(event.model_dump(), default=str)
                yield f"data: {payload}\n\n"

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    # Static UI serving
    static_dir = Path(__file__).parent / "static"

    @app.get("/")
    async def serve_index() -> FileResponse:
        """Serve the embedded web application interface."""
        index_path = static_dir / "index.html"
        if not index_path.exists():
            return JSONResponse({"message": "Jarvis API is running. UI not found."})
        return FileResponse(index_path)

    return app


app = create_app()
