"""Security Policies, Action Types, and Canonical Path Boundary Enforcement."""

from enum import Enum
from pathlib import Path
from typing import Optional, Union


class ActionType(str, Enum):
    """Classification of action risk level and mutation impact."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    NETWORK = "network"


class SecurityError(Exception):
    """Base security exception."""
    pass


class PathTraversalError(SecurityError):
    """Raised when a path points or resolves outside the allowed root."""
    pass


class PermissionDeniedError(SecurityError):
    """Raised when an operation is prohibited by policy or rejected by the user."""
    pass


class ApprovalRequiredError(SecurityError):
    """Raised when an action requires explicit interactive user confirmation."""
    def __init__(self, message: str, request_id: str) -> None:
        super().__init__(message)
        self.request_id = request_id


class PathValidator:
    """Deterministic path boundary validator.

    Guarantees all path operations resolve strictly within the project workspace,
    rejecting path traversals, relative dot-dot components, and symlink escapes.
    """

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def validate_path(self, target_path: Union[str, Path], allow_symlinks_outside: bool = False) -> Path:
        """Validate and resolve target path strictly within workspace root."""
        p = Path(target_path)
        
        # If relative, resolve relative to workspace root
        if not p.is_absolute():
            resolved = (self.workspace_root / p).resolve()
        else:
            resolved = p.resolve()

        # Strict boundary check
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise PathTraversalError(
                f"Path traversal escape detected: '{target_path}' resolves to '{resolved}', "
                f"which is outside workspace root '{self.workspace_root}'."
            ) from exc

        return resolved

    def is_inside_workspace(self, target_path: Union[str, Path]) -> bool:
        """Non-raising check returning True if path is safely inside workspace."""
        try:
            self.validate_path(target_path)
            return True
        except PathTraversalError:
            return False
