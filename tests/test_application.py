from __future__ import annotations

from datetime import date

from expediente.application.orchestrator import OrchestratorService
from expediente.storage.filesystem import FilesystemWorkspaceRepository


class FakeModelGateway:
    def __init__(self, response: str = "respuesta del modelo") -> None:
        self.response = response
        self.calls = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        return self.response


def test_orchestrator_creates_patient_and_records_log(tmp_path):
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))

    patient = service.create_patient("P-001")

    log = patient.log_file.read_text(encoding="utf-8")
    assert service.list_patients() == ["P-001"]
    assert "Creación de expediente de paciente" in log
    assert "Orquestador" in log


def test_orchestrator_returns_patient_summary(tmp_path):
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")

    summary = service.get_patient_summary("P-001")

    assert summary.patient_id == "P-001"
    assert summary.raw_consultation_count == 0
    assert summary.medical_consultation_count == 0


def test_orchestrator_creates_raw_consultation_and_logs_operation(tmp_path):
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    patient = service.create_patient("P-001")

    raw_file = service.create_raw_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        content="Paciente refiere dolor de cabeza.",
    )

    assert raw_file.exists()
    assert service.get_patient_summary("P-001").raw_consultation_count == 1
    log = patient.log_file.read_text(encoding="utf-8")
    assert "Creación de Formato Crudo" in log
    assert str(raw_file) in log


def test_orchestrator_generates_medical_draft_from_raw_and_template(tmp_path):
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")
    service.create_raw_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        content="Paciente refiere dolor de cabeza.",
    )

    draft = service.generate_medical_draft(patient_id="P-001", consultation_date=date(2026, 5, 22))

    assert "# Borrador de Formato Médico — Paciente P-001" in draft
    assert "## Plantilla" in draft
    assert "## Fuente — Formato Crudo" in draft
    assert "Paciente refiere dolor de cabeza." in draft
    assert "paciente_id:" not in draft


def test_orchestrator_uses_model_gateway_for_medical_draft_when_configured(tmp_path):
    gateway = FakeModelGateway("borrador generado por modelo")
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"), model_gateway=gateway)
    service.create_patient("P-001")
    service.create_raw_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        content="Paciente refiere dolor de cabeza.",
    )

    draft = service.generate_medical_draft(patient_id="P-001", consultation_date=date(2026, 5, 22))

    assert draft == "borrador generado por modelo"
    assert "Formateador" in gateway.calls[0]["system"]
    assert "Paciente refiere dolor de cabeza." in gateway.calls[0]["user"]


def test_orchestrator_saves_medical_consultation_and_logs_operation(tmp_path):
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    patient = service.create_patient("P-001")
    service.create_raw_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        content="Texto crudo.",
    )

    medical_file = service.save_medical_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        content="# Borrador revisado\n\nPlan médico.",
    )

    assert medical_file.exists()
    assert service.get_patient_summary("P-001").medical_consultation_count == 1
    log = patient.log_file.read_text(encoding="utf-8")
    assert "Creación de Formato Médico" in log
    assert str(medical_file) in log


def test_orchestrator_answers_patient_question_from_medical_documents(tmp_path):
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")
    service.create_raw_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        content="Texto crudo.",
    )
    service.save_medical_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        content="# Consulta médica\n\nPlan médico.",
    )

    answer = service.answer_patient_question(patient_id="P-001", question="¿Cuál es el plan?")

    assert "Pregunta: ¿Cuál es el plan?" in answer
    assert "## Consulta 2026-05-22" in answer
    assert "Referencia:" in answer
    assert "Plan médico." in answer


def test_orchestrator_uses_model_gateway_for_patient_question_when_configured(tmp_path):
    gateway = FakeModelGateway("respuesta sintetizada")
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"), model_gateway=gateway)
    service.create_patient("P-001")
    service.create_raw_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        content="Texto crudo.",
    )
    service.save_medical_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        content="# Consulta médica\n\nPlan médico.",
    )

    answer = service.answer_patient_question(patient_id="P-001", question="¿Cuál es el plan?")

    assert answer == "respuesta sintetizada"
    assert "Investigador" in gateway.calls[0]["system"]
    assert "Plan médico." in gateway.calls[0]["user"]


def test_orchestrator_reports_no_medical_documents_for_question(tmp_path):
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")

    answer = service.answer_patient_question(patient_id="P-001", question="¿Cuál es el plan?")

    assert answer == "No hay Formatos Médicos definitivos disponibles para el paciente P-001."
