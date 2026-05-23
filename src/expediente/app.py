from __future__ import annotations

import sys

from expediente.application.orchestrator import OrchestratorService
from expediente.config import Settings
from expediente.llm.gateway import build_model_gateway_from_env
from expediente.storage.filesystem import FilesystemWorkspaceRepository
from expediente.ui.main_window import MainWindowFactory


def build_orchestrator() -> OrchestratorService:
    settings = Settings.from_env()
    repository = FilesystemWorkspaceRepository(settings.workspace_root)
    model_gateway = build_model_gateway_from_env()
    return OrchestratorService(repository, model_gateway=model_gateway)


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError as exc:
        raise RuntimeError("PySide6 is required. Install with `pip install -e .[desktop]`.") from exc

    app = QApplication(sys.argv)
    orchestrator = build_orchestrator()
    orchestrator.bootstrap_workspace()
    window = MainWindowFactory(orchestrator).create()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
