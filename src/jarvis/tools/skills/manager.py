"""Skill Manager and Lifecycle Subsystem."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from jarvis.tools.skills.manifest import SkillManifest


class SkillManager:
    """Manages skill discovery, validation, activation, and instruction compiling."""

    def __init__(self) -> None:
        self._skills: Dict[str, SkillManifest] = {}
        self._register_default_skills()

    def _register_default_skills(self) -> None:
        """Register built-in skills."""
        code_analyzer = SkillManifest(
            name="workspace_analyzer",
            version="1.0.0",
            description="Analyzes project files and synthesizes architectural overviews.",
            instructions=(
                "When asked to analyze or summarize the workspace, first list the directory contents, "
                "read relevant files, and produce a concise, structured report."
            ),
            required_tools=["workspace_list_directory", "workspace_read_file"],
            declared_permissions=[],
            enabled=True,
        )
        web_researcher = SkillManifest(
            name="web_researcher",
            version="1.0.0",
            description="Performs multi-query search research and synthesizes citations.",
            instructions=(
                "When conducting research, search for authoritative documentation, cross-reference "
                "sources, and cite key links in your response."
            ),
            required_tools=["web_search"],
            declared_permissions=[],
            enabled=True,
        )
        self.register(code_analyzer)
        self.register(web_researcher)

    def register(self, skill: SkillManifest) -> None:
        """Register a validated skill manifest."""
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[SkillManifest]:
        """Retrieve a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> List[SkillManifest]:
        """List all installed skills."""
        return list(self._skills.values())

    def enable(self, name: str) -> bool:
        """Enable a skill."""
        skill = self.get(name)
        if skill:
            skill.enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a skill."""
        skill = self.get(name)
        if skill:
            skill.enabled = False
            return True
        return False

    def load_from_json(self, json_content: str) -> SkillManifest:
        """Parse, validate, and register a skill from JSON."""
        data = json.loads(json_content)
        manifest = SkillManifest(**data)
        self.register(manifest)
        return manifest

    def get_active_instructions(self) -> str:
        """Compile instructions for all active enabled skills."""
        active = [s for s in self._skills.values() if s.enabled]
        if not active:
            return ""
        compiled = ["## Active Skill Guidelines:"]
        for s in active:
            compiled.append(f"### Skill: {s.name}\n{s.instructions}\n")
        return "\n".join(compiled)
