"""Assistant Core Task Orchestrator.

Manages conversational fast-paths and bounded multi-step tool execution loops
with step budgets, loop detection, timeout enforcement, and cancellation.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.config import Settings, settings
from jarvis.core.session import SessionManager
from jarvis.logging import logger
from jarvis.models.messages import ChatMessage, MessageRole, ToolCall, ToolResult
from jarvis.models.session import TaskProgress, TaskState, TaskStatus
from jarvis.providers.base import BaseLLMProvider, CancellationToken
from jarvis.providers.factory import ProviderFactory
from jarvis.routing.router import ModelRouter, RoutingDecision


class OrchestrationEvent(BaseModel):
    """Event emitted during task execution and streaming."""
    event_type: str  # "route", "token", "tool_call", "tool_result", "progress", "error", "done"
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LoopDetectedError(Exception):
    """Raised when orchestrator detects repeated identical tool calls."""
    pass


class TaskOrchestrator:
    """Core orchestrator executing conversations and bounded tool tasks."""

    def __init__(
        self,
        session_manager: SessionManager,
        router: Optional[ModelRouter] = None,
        provider: Optional[BaseLLMProvider] = None,
        tool_executor: Optional[Callable[[ToolCall], Any]] = None,
        tool_registry: Optional[Any] = None,
        personality_manager: Optional[Any] = None,
        memory_manager: Optional[Any] = None,
        app_settings: Optional[Settings] = None,
    ) -> None:
        self.session_manager = session_manager
        self.settings = app_settings or settings
        self.router = router or ModelRouter(app_settings=self.settings)
        self.provider = provider
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor or (tool_registry.execute_tool if tool_registry else None)
        self.personality_manager = personality_manager
        self.memory_manager = memory_manager

    def compile_system_prompt(self, user_prompt: str = "") -> str:
        """Compose universal, persistent identity prompt with tool and memory awareness."""
        from datetime import datetime
        import platform
        now = datetime.now()
        dt_str = now.strftime("%A, %B %d, %Y %H:%M:%S")
        os_name = platform.system()
        arch = platform.machine()

        name = self.settings.assistant_name
        tone = self.settings.tone
        if self.personality_manager and hasattr(self.personality_manager, "profile"):
            name = self.personality_manager.profile.name or name
            tone = self.personality_manager.profile.tone or tone

        prompt = (
            f"You are {name}, a capable, desktop-first personal AI assistant running locally on the user's computer.\n\n"
            "CRITICAL IDENTITY & BEHAVIORAL DIRECTIVES:\n"
            f"1. Your identity is {name}. You are the user's personal assistant. You are NOT a remote generic language model, and you NEVER refer to yourself as an LLM, language model, or AI developed by OpenAI, Meta, Google, or Alibaba.\n"
            f"2. Tone: {tone}. Be direct, clear, highly competent, and helpful. Never offer unsolicited disclaimers.\n"
            f"3. Local Environment: Executing on {os_name} ({arch}). The current date and time is {dt_str}.\n"
            "4. Tools: You have access to local workspace tools: reading files, writing files, deleting files, listing directories, searching files, web search, fetching URLs, system diagnostics, date/time retrieval, mathematical calculations, and terminal shell execution. When the user requests an action involving files, system, time, or calculations, ALWAYS invoke your tools. Never guess, pretend, or fabricate tool outputs.\n"
            f"5. Always respond in character as {name}."
        )

        if self.memory_manager and hasattr(self.memory_manager, "list_memories"):
            try:
                memories = self.memory_manager.list_memories(limit=10)
                if memories:
                    mem_items = [f"- [{m.category.value}] {m.title}: {m.content}" for m in memories]
                    prompt += "\n\nUSER STORED PREFERENCES & CONTEXT:\n" + "\n".join(mem_items)
            except Exception:
                pass

        return prompt

    def _get_provider(self, decision: RoutingDecision) -> BaseLLMProvider:
        """Resolve LLM provider for the selected route."""
        if self.provider:
            return self.provider
        prefer_cloud = decision.route == "cloud"
        return ProviderFactory.get_provider(
            app_settings=self.settings,
            prefer_cloud=prefer_cloud,
            model_override=decision.model_name,
        )

    def _detect_loop(self, tool_call: ToolCall, history: List[ToolCall]) -> bool:
        """Detect if the same tool call with identical arguments occurred consecutively."""
        if len(history) < 2:
            return False
        # Check last 2 calls
        identical_count = sum(
            1 for prior in history[-2:]
            if prior.tool_name == tool_call.tool_name and prior.arguments == tool_call.arguments
        )
        return identical_count >= 2

    async def execute(
        self,
        session_id: str,
        user_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        force_fast_path: bool = False,
    ) -> AsyncIterator[OrchestrationEvent]:
        """Execute request, streaming real-time tokens and tool events."""
        token = cancellation_token or CancellationToken()

        # 1. Append user message to session
        user_msg = ChatMessage(role=MessageRole.USER, content=user_prompt)
        self.session_manager.add_message(session_id, user_msg)
        messages = self.session_manager.get_messages(session_id)

        # Prepend universal system identity & context prompt
        system_content = self.compile_system_prompt(user_prompt)
        injected_messages = [ChatMessage(role=MessageRole.SYSTEM, content=system_content)]
        for m in messages:
            if m.role != MessageRole.SYSTEM:
                injected_messages.append(m)

        active_tools = tools
        if active_tools is None and not force_fast_path and self.tool_registry:
            active_tools = self.tool_registry.get_schemas()

        # 2. Routing Decision
        force_tools_param = None
        if force_fast_path:
            force_tools_param = False
        elif active_tools is not None and len(active_tools) > 0:
            # Check if prompt requires tools
            force_tools_param = None  # Let router check prompt unless explicit

        decision = self.router.route_request(
            messages,
            force_tools=force_tools_param
        )
        yield OrchestrationEvent(event_type="route", data=decision.model_dump())

        provider = self._get_provider(decision)

        # 3. Fast Path (Conversational, no tools needed)
        if decision.is_fast_path or not active_tools:
            logger.info("Executing conversational fast-path on route '%s'", decision.route)
            accumulated_content = []

            try:
                async for chunk in provider.stream(
                    messages=injected_messages,
                    cancellation_token=token,
                ):
                    if token.is_cancelled:
                        break
                    if chunk.content_delta:
                        accumulated_content.append(chunk.content_delta)
                        yield OrchestrationEvent(
                            event_type="token",
                            data={"delta": chunk.content_delta}
                        )

                full_reply = "".join(accumulated_content)
                assistant_msg = ChatMessage(role=MessageRole.ASSISTANT, content=full_reply)
                self.session_manager.add_message(session_id, assistant_msg)

                yield OrchestrationEvent(
                    event_type="done",
                    data={"content": full_reply, "fast_path": True}
                )
                return

            except asyncio.CancelledError:
                yield OrchestrationEvent(event_type="error", data={"error": "Request cancelled by user."})
                return
            except Exception as exc:
                logger.error("Fast-path generation error: %s", exc)
                yield OrchestrationEvent(event_type="error", data={"error": str(exc)})
                return

        # 4. Bounded Tool-Assisted Execution Path
        max_steps = self.settings.max_orchestrator_steps
        timeout = self.settings.orchestrator_timeout_seconds

        task = self.session_manager.create_task(
            session_id=session_id,
            goal=user_prompt,
            max_steps=max_steps
        )
        yield OrchestrationEvent(
            event_type="progress",
            data=TaskProgress(
                task_id=task.task_id,
                step=0,
                max_steps=max_steps,
                current_action="Task initialized",
                status=TaskStatus.RUNNING
            ).model_dump()
        )

        step = 0
        executed_tool_calls: List[ToolCall] = []
        start_time = asyncio.get_event_loop().time()

        try:
            while step < max_steps:
                token.raise_if_cancelled()

                # Timeout check
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(f"Task exceeded execution timeout of {timeout}s.")

                step += 1
                self.session_manager.update_task_progress(
                    task_id=task.task_id,
                    step=step,
                    current_action=f"Reasoning step {step}/{max_steps}",
                    status=TaskStatus.RUNNING
                )
                yield OrchestrationEvent(
                    event_type="progress",
                    data={"step": step, "max_steps": max_steps, "status": "running"}
                )

                # Request model completion with tools
                response = await provider.generate(
                    messages=injected_messages,
                    tools=active_tools,
                    cancellation_token=token
                )

                # If model finished without requesting further tools
                if not response.tool_calls:
                    assistant_msg = ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content=response.content
                    )
                    self.session_manager.add_message(session_id, assistant_msg)
                    self.session_manager.complete_task(task.task_id)

                    # Emit token event so UI displays response immediately
                    if response.content:
                        yield OrchestrationEvent(
                            event_type="token",
                            data={"delta": response.content}
                        )

                    yield OrchestrationEvent(
                        event_type="done",
                        data={"content": response.content, "task_id": task.task_id}
                    )
                    return

                # Process Tool Calls
                for tc in response.tool_calls:
                    token.raise_if_cancelled()

                    # Loop detection
                    if self._detect_loop(tc, executed_tool_calls):
                        raise LoopDetectedError(
                            f"Infinite loop detected: tool '{tc.tool_name}' invoked multiple times with identical arguments."
                        )
                    executed_tool_calls.append(tc)

                    yield OrchestrationEvent(
                        event_type="tool_call",
                        data={"tool_call": tc.model_dump()}
                    )

                    # Execute tool via executor if available
                    tool_output = None
                    if self.tool_executor:
                        tool_output = await self._run_tool(tc)
                    else:
                        tool_output = f"Simulated output for {tc.tool_name}({tc.arguments})"

                    tool_result = ToolResult(
                        tool_call_id=tc.id,
                        tool_name=tc.tool_name,
                        status="success",
                        output=tool_output
                    )
                    task.tool_results.append(tool_result)

                    yield OrchestrationEvent(
                        event_type="tool_result",
                        data={"tool_result": tool_result.model_dump()}
                    )

                    # Append tool message to history for next model turn
                    tool_msg = ChatMessage(
                        role=MessageRole.TOOL,
                        content=str(tool_output),
                        tool_call_id=tc.id,
                        name=tc.tool_name
                    )
                    self.session_manager.add_message(session_id, tool_msg)
                    messages = self.session_manager.get_messages(session_id)
                    injected_messages = [
                        ChatMessage(role=MessageRole.SYSTEM, content=system_content),
                        *[m for m in messages if m.role != MessageRole.SYSTEM]
                    ]

            # Max steps exceeded
            self.session_manager.fail_task(task.task_id, "Max steps budget reached.")
            yield OrchestrationEvent(
                event_type="error",
                data={"error": f"Orchestrator halted: reached maximum budget of {max_steps} steps."}
            )

        except asyncio.CancelledError:
            self.session_manager.cancel_task(task.task_id)
            yield OrchestrationEvent(event_type="error", data={"error": "Task cancelled by user."})
        except LoopDetectedError as exc:
            self.session_manager.fail_task(task.task_id, str(exc))
            yield OrchestrationEvent(event_type="error", data={"error": str(exc)})
        except Exception as exc:
            logger.error("Orchestrator error during task %s: %s", task.task_id, exc)
            self.session_manager.fail_task(task.task_id, str(exc))
            yield OrchestrationEvent(event_type="error", data={"error": str(exc)})

    async def _run_tool(self, tool_call: ToolCall) -> Any:
        """Invoke tool executor safely."""
        from jarvis.models.messages import ToolResult
        if asyncio.iscoroutinefunction(self.tool_executor):
            res = await self.tool_executor(tool_call)
        else:
            res = self.tool_executor(tool_call)
        if isinstance(res, ToolResult):
            return res.output if res.status == "success" else f"Error: {res.error_message}"
        return res
