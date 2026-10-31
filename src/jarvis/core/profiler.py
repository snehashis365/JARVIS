"""Resource Awareness and Hardware Profiler.

Detects available hardware (CPU cores, RAM, OS, Apple Silicon / GPU availability)
and configures suitable resource consumption profiles.
"""

import os
import platform
from typing import Any, Dict
from pydantic import BaseModel


class HardwareProfile(BaseModel):
    """Hardware inventory and recommended resource profile."""
    os_name: str
    architecture: str
    cpu_cores: int
    has_apple_silicon: bool
    recommended_profile: str  # "low_resource", "balanced", "performance"
    max_concurrent_tasks: int
    recommended_context_tokens: int


class HardwareProfiler:
    """Inspects host system capabilities and calculates resource limits."""

    @staticmethod
    def profile() -> HardwareProfile:
        os_name = platform.system()
        arch = platform.machine()
        cores = os.cpu_count() or 2

        # Detect Apple Silicon (macOS arm64)
        is_apple_silicon = os_name == "Darwin" and arch in ("arm64", "aarch64")

        # Determine sensible resource profile
        if cores <= 4 and not is_apple_silicon:
            profile_name = "low_resource"
            concurrent = 1
            context_tokens = 4096
        elif cores <= 8 or is_apple_silicon:
            profile_name = "balanced"
            concurrent = 2
            context_tokens = 8192
        else:
            profile_name = "performance"
            concurrent = 4
            context_tokens = 16384

        return HardwareProfile(
            os_name=os_name,
            architecture=arch,
            cpu_cores=cores,
            has_apple_silicon=is_apple_silicon,
            recommended_profile=profile_name,
            max_concurrent_tasks=concurrent,
            recommended_context_tokens=context_tokens,
        )
