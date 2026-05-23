from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    workspace_root: Path

    @classmethod
    def from_env(cls) -> "Settings":
        raw_root = os.environ.get("EXPEDIENTE_WORKSPACE_ROOT", "expedientes")
        return cls(workspace_root=Path(raw_root).expanduser())
