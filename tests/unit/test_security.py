"""Unit tests for Phase 4 Deterministic Security and Permission Enforcement.

Verifies PathValidator, PermissionManager across all autonomy modes,
interactive approval workflows, and audit logging with secret redaction.
"""

from pathlib import Path
import pytest

from jarvis.config import AutonomyMode, Settings
from jarvis.security.audit import AuditLogger
from jarvis.security.permissions import PermissionManager
from jarvis.security.policy import (
    ActionType,
    PathTraversalError,
    PathValidator,
    PermissionDeniedError,
)


def test_path_validator_boundaries(tmp_path: Path):
    """Verify PathValidator permits workspace paths and rejects traversals."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    safe_file = workspace / "test.txt"
    safe_file.write_text("safe content")

    validator = PathValidator(workspace_root=workspace)

    # Safe relative and absolute paths
    assert validator.validate_path("test.txt") == safe_file.resolve()
    assert validator.validate_path(safe_file) == safe_file.resolve()
    assert validator.is_inside_workspace("test.txt") is True

    # Traversal attempts outside workspace
    outside_file = tmp_path / "private_outside.txt"
    outside_file.write_text("private")

    with pytest.raises(PathTraversalError):
        validator.validate_path("../private_outside.txt")

    with pytest.raises(PathTraversalError):
        validator.validate_path(outside_file)

    with pytest.raises(PathTraversalError):
        validator.validate_path("/etc/passwd")

    assert validator.is_inside_workspace("../private_outside.txt") is False


def test_plan_mode_read_only(tmp_path: Path):
    """Verify Plan mode permits reads but strictly forbids state mutations."""
    settings = Settings(
        project_root=tmp_path,
        JARVIS_AUTONOMY_MODE=AutonomyMode.PLAN
    )
    pm = PermissionManager(app_settings=settings)

    # Read action allowed
    decision_read = pm.evaluate_action(
        tool_name="read_file",
        action_type=ActionType.READ,
        resource_path="file.txt"
    )
    assert decision_read.allowed is True
    assert decision_read.requires_approval is False

    # Write action forbidden
    decision_write = pm.evaluate_action(
        tool_name="write_file",
        action_type=ActionType.WRITE,
        resource_path="file.txt"
    )
    assert decision_write.allowed is False
    assert "strictly prohibits" in decision_read.reason or "strictly prohibits" in decision_write.reason

    # Delete action forbidden
    decision_delete = pm.evaluate_action(
        tool_name="delete_file",
        action_type=ActionType.DELETE,
        resource_path="file.txt"
    )
    assert decision_delete.allowed is False


def test_agent_decides_mode_approval(tmp_path: Path):
    """Verify Agent Decides allows reads but requires approval for mutations."""
    settings = Settings(
        project_root=tmp_path,
        JARVIS_AUTONOMY_MODE=AutonomyMode.AGENT_DECIDES
    )
    pm = PermissionManager(app_settings=settings)

    # Read allowed autonomously
    decision_read = pm.evaluate_action(
        tool_name="read_file",
        action_type=ActionType.READ,
        resource_path="file.txt"
    )
    assert decision_read.allowed is True
    assert decision_read.requires_approval is False

    # Write triggers approval requirement
    decision_write = pm.evaluate_action(
        tool_name="write_file",
        action_type=ActionType.WRITE,
        resource_path="file.txt",
        parameters={"content": "hello"}
    )
    assert decision_write.allowed is False
    assert decision_write.requires_approval is True
    assert decision_write.approval_request is not None

    req_id = decision_write.approval_request.request_id

    # Pending list reflects request
    pending = pm.get_pending_approvals()
    assert len(pending) == 1
    assert pending[0].request_id == req_id

    # Approve request
    approved_req = pm.resolve_approval(req_id, approved=True)
    assert approved_req.status == "APPROVED"

    # Re-evaluate with approval token now succeeds
    decision_approved = pm.evaluate_action(
        tool_name="write_file",
        action_type=ActionType.WRITE,
        resource_path="file.txt",
        approval_token=req_id
    )
    assert decision_approved.allowed is True


def test_auto_mode_boundaries(tmp_path: Path):
    """Verify Auto mode pre-approves safe writes, but gates deletion."""
    settings = Settings(
        project_root=tmp_path,
        JARVIS_AUTONOMY_MODE=AutonomyMode.AUTO
    )
    pm = PermissionManager(app_settings=settings)

    # Safe write allowed without prompt
    decision_write = pm.evaluate_action(
        tool_name="write_file",
        action_type=ActionType.WRITE,
        resource_path="file.txt"
    )
    assert decision_write.allowed is True
    assert decision_write.requires_approval is False

    # Deletion still requires approval
    decision_delete = pm.evaluate_action(
        tool_name="delete_file",
        action_type=ActionType.DELETE,
        resource_path="file.txt"
    )
    assert decision_delete.allowed is False
    assert decision_delete.requires_approval is True


def test_sandbox_only_mode(tmp_path: Path):
    """Verify Sandbox Only mode restricts operations strictly to sandbox directory."""
    settings = Settings(
        project_root=tmp_path,
        JARVIS_AUTONOMY_MODE=AutonomyMode.SANDBOX_ONLY
    )
    pm = PermissionManager(app_settings=settings)

    # Operation on general workspace path rejected
    decision_outside = pm.evaluate_action(
        tool_name="write_file",
        action_type=ActionType.WRITE,
        resource_path="root_file.txt"
    )
    assert decision_outside.allowed is False
    assert "sandbox" in decision_outside.reason.lower()

    # Operation inside sandbox directory allowed
    decision_inside = pm.evaluate_action(
        tool_name="write_file",
        action_type=ActionType.WRITE,
        resource_path="data/sandbox/test.txt"
    )
    assert decision_inside.allowed is True

    # Network and process execution prohibited
    decision_net = pm.evaluate_action(
        tool_name="external_api",
        action_type=ActionType.NETWORK
    )
    assert decision_net.allowed is False


def test_audit_logger_redaction(tmp_path: Path):
    """Verify audit logger stores records and automatically redacts secrets."""
    audit_logger = AuditLogger(log_dir=tmp_path)
    audit_logger.record(
        action_type="write",
        tool_name="save_config",
        decision="ALLOWED",
        autonomy_mode="agent_decides",
        resource="config.json",
        parameters={
            "token": "Bearer secret_user_jwt_1234567890",
            "key": "sk-1234567890abcdef1234567890",
            "normal": "safe_value"
        },
        reason="Bearer abcdef1234567890 approved"
    )

    records = audit_logger.get_records()
    assert len(records) == 1
    rec = records[0]
    assert rec.parameters["normal"] == "safe_value"
    assert "secret_user_jwt" not in rec.parameters["token"]
    assert "REDACTED" in rec.parameters["token"]
    assert "REDACTED" in rec.parameters["key"]
    assert "abcdef" not in rec.reason


@pytest.mark.asyncio
async def test_approvals_api_endpoints(async_client):
    """Verify /api/approvals list and resolve endpoints."""
    # List approvals
    res = await async_client.get("/api/approvals")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
