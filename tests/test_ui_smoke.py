from __future__ import annotations

import os
from datetime import date

import pytest

from expediente.application.orchestrator import OrchestratorService
from expediente.storage.filesystem import FilesystemWorkspaceRepository
from expediente.ui.main_window import MainWindowFactory, MissingDesktopDependencyError


def test_main_window_factory_reports_missing_pyside6(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    factory = MainWindowFactory(service)

    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        with pytest.raises(MissingDesktopDependencyError):
            factory.create()
    else:
        app = QApplication.instance() or QApplication([])
        assert factory.create().windowTitle() == "Expediente Vivo"
        assert app is not None


def test_dashboard_shows_safe_model_provider_status(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("EXPEDIENTE_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("EXPEDIENTE_MODEL_API_KEY", "secret-key")
    monkeypatch.setenv("EXPEDIENTE_MODEL_NAME", "gpt-test")

    try:
        from PySide6.QtWidgets import QApplication, QLabel
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    window = MainWindowFactory(service).create()

    model_status = window.findChild(QLabel, "modelProviderStatusLabel")

    assert model_status.text() == "Modelo: openai / gpt-test — API key configurada"
    assert "secret-key" not in model_status.text()
    assert app is not None


def test_dashboard_groups_workflows_in_tabs(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QTabWidget
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    window = MainWindowFactory(service).create()

    tabs = window.findChild(QTabWidget, "mainWorkflowTabs")

    assert [tabs.tabText(index) for index in range(tabs.count())] == [
        "Pacientes",
        "Consulta",
        "Formateador",
        "Investigador",
        "Configuración",
    ]
    assert app is not None


def test_dashboard_can_create_patient_from_form(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QListWidget, QPushButton
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    window = MainWindowFactory(service).create()

    patient_input = window.findChild(QLineEdit, "patientIdInput")
    create_button = window.findChild(QPushButton, "createPatientButton")
    status = window.findChild(QLabel, "statusLabel")
    patient_count = window.findChild(QLabel, "patientCountLabel")
    patient_list = window.findChild(QListWidget, "patientListWidget")
    patient_detail = window.findChild(QLabel, "patientDetailLabel")

    patient_input.setText(" P-001 ")
    create_button.click()
    app.processEvents()

    assert service.list_patients() == ["P-001"]
    assert status.text() == "Paciente P-001 creado."
    assert patient_count.text() == "Pacientes registrados: 1"
    assert patient_list.count() == 1
    assert patient_list.item(0).text() == "P-001"
    assert "Paciente: P-001" in patient_detail.text()
    assert "Formatos crudos: 0" in patient_detail.text()


def test_dashboard_reports_duplicate_patient(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")
    window = MainWindowFactory(service).create()

    patient_input = window.findChild(QLineEdit, "patientIdInput")
    create_button = window.findChild(QPushButton, "createPatientButton")
    status = window.findChild(QLabel, "statusLabel")

    patient_input.setText("P-001")
    create_button.click()
    app.processEvents()

    assert status.text() == "El paciente P-001 ya existe."


def test_dashboard_requires_patient_id(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    window = MainWindowFactory(service).create()

    patient_input = window.findChild(QLineEdit, "patientIdInput")
    create_button = window.findChild(QPushButton, "createPatientButton")
    status = window.findChild(QLabel, "statusLabel")

    patient_input.setText("   ")
    create_button.click()
    app.processEvents()

    assert status.text() == "Ingresá un ID de paciente."
    assert service.list_patients() == []


def test_dashboard_shows_selected_patient_detail(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QListWidget
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")
    service.create_patient("P-002")
    window = MainWindowFactory(service).create()

    patient_list = window.findChild(QListWidget, "patientListWidget")
    patient_detail = window.findChild(QLabel, "patientDetailLabel")

    patient_list.setCurrentRow(1)
    app.processEvents()

    assert patient_list.currentItem().text() == "P-002"
    assert "Paciente: P-002" in patient_detail.text()
    assert "Index:" in patient_detail.text()
    assert "Log:" in patient_detail.text()


def test_dashboard_can_create_raw_consultation_for_selected_patient(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QListWidget, QPushButton, QTextEdit
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")
    window = MainWindowFactory(service).create()

    patient_list = window.findChild(QListWidget, "patientListWidget")
    raw_date = window.findChild(QLineEdit, "rawConsultationDateInput")
    raw_content = window.findChild(QTextEdit, "rawConsultationContentInput")
    create_raw = window.findChild(QPushButton, "createRawConsultationButton")
    status = window.findChild(QLabel, "statusLabel")
    patient_detail = window.findChild(QLabel, "patientDetailLabel")

    patient_list.setCurrentRow(0)
    raw_date.setText("2026-05-22")
    raw_content.setPlainText("Paciente refiere dolor de cabeza.")
    create_raw.click()
    app.processEvents()

    raw_file = service.repository.build_consultation_paths("P-001", date(2026, 5, 22)).raw_file
    assert raw_file.exists()
    assert status.text() == "Formato Crudo guardado: 2026-05-22_consulta.md"
    assert "Formatos crudos: 1" in patient_detail.text()


def test_dashboard_requires_selected_patient_for_raw_consultation(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    window = MainWindowFactory(service).create()

    raw_content = window.findChild(QTextEdit, "rawConsultationContentInput")
    create_raw = window.findChild(QPushButton, "createRawConsultationButton")
    status = window.findChild(QLabel, "statusLabel")

    raw_content.setPlainText("Texto crudo")
    create_raw.click()
    app.processEvents()

    assert status.text() == "Seleccioná un paciente antes de guardar el Formato Crudo."


def test_dashboard_reports_duplicate_raw_consultation(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QListWidget, QPushButton, QTextEdit
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")
    window = MainWindowFactory(service).create()

    patient_list = window.findChild(QListWidget, "patientListWidget")
    raw_date = window.findChild(QLineEdit, "rawConsultationDateInput")
    raw_content = window.findChild(QTextEdit, "rawConsultationContentInput")
    create_raw = window.findChild(QPushButton, "createRawConsultationButton")
    status = window.findChild(QLabel, "statusLabel")

    patient_list.setCurrentRow(0)
    raw_date.setText("2026-05-22")
    raw_content.setPlainText("Primera consulta")
    create_raw.click()
    raw_content.setPlainText("Duplicada")
    create_raw.click()
    app.processEvents()

    assert status.text() == "Ya existe un Formato Crudo para esa fecha."


def test_dashboard_generates_medical_draft_preview(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QListWidget, QPushButton, QTextEdit
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")
    service.create_raw_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        content="Paciente refiere dolor de cabeza.",
    )
    window = MainWindowFactory(service).create()

    patient_list = window.findChild(QListWidget, "patientListWidget")
    raw_date = window.findChild(QLineEdit, "rawConsultationDateInput")
    generate_draft = window.findChild(QPushButton, "generateMedicalDraftButton")
    draft_preview = window.findChild(QTextEdit, "medicalDraftPreview")
    status = window.findChild(QLabel, "statusLabel")

    patient_list.setCurrentRow(0)
    raw_date.setText("2026-05-22")
    generate_draft.click()
    app.processEvents()

    assert "# Borrador de Formato Médico — Paciente P-001" in draft_preview.toPlainText()
    assert "Paciente refiere dolor de cabeza." in draft_preview.toPlainText()
    assert status.text() == "Borrador médico generado. Revisalo antes de guardar definitivo."


def test_dashboard_reports_missing_raw_for_medical_draft(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QListWidget, QPushButton
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")
    window = MainWindowFactory(service).create()

    patient_list = window.findChild(QListWidget, "patientListWidget")
    raw_date = window.findChild(QLineEdit, "rawConsultationDateInput")
    generate_draft = window.findChild(QPushButton, "generateMedicalDraftButton")
    status = window.findChild(QLabel, "statusLabel")

    patient_list.setCurrentRow(0)
    raw_date.setText("2026-05-22")
    generate_draft.click()
    app.processEvents()

    assert status.text() == "No existe un Formato Crudo para esa fecha."


def test_dashboard_saves_definitive_medical_consultation(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QListWidget, QPushButton, QTextEdit
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")
    service.create_raw_consultation(
        patient_id="P-001",
        medico_id="M-001",
        consultation_date=date(2026, 5, 22),
        content="Texto crudo.",
    )
    window = MainWindowFactory(service).create()

    patient_list = window.findChild(QListWidget, "patientListWidget")
    raw_date = window.findChild(QLineEdit, "rawConsultationDateInput")
    draft_preview = window.findChild(QTextEdit, "medicalDraftPreview")
    save_medical = window.findChild(QPushButton, "saveMedicalConsultationButton")
    status = window.findChild(QLabel, "statusLabel")
    patient_detail = window.findChild(QLabel, "patientDetailLabel")

    patient_list.setCurrentRow(0)
    raw_date.setText("2026-05-22")
    draft_preview.setPlainText("# Borrador revisado\n\nPlan médico.")
    save_medical.click()
    app.processEvents()

    medical_file = service.repository.build_consultation_paths("P-001", date(2026, 5, 22)).medical_file
    assert medical_file.exists()
    assert status.text() == "Formato Médico definitivo guardado: 2026-05-22_consulta.md"
    assert "Formatos médicos: 1" in patient_detail.text()


def test_dashboard_requires_draft_before_saving_medical_consultation(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QPushButton
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")
    window = MainWindowFactory(service).create()

    patient_list = window.findChild(QListWidget, "patientListWidget")
    save_medical = window.findChild(QPushButton, "saveMedicalConsultationButton")
    status = window.findChild(QLabel, "statusLabel")

    patient_list.setCurrentRow(0)
    save_medical.click()
    app.processEvents()

    assert status.text() == "Generá o pegá un borrador médico antes de guardar definitivo."


def test_dashboard_reports_duplicate_definitive_medical_consultation(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QListWidget, QPushButton, QTextEdit
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
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
        content="# Borrador revisado",
    )
    window = MainWindowFactory(service).create()

    patient_list = window.findChild(QListWidget, "patientListWidget")
    raw_date = window.findChild(QLineEdit, "rawConsultationDateInput")
    draft_preview = window.findChild(QTextEdit, "medicalDraftPreview")
    save_medical = window.findChild(QPushButton, "saveMedicalConsultationButton")
    status = window.findChild(QLabel, "statusLabel")

    patient_list.setCurrentRow(0)
    raw_date.setText("2026-05-22")
    draft_preview.setPlainText("# Otro borrador")
    save_medical.click()
    app.processEvents()

    assert status.text() == "Ya existe un Formato Médico para esa fecha."


def test_dashboard_investigator_answers_from_medical_documents(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QListWidget, QPushButton, QTextEdit
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
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
    window = MainWindowFactory(service).create()

    patient_list = window.findChild(QListWidget, "patientListWidget")
    question = window.findChild(QLineEdit, "investigatorQuestionInput")
    ask = window.findChild(QPushButton, "askInvestigatorButton")
    answer = window.findChild(QTextEdit, "investigatorAnswerPreview")
    status = window.findChild(QLabel, "statusLabel")

    patient_list.setCurrentRow(0)
    question.setText("¿Cuál es el plan?")
    ask.click()
    app.processEvents()

    assert "## Consulta 2026-05-22" in answer.toPlainText()
    assert "Plan médico." in answer.toPlainText()
    assert status.text() == "Investigador respondió con referencias a Formato Médico."


def test_dashboard_investigator_requires_question(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QPushButton
    except ModuleNotFoundError:
        pytest.skip("PySide6 is not installed")

    app = QApplication.instance() or QApplication([])
    service = OrchestratorService(FilesystemWorkspaceRepository(tmp_path / "expedientes"))
    service.create_patient("P-001")
    window = MainWindowFactory(service).create()

    patient_list = window.findChild(QListWidget, "patientListWidget")
    ask = window.findChild(QPushButton, "askInvestigatorButton")
    status = window.findChild(QLabel, "statusLabel")

    patient_list.setCurrentRow(0)
    ask.click()
    app.processEvents()

    assert status.text() == "Ingresá una pregunta para el Investigador."
