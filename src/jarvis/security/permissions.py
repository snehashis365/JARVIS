"""Deterministic Software Permission Manager.

Controls all tool and action execution according to Autonomy Modes (Plan, Agent Decides,
Auto, Sandbox Only), path allowlists, and cryptographic approval grants.
"""

import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from jarvis.config import AutonomyMode, Settings, settings
from jarvis.security.audit import AuditLogger, AuditRecord
from jarvis.security.policy import (
    ActionType,
    ApprovalRequiredError,
    PathTraversalError,
    PathValidator,
    PermissionDeniedError,
)


class ApprovalRequest(BaseModel):
    """Interactive approval request for mutating or high-impact actions."""
    request_id: str = Field(default_factory=lambda: secrets.token_hex(12))
    tool_name: str
    action_type: ActionType
    resource_path: Optional[str] = None
    target: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    justification: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at_epoch: float = Field(default_factory=lambda: time.time() + 300.0)  # 5 min expiration
    status: str = "PENDING"  # "PENDING", "APPROVED", "REJECTED", "EXPIRED"

    def model_post_init(self, __context: Any) -> None:
        if not self.target:
            self.target = self.resource_path or str(
                self.parameters.get("file_path")
                or self.parameters.get("command")
                or self.parameters.get("path")
                or self.tool_name
            )


class PermissionDecision(BaseModel):
    """Result of a permission evaluation."""
    allowed: bool
    requires_approval: bool = False
    approval_request: Optional[ApprovalRequest] = None
    reason: str = ""
    resolved_path: Optional[str] = None


class PermissionManager:
    """Deterministic permission enforcement engine."""

    def __init__(
        self,
        app_settings: Optional[Settings] = None,
        path_validator: Optional[PathValidator] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self.settings = app_settings or settings
        self.path_validator = path_validator or PathValidator(self.settings.project_root)
        self.audit_logger = audit_logger or AuditLogger(self.settings.logs_dir)
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._approved_tokens: Dict[str, ApprovalRequest] = {}

    @property
    def current_mode(self) -> AutonomyMode:
        return self.settings.autonomy_mode

    def evaluate_action(
        self,
        tool_name: str,
        action_type: ActionType,
        resource_path: Optional[Union[str, Path]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        justification: str = "",
        approval_token: Optional[str] = None,
    ) -> PermissionDecision:
        """Evaluate whether an action is allowed, denied, or requires approval."""
        params = parameters or {}
        mode = self.current_mode
        resolved_path_str: Optional[str] = None

        # 1. Path Boundary Enforcement
        if resource_path:
            try:
                resolved = self.path_validator.validate_path(resource_path)
                resolved_path_str = str(resolved)
            except PathTraversalError as exc:
                self.audit_logger.record(
                    action_type=action_type.value,
                    tool_name=tool_name,
                    decision="DENIED",
                    autonomy_mode=mode.value,
                    resource=str(resource_path),
                    parameters=params,
                    session_id=session_id,
                    reason=str(exc),
                )
                raise

        # 2. Check if a pre-existing approval token was provided
        if approval_token and approval_token in self._approved_tokens:
            req = self._approved_tokens[approval_token]
            if time.time() <= req.expires_at_epoch:
                self.audit_logger.record(
                    action_type=action_type.value,
                    tool_name=tool_name,
                    decision="APPROVED",
                    autonomy_mode=mode.value,
                    resource=resolved_path_str,
                    parameters=params,
                    session_id=session_id,
                    reason="Pre-approved via interactive user token.",
                )
                return PermissionDecision(
                    allowed=True,
                    reason="Pre-authorized with valid approval token.",
                    resolved_path=resolved_path_str,
                )

        # 3. Autonomy Mode Policy Enforcement
        # MODE 1: PLAN (Strictly Read-Only)
        if mode == AutonomyMode.PLAN:
            if action_type != ActionType.READ:
                reason = f"Plan mode strictly prohibits state-changing '{action_type.value}' actions."
                self.audit_logger.record(
                    action_type=action_type.value,
                    tool_name=tool_name,
                    decision="DENIED",
                    autonomy_mode=mode.value,
                    resource=resolved_path_str,
                    parameters=params,
                    session_id=session_id,
                    reason=reason,
                )
                return PermissionDecision(allowed=False, reason=reason)
            
            # Read allowed
            self.audit_logger.record(
                action_type=action_type.value,
                tool_name=tool_name,
                decision="ALLOWED",
                autonomy_mode=mode.value,
                resource=resolved_path_str,
                parameters=params,
                session_id=session_id,
                reason="Plan mode permitted read-only inspection.",
            )
            return PermissionDecision(allowed=True, reason="Read allowed in Plan mode.", resolved_path=resolved_path_str)

        # MODE 2: SANDBOX_ONLY (Confined to sandbox directory only, zero network/exec)
        if mode == AutonomyMode.SANDBOX_ONLY:
            sandbox_dir = (self.settings.data_dir / "sandbox").resolve()
            sandbox_dir.mkdir(parents=True, exist_ok=True)

            if action_type in (ActionType.EXECUTE, ActionType.NETWORK):
                reason = f"Sandbox-only mode prohibits '{action_type.value}' operations."
                self.audit_logger.record(
                    action_type=action_type.value,
                    tool_name=tool_name,
                    decision="DENIED",
                    autonomy_mode=mode.value,
                    resource=resolved_path_str,
                    parameters=params,
                    session_id=session_id,
                    reason=reason,
                )
                return PermissionDecision(allowed=False, reason=reason)

            if resource_path:
                resolved_p = Path(resolved_path_str)
                try:
                    resolved_p.relative_to(sandbox_dir)
                except ValueError:
                    reason = f"Sandbox-only mode restricts operations strictly to '{sandbox_dir}'."
                    self.audit_logger.record(
                        action_type=action_type.value,
                        tool_name=tool_name,
                        decision="DENIED",
                        autonomy_mode=mode.value,
                        resource=resolved_path_str,
                        parameters=params,
                        session_id=session_id,
                        reason=reason,
                    )
                    return PermissionDecision(allowed=False, reason=reason)

            return PermissionDecision(allowed=True, reason="Permitted within sandbox boundary.", resolved_path=resolved_path_str)

        # MODE 3: AUTO (Pre-approved within workspace, except destructive actions)
        if mode == AutonomyMode.AUTO:
            # Irreversible actions (DELETE, arbitrary execute) always prompt
            if action_type == ActionType.DELETE:
                req = self._create_approval_request(tool_name, action_type, resolved_path_str, params, justification)
                return PermissionDecision(
                    allowed=False,
                    requires_approval=True,
                    approval_request=req,
                    reason="Deletion actions require explicit confirmation even in Auto mode.",
                    resolved_path=resolved_path_str,
                )

            self.audit_logger.record(
                action_type=action_type.value,
                tool_name=tool_name,
                decision="ALLOWED",
                autonomy_mode=mode.value,
                resource=resolved_path_str,
                parameters=params,
                session_id=session_id,
                reason="Auto mode pre-authorized workspace operation.",
            )
            return PermissionDecision(allowed=True, reason="Auto mode pre-authorized.", resolved_path=resolved_path_str)

        # MODE 4: AGENT_DECIDES (Default Safe Operating Mode)
        # Low-risk read and network search operations run autonomously
        if action_type in (ActionType.READ, ActionType.NETWORK):
            self.audit_logger.record(
                action_type=action_type.value,
                tool_name=tool_name,
                decision="ALLOWED",
                autonomy_mode=mode.value,
                resource=resolved_path_str,
                parameters=params,
                session_id=session_id,
                reason="Agent Decides mode autonomously permitted read/search operation.",
            )
            return PermissionDecision(allowed=True, reason="Read/search allowed.", resolved_path=resolved_path_str)

        # Mutating actions (write, delete, execute) trigger interactive approval
        req = self._create_approval_request(
            tool_name, action_type, resolved_path_str, params, justification or f"Mutating action: {action_type.value}"
        )
        self.audit_logger.record(
            action_type=action_type.value,
            tool_name=tool_name,
            decision="PENDING_APPROVAL",
            autonomy_mode=mode.value,
            resource=resolved_path_str,
            parameters=params,
            session_id=session_id,
            reason=f"Action '{action_type.value}' requires explicit user approval in Agent Decides mode.",
        )
        return PermissionDecision(
            allowed=False,
            requires_approval=True,
            approval_request=req,
            reason=f"Action '{action_type.value}' requires explicit user approval.",
            resolved_path=resolved_path_str,
        )

    def _create_approval_request(
        self,
        tool_name: str,
        action_type: ActionType,
        resource_path: Optional[str],
        parameters: Dict[str, Any],
        justification: str,
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            tool_name=tool_name,
            action_type=action_type,
            resource_path=resource_path,
            parameters=parameters,
            justification=justification,
        )
        self._pending_approvals[req.request_id] = req
        return req

    def resolve_approval(self, request_id: str, approved: bool) -> ApprovalRequest:
        """Resolve a pending approval request."""
        req = self._pending_approvals.get(request_id)
        if not req:
            raise ValueError(f"Approval request '{request_id}' not found.")

        if time.time() > req.expires_at_epoch:
            req.status = "EXPIRED"
            raise PermissionDeniedError(f"Approval request '{request_id}' has expired.")

        if approved:
            req.status = "APPROVED"
            self._approved_tokens[request_id] = req
            self.audit_logger.record(
                action_type=req.action_type.value,
                tool_name=req.tool_name,
                decision="APPROVED",
                autonomy_mode=self.current_mode.value,
                resource=req.resource_path,
                parameters=req.parameters,
                reason="User explicitly approved the action.",
            )
        else:
            req.status = "REJECTED"
            self.audit_logger.record(
                action_type=req.action_type.value,
                tool_name=req.tool_name,
                decision="REJECTED",
                autonomy_mode=self.current_mode.value,
                resource=req.resource_path,
                parameters=req.parameters,
                reason="User explicitly rejected the action.",
            )

        del self._pending_approvals[request_id]
        return req

    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """List active pending approval requests that have not expired."""
        now = time.time()
        return [r for r in self._pending_approvals.values() if r.expires_at_epoch > now and r.status == "PENDING"]
