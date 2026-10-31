"""Filesystem Tools (Read, Write, List Directory)."""

import os
from pathlib import Path
from typing import Any, Dict, List
from jarvis.security.policy import ActionType
from jarvis.tools.base import BaseTool, ToolDefinition


class ReadFileTool(BaseTool):
    """Tool to read the contents of a file within the workspace."""

    def __init__(self) -> None:
        super().__init__(
            ToolDefinition(
                name="workspace_read_file",
                description="Read UTF-8 text contents of a file within the workspace.",
                action_type=ActionType.READ,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Relative or absolute path to the file inside workspace."
                        },
                        "max_lines": {
                            "type": "integer",
                            "description": "Optional maximum number of lines to read.",
                            "default": 500
                        }
                    },
                    "required": ["file_path"],
                },
            )
        )

    async def run(self, file_path: str, max_lines: int = 500, **kwargs: Any) -> str:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not p.is_file():
            raise IsADirectoryError(f"Target is a directory, not a file: {file_path}")

        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines)]
        return "".join(lines)


class WriteFileTool(BaseTool):
    """Tool to write or overwrite a file within the workspace."""

    def __init__(self) -> None:
        super().__init__(
            ToolDefinition(
                name="workspace_write_file",
                description="Write text contents to a file within the workspace.",
                action_type=ActionType.WRITE,
                requires_approval_by_default=True,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Relative or absolute path to the file inside workspace."
                        },
                        "content": {
                            "type": "string",
                            "description": "Text content to write."
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Whether to overwrite existing file.",
                            "default": True
                        }
                    },
                    "required": ["file_path", "content"],
                },
            )
        )

    async def run(self, file_path: str, content: str, overwrite: bool = True, **kwargs: Any) -> Dict[str, Any]:
        p = Path(file_path)
        if p.exists() and not overwrite:
            raise FileExistsError(f"File '{file_path}' already exists and overwrite is False.")
        
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "written",
            "file_path": str(p),
            "bytes_written": len(content.encode("utf-8")),
        }


class ListDirectoryTool(BaseTool):
    """Tool to list directory entries within the workspace."""

    def __init__(self) -> None:
        super().__init__(
            ToolDefinition(
                name="workspace_list_directory",
                description="List files and directories within a workspace directory.",
                action_type=ActionType.READ,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "directory_path": {
                            "type": "string",
                            "description": "Relative or absolute directory path.",
                            "default": "."
                        }
                    },
                },
            )
        )

    async def run(self, directory_path: str = ".", **kwargs: Any) -> List[Dict[str, Any]]:
        p = Path(directory_path)
        if not p.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        if not p.is_dir():
            raise NotADirectoryError(f"Target is not a directory: {directory_path}")

        entries = []
        for item in sorted(p.iterdir()):
            entries.append({
                "name": item.name,
                "is_dir": item.is_dir(),
                "size_bytes": item.stat().st_size if item.is_file() else 0,
            })
        return entries


class DeleteFileTool(BaseTool):
    """Tool to delete a file within the workspace (requires explicit confirmation)."""

    def __init__(self) -> None:
        super().__init__(
            ToolDefinition(
                name="workspace_delete_file",
                description="Delete a file within the workspace. This is a mutating action requiring confirmation.",
                action_type=ActionType.DELETE,
                requires_approval_by_default=True,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Relative or absolute path to the file to remove inside workspace."
                        }
                    },
                    "required": ["file_path"],
                },
            )
        )

    async def run(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if p.is_dir():
            raise IsADirectoryError(f"Target is a directory, not a file: {file_path}")

        p.unlink()
        return {
            "status": "deleted",
            "file_path": str(p),
        }


class SearchFilesTool(BaseTool):
    """Tool to search for files matching patterns or containing text."""

    def __init__(self) -> None:
        super().__init__(
            ToolDefinition(
                name="workspace_search_files",
                description="Search for workspace files matching a glob pattern (e.g. *.py, src/**/*.ts) or containing a keyword.",
                action_type=ActionType.READ,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Glob pattern such as '*.py' or '**/*.json'.",
                            "default": "*"
                        },
                        "containing_text": {
                            "type": "string",
                            "description": "Optional substring to search inside files.",
                            "default": ""
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of file matches to return.",
                            "default": 30
                        }
                    },
                },
            )
        )

    async def run(self, pattern: str = "*", containing_text: str = "", max_results: int = 30, **kwargs: Any) -> List[Dict[str, Any]]:
        matches = []
        root = Path(".")
        for p in root.glob(pattern):
            if len(matches) >= max_results:
                break
            if not p.is_file():
                continue
            # Skip hidden files or heavy dirs like .venv, .git, node_modules
            parts = p.parts
            if any(part.startswith(".") or part in ("node_modules", "__pycache__", "dist", "build") for part in parts):
                continue

            if containing_text:
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    if containing_text.lower() not in text.lower():
                        continue
                except Exception:
                    continue

            matches.append({
                "path": str(p),
                "size_bytes": p.stat().st_size,
            })
        return matches
