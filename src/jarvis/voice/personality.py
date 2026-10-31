"""Central Assistant Identity and Personality Configuration."""

from typing import Optional
from pydantic import BaseModel, Field

from jarvis.config import FormalityLevel, Settings, VerbosityLevel, settings


class PersonalityProfile(BaseModel):
    """Configurable personality attributes."""
    name: str = "Jarvis"
    tone: str = "helpful, competent, and respectful"
    formality: FormalityLevel = FormalityLevel.BALANCED
    verbosity: VerbosityLevel = VerbosityLevel.CONCISE
    humor: float = Field(default=0.3, ge=0.0, le=1.0)
    proactivity: float = Field(default=0.5, ge=0.0, le=1.0)
    preferred_format: str = "markdown"
    custom_instructions: str = ""


class PersonalityManager:
    """Manages identity settings and formats provider-agnostic system prompts."""

    def __init__(self, profile: Optional[PersonalityProfile] = None, app_settings: Optional[Settings] = None) -> None:
        cfg = app_settings or settings
        self.profile = profile or PersonalityProfile(
            name=cfg.assistant_name,
            tone=cfg.tone,
            formality=cfg.formality,
            verbosity=cfg.verbosity,
            proactivity=cfg.proactivity,
        )

    def get_profile(self) -> PersonalityProfile:
        """Retrieve current personality settings."""
        return self.profile

    def update_profile(
        self,
        name: Optional[str] = None,
        tone: Optional[str] = None,
        formality: Optional[FormalityLevel] = None,
        verbosity: Optional[VerbosityLevel] = None,
        humor: Optional[float] = None,
        proactivity: Optional[float] = None,
        custom_instructions: Optional[str] = None,
    ) -> PersonalityProfile:
        """Update personality settings."""
        if name is not None:
            self.profile.name = name
        if tone is not None:
            self.profile.tone = tone
        if formality is not None:
            self.profile.formality = formality
        if verbosity is not None:
            self.profile.verbosity = verbosity
        if humor is not None:
            self.profile.humor = humor
        if proactivity is not None:
            self.profile.proactivity = proactivity
        if custom_instructions is not None:
            self.profile.custom_instructions = custom_instructions
        return self.profile

    def compile_system_prompt(self, skill_guidelines: str = "") -> str:
        """Compose a unified, robust system prompt."""
        p = self.profile

        formality_desc = {
            FormalityLevel.CASUAL: "friendly, relaxed, and conversational",
            FormalityLevel.BALANCED: "polite, clear, and professional yet approachable",
            FormalityLevel.FORMAL: "structured, rigorous, and strictly professional",
        }[p.formality]

        verbosity_desc = {
            VerbosityLevel.TERSE: "very brief and direct with minimal elaboration",
            VerbosityLevel.CONCISE: "clear, focused, and informative without needless filler",
            VerbosityLevel.DETAILED: "thorough, detailed, and comprehensive",
        }[p.verbosity]

        prompt_parts = [
            f"You are {p.name}, a desktop-first personal AI assistant.",
            f"Tone: {p.tone}.",
            f"Formality: {formality_desc}.",
            f"Verbosity: {verbosity_desc}.",
            f"Humor Level: {int(p.humor * 100)}% (use subtle wit where appropriate without being silly).",
            f"Proactivity Level: {int(p.proactivity * 100)}% (anticipate user needs within permission boundaries).",
            "General Rules:",
            "1. You are running on the user's computer. Maintain strict privacy and adhere to software permission gates.",
            "2. Never claim actions occurred unless they were successfully executed by approved tools.",
            "3. Format your responses in clean GitHub-flavored markdown.",
        ]

        if p.custom_instructions.strip():
            prompt_parts.append(f"User Custom Directives:\n{p.custom_instructions.strip()}")

        if skill_guidelines.strip():
            prompt_parts.append(skill_guidelines.strip())

        return "\n\n".join(prompt_parts)
