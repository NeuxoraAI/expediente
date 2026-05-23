from __future__ import annotations

from datetime import date, datetime

import pytest

from expediente.domain.models import LogEntry
from expediente.storage.filesystem import (
    ConsultationAlreadyExistsError,
    ConsultationNotFoundError,
    FilesystemWorkspaceRepository,
    PatientAlreadyExistsError,
)


def test_bootstrap_workspace_creates_expected_structure(tmp_path):
    repo = FilesystemWorkspaceRepository(tmp_path / "expedientes")

    paths = repo.bootstrap_workspace()

    assert paths.root.exists()
    assert paths.medico_dir.exists()
    assert paths.patients_dir.exists()
    assert (paths.medico_dir / "plantilla.md").exists()
    assert paths.global_index_file.exists()
    assert paths.agents_file.exists()


def test_create_patient_creates_prd_compliant_directories(tmp_path):
    repo = FilesystemWorkspaceRepository(tmp_path / "expedientes")

    paths = repo.create_patient("P-001")

    assert paths.index_file.exists()
    assert paths.log_file.exists()
    assert paths.raw_dir.is_dir()
    assert paths.medical_dir.is_dir()
    assert repo.list_patient_ids() == ["P-001"]


def test_create_patient_rejects_overwrite(tmp_path):
    repo = FilesystemWorkspaceRepository(tmp_path / "expedientes")
    repo.create_patient("P-001")

    with pytest.raises(PatientAlreadyExistsError):
        repo.create_patient("P-001")


def test_consultation_paths_use_prd_file_naming(tmp_path):
    repo = FilesystemWorkspaceRepository(tmp_path / "expedientes")
    repo.create_patient("P-001")

    consultation = repo.build_consultation_paths("P-001", date(2026, 5, 22))

    assert consultation.filename == "2026-05-22_consulta.md"
    assert consultation.raw_file.name == consultation.filename
    assert consultation.medical_file.name == consultation.filename


def test_patient_summary_counts_consultation_files(tmp_path):
    repo = FilesystemWorkspaceRepository(tmp_path / "expedientes")
    repo.create_patient("P-001")
    consultation = repo.build_consultation_paths("P-001", date(2026, 5, 22))
    consultation.raw_file.write_text("raw", encoding="utf-8")
    consultation.medical_file.write_text("medical", encoding="utf-8")

    summary = repo.patient_summary("P-001")

    assert summary.patient_id == "P-001"
    assert summary.raw_consultation_count == 1
    assert summary.medical_consultation_count == 1
    assert summary.index_file.name == "index.md"
    assert summary.log_file.name == "log.md"


def test_create_raw_consultation_writes_frontmatter_and_is_create_only(tmp_path):
    repo = FilesystemWorkspaceRepository(tmp_path / "expedientes")
    repo.create_patient("P-001")

    raw_file = repo.create_raw_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        consultation_number=1,
        content="Paciente refiere dolor de cabeza.",
    )

    content = raw_file.read_text(encoding="utf-8")
    assert raw_file.name == "2026-05-22_consulta.md"
    assert "paciente_id: P-001" in content
    assert "medico_id: M-001" in content
    assert "fecha_consulta: 2026-05-22" in content
    assert "numero_consulta: 1" in content
    assert "tipo_entrada: voz" in content
    assert "agente_origen: whisper" in content
    assert "tipo_documento: crudo" in content
    assert "Paciente refiere dolor de cabeza." in content

    with pytest.raises(ConsultationAlreadyExistsError):
        repo.create_raw_consultation(
            patient_id="P-001",
            medico_id="M-001",
            consultation_date=date(2026, 5, 22),
            consultation_number=2,
            content="Otro contenido",
        )


def test_read_raw_consultation_body_strips_frontmatter(tmp_path):
    repo = FilesystemWorkspaceRepository(tmp_path / "expedientes")
    repo.create_patient("P-001")
    repo.create_raw_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        consultation_number=1,
        content="Paciente refiere dolor de cabeza.",
    )

    body = repo.read_raw_consultation_body(patient_id="P-001", consultation_date=date(2026, 5, 22))

    assert "paciente_id:" not in body
    assert "Paciente refiere dolor de cabeza." in body


def test_read_raw_consultation_body_requires_existing_raw_file(tmp_path):
    repo = FilesystemWorkspaceRepository(tmp_path / "expedientes")
    repo.create_patient("P-001")

    with pytest.raises(ConsultationNotFoundError):
        repo.read_raw_consultation_body(patient_id="P-001", consultation_date=date(2026, 5, 22))


def test_create_medical_consultation_writes_frontmatter_updates_index_and_is_create_only(tmp_path):
    repo = FilesystemWorkspaceRepository(tmp_path / "expedientes")
    patient = repo.create_patient("P-001")
    repo.create_raw_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        consultation_number=1,
        content="Texto crudo.",
    )

    medical_file = repo.create_medical_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        consultation_number=1,
        content="# Borrador revisado\n\nPlan médico.",
    )

    content = medical_file.read_text(encoding="utf-8")
    index = patient.index_file.read_text(encoding="utf-8")
    assert medical_file.name == "2026-05-22_consulta.md"
    assert "tipo_documento: medico" in content
    assert "agente_origen: formateador" in content
    assert "# Borrador revisado" in content
    assert "| # | Fecha | Entrada | Motivo | Archivos |" in index
    assert "| 1 | 2026-05-22 | voz |  |" in index
    assert "[crudo](Formato crudo/2026-05-22_consulta.md)" in index
    assert "[médico](Formato médico/2026-05-22_consulta.md)" in index

    with pytest.raises(ConsultationAlreadyExistsError):
        repo.create_medical_consultation(
            patient_id="P-001",
            medico_id="M-001",
            consultation_date=date(2026, 5, 22),
            consultation_number=2,
            content="Duplicado",
        )


def test_create_medical_consultation_requires_raw_file(tmp_path):
    repo = FilesystemWorkspaceRepository(tmp_path / "expedientes")
    repo.create_patient("P-001")

    with pytest.raises(ConsultationNotFoundError):
        repo.create_medical_consultation(
            patient_id="P-001",
            medico_id="M-001",
            consultation_date=date(2026, 5, 22),
            consultation_number=1,
            content="Borrador",
        )


def test_list_medical_consultations_returns_bodies_with_references(tmp_path):
    repo = FilesystemWorkspaceRepository(tmp_path / "expedientes")
    repo.create_patient("P-001")
    repo.create_raw_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        consultation_number=1,
        content="Texto crudo.",
    )
    repo.create_medical_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        consultation_number=1,
        content="# Consulta médica\n\nPlan médico.",
    )

    documents = repo.list_medical_consultations("P-001")

    assert len(documents) == 1
    assert documents[0].consultation_date == date(2026, 5, 22)
    assert documents[0].file.name == "2026-05-22_consulta.md"
    assert "# Consulta médica" in documents[0].body
    assert "tipo_documento:" not in documents[0].body


def test_append_patient_log_is_append_only(tmp_path):
    repo = FilesystemWorkspaceRepository(tmp_path / "expedientes")
    patient = repo.create_patient("P-001")
    before = patient.log_file.read_text(encoding="utf-8")

    repo.append_patient_log(
        "P-001",
        LogEntry(
            timestamp=datetime(2026, 5, 22, 14, 35),
            agent="Orquestador",
            action="Creación de Formato Crudo",
            location="Formato crudo/2026-05-22_consulta.md",
            reason="Entrada de voz recibida para consulta del día",
        ),
    )

    after = patient.log_file.read_text(encoding="utf-8")
    assert after.startswith(before)
    assert "## 2026-05-22 14:35 — Creación de Formato Crudo" in after
    assert "- **Agente:** Orquestador" in after
    assert "- **Dónde:** Formato crudo/2026-05-22_consulta.md" in after
