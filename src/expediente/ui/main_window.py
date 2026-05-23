from __future__ import annotations

from datetime import date

from expediente.application.orchestrator import OrchestratorService
from expediente.llm.gateway import inspect_model_provider_env
from expediente.storage.filesystem import (
    ConsultationAlreadyExistsError,
    ConsultationNotFoundError,
    PatientAlreadyExistsError,
    PatientNotFoundError,
)


class MissingDesktopDependencyError(RuntimeError):
    """Raised when PySide6 is not installed for the desktop shell."""


class MainWindowFactory:
    def __init__(self, orchestrator: OrchestratorService) -> None:
        self.orchestrator = orchestrator

    def create(self):
        try:
            from PySide6.QtWidgets import (
                QLabel,
                QLineEdit,
                QListWidget,
                QMainWindow,
                QPushButton,
                QTabWidget,
                QTextEdit,
                QVBoxLayout,
                QWidget,
            )
        except ModuleNotFoundError as exc:
            raise MissingDesktopDependencyError(
                "PySide6 is required for the desktop dashboard. Install with `pip install -e .[desktop]`."
            ) from exc

        window = QMainWindow()
        window.setWindowTitle("Expediente Vivo")

        title = QLabel("Expediente Vivo")
        title.setObjectName("titleLabel")

        model_status = QLabel(inspect_model_provider_env().safe_label())
        model_status.setObjectName("modelProviderStatusLabel")

        patient_count = QLabel(self._patient_count_text())
        patient_count.setObjectName("patientCountLabel")

        patient_list = QListWidget()
        patient_list.setObjectName("patientListWidget")
        self._refresh_patient_list(patient_list, patient_count)

        patient_id_input = QLineEdit()
        patient_id_input.setObjectName("patientIdInput")
        patient_id_input.setPlaceholderText("ID del paciente, ej. P-001")

        status = QLabel("")
        status.setObjectName("statusLabel")

        patient_detail = QLabel("Seleccioná un paciente para ver el detalle.")
        patient_detail.setObjectName("patientDetailLabel")
        patient_detail.setWordWrap(True)

        raw_date_input = QLineEdit(date.today().isoformat())
        raw_date_input.setObjectName("rawConsultationDateInput")
        raw_date_input.setPlaceholderText("Fecha YYYY-MM-DD")

        raw_content_input = QTextEdit()
        raw_content_input.setObjectName("rawConsultationContentInput")
        raw_content_input.setPlaceholderText("Pegá o escribí la transcripción cruda de la consulta")

        create_raw_consultation = QPushButton("Guardar Formato Crudo")
        create_raw_consultation.setObjectName("createRawConsultationButton")

        medical_draft_preview = QTextEdit()
        medical_draft_preview.setObjectName("medicalDraftPreview")
        medical_draft_preview.setReadOnly(True)
        medical_draft_preview.setPlaceholderText("El borrador médico aparecerá acá")

        generate_medical_draft = QPushButton("Generar Borrador Médico")
        generate_medical_draft.setObjectName("generateMedicalDraftButton")

        save_medical_consultation = QPushButton("Confirmar y Guardar Formato Médico")
        save_medical_consultation.setObjectName("saveMedicalConsultationButton")

        investigator_question = QLineEdit()
        investigator_question.setObjectName("investigatorQuestionInput")
        investigator_question.setPlaceholderText("Pregunta sobre el paciente seleccionado")

        ask_investigator = QPushButton("Consultar Investigador")
        ask_investigator.setObjectName("askInvestigatorButton")

        investigator_answer = QTextEdit()
        investigator_answer.setObjectName("investigatorAnswerPreview")
        investigator_answer.setReadOnly(True)
        investigator_answer.setPlaceholderText("La respuesta del Investigador aparecerá acá")

        create_patient = QPushButton("Crear paciente")
        create_patient.setObjectName("createPatientButton")

        def handle_create_patient() -> None:
            patient_id = patient_id_input.text().strip()
            if not patient_id:
                status.setText("Ingresá un ID de paciente.")
                return

            try:
                self.orchestrator.create_patient(patient_id)
            except PatientAlreadyExistsError:
                status.setText(f"El paciente {patient_id} ya existe.")
                return
            except ValueError as exc:
                status.setText(str(exc))
                return

            patient_id_input.clear()
            status.setText(f"Paciente {patient_id} creado.")
            self._refresh_patient_list(patient_list, patient_count)
            self._select_patient(patient_list, patient_id)
            self._show_patient_detail(patient_id, patient_detail)

        create_patient.clicked.connect(handle_create_patient)

        def handle_create_raw_consultation() -> None:
            selected_item = patient_list.currentItem()
            if selected_item is None:
                status.setText("Seleccioná un paciente antes de guardar el Formato Crudo.")
                return

            raw_text = raw_content_input.toPlainText().strip()
            if not raw_text:
                status.setText("Ingresá el texto crudo de la consulta.")
                return

            try:
                consultation_date = date.fromisoformat(raw_date_input.text().strip())
                raw_file = self.orchestrator.create_raw_consultation(
                    patient_id=selected_item.text(),
                    medico_id="M-001",
                    consultation_date=consultation_date,
                    content=raw_text,
                )
            except ValueError as exc:
                status.setText(str(exc))
                return
            except ConsultationAlreadyExistsError:
                status.setText("Ya existe un Formato Crudo para esa fecha.")
                return
            except PatientNotFoundError:
                status.setText("El paciente seleccionado ya no existe.")
                return

            raw_content_input.clear()
            status.setText(f"Formato Crudo guardado: {raw_file.name}")
            self._show_patient_detail(selected_item.text(), patient_detail)

        create_raw_consultation.clicked.connect(handle_create_raw_consultation)

        def handle_generate_medical_draft() -> None:
            selected_item = patient_list.currentItem()
            if selected_item is None:
                status.setText("Seleccioná un paciente antes de generar el borrador médico.")
                return

            try:
                consultation_date = date.fromisoformat(raw_date_input.text().strip())
                draft = self.orchestrator.generate_medical_draft(
                    patient_id=selected_item.text(),
                    consultation_date=consultation_date,
                )
            except ValueError as exc:
                status.setText(str(exc))
                return
            except ConsultationNotFoundError:
                status.setText("No existe un Formato Crudo para esa fecha.")
                return
            except PatientNotFoundError:
                status.setText("El paciente seleccionado ya no existe.")
                return

            medical_draft_preview.setPlainText(draft)
            status.setText("Borrador médico generado. Revisalo antes de guardar definitivo.")

        generate_medical_draft.clicked.connect(handle_generate_medical_draft)

        def handle_save_medical_consultation() -> None:
            selected_item = patient_list.currentItem()
            if selected_item is None:
                status.setText("Seleccioná un paciente antes de guardar el Formato Médico.")
                return

            draft = medical_draft_preview.toPlainText().strip()
            if not draft:
                status.setText("Generá o pegá un borrador médico antes de guardar definitivo.")
                return

            try:
                consultation_date = date.fromisoformat(raw_date_input.text().strip())
                medical_file = self.orchestrator.save_medical_consultation(
                    patient_id=selected_item.text(),
                    medico_id="M-001",
                    consultation_date=consultation_date,
                    content=draft,
                )
            except ValueError as exc:
                status.setText(str(exc))
                return
            except ConsultationNotFoundError:
                status.setText("No existe un Formato Crudo para esa fecha.")
                return
            except ConsultationAlreadyExistsError:
                status.setText("Ya existe un Formato Médico para esa fecha.")
                return
            except PatientNotFoundError:
                status.setText("El paciente seleccionado ya no existe.")
                return

            status.setText(f"Formato Médico definitivo guardado: {medical_file.name}")
            self._show_patient_detail(selected_item.text(), patient_detail)

        save_medical_consultation.clicked.connect(handle_save_medical_consultation)

        def handle_ask_investigator() -> None:
            selected_item = patient_list.currentItem()
            if selected_item is None:
                status.setText("Seleccioná un paciente antes de consultar al Investigador.")
                return

            question = investigator_question.text().strip()
            if not question:
                status.setText("Ingresá una pregunta para el Investigador.")
                return

            try:
                answer = self.orchestrator.answer_patient_question(
                    patient_id=selected_item.text(),
                    question=question,
                )
            except PatientNotFoundError:
                status.setText("El paciente seleccionado ya no existe.")
                return
            except ValueError as exc:
                status.setText(str(exc))
                return

            investigator_answer.setPlainText(answer)
            status.setText("Investigador respondió con referencias a Formato Médico.")

        ask_investigator.clicked.connect(handle_ask_investigator)

        patient_list.currentTextChanged.connect(lambda patient_id: self._show_patient_detail(patient_id, patient_detail))

        refresh = QPushButton("Actualizar pacientes")
        refresh.setObjectName("refreshPatientsButton")
        refresh.clicked.connect(lambda: self._refresh_patient_list(patient_list, patient_count, patient_detail))

        tabs = QTabWidget()
        tabs.setObjectName("mainWorkflowTabs")

        patients_tab = QWidget()
        patients_layout = QVBoxLayout()
        patients_layout.addWidget(patient_count)
        patients_layout.addWidget(patient_list)
        patients_layout.addWidget(patient_detail)
        patients_layout.addWidget(patient_id_input)
        patients_layout.addWidget(create_patient)
        patients_layout.addWidget(refresh)
        patients_tab.setLayout(patients_layout)

        raw_tab = QWidget()
        raw_layout = QVBoxLayout()
        raw_layout.addWidget(raw_date_input)
        raw_layout.addWidget(raw_content_input)
        raw_layout.addWidget(create_raw_consultation)
        raw_tab.setLayout(raw_layout)

        formatter_tab = QWidget()
        formatter_layout = QVBoxLayout()
        formatter_layout.addWidget(generate_medical_draft)
        formatter_layout.addWidget(medical_draft_preview)
        formatter_layout.addWidget(save_medical_consultation)
        formatter_tab.setLayout(formatter_layout)

        investigator_tab = QWidget()
        investigator_layout = QVBoxLayout()
        investigator_layout.addWidget(investigator_question)
        investigator_layout.addWidget(ask_investigator)
        investigator_layout.addWidget(investigator_answer)
        investigator_tab.setLayout(investigator_layout)

        config_tab = QWidget()
        config_layout = QVBoxLayout()
        config_layout.addWidget(model_status)
        config_tab.setLayout(config_layout)

        tabs.addTab(patients_tab, "Pacientes")
        tabs.addTab(raw_tab, "Consulta")
        tabs.addTab(formatter_tab, "Formateador")
        tabs.addTab(investigator_tab, "Investigador")
        tabs.addTab(config_tab, "Configuración")

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(tabs)
        layout.addWidget(status)

        container = QWidget()
        container.setLayout(layout)
        window.setCentralWidget(container)
        return window

    def _patient_count_text(self) -> str:
        count = len(self.orchestrator.list_patients())
        return f"Pacientes registrados: {count}"

    def _refresh_patient_list(self, patient_list, patient_count, patient_detail=None) -> None:
        selected_patient_id = patient_list.currentItem().text() if patient_list.currentItem() else ""
        patient_ids = self.orchestrator.list_patients()
        patient_list.clear()
        patient_list.addItems(patient_ids)
        patient_count.setText(f"Pacientes registrados: {len(patient_ids)}")
        if selected_patient_id in patient_ids:
            self._select_patient(patient_list, selected_patient_id)
        elif patient_detail is not None:
            patient_detail.setText("Seleccioná un paciente para ver el detalle.")

    def _select_patient(self, patient_list, patient_id: str) -> None:
        for index in range(patient_list.count()):
            item = patient_list.item(index)
            if item.text() == patient_id:
                patient_list.setCurrentItem(item)
                return

    def _show_patient_detail(self, patient_id: str, patient_detail) -> None:
        if not patient_id:
            patient_detail.setText("Seleccioná un paciente para ver el detalle.")
            return

        try:
            summary = self.orchestrator.get_patient_summary(patient_id)
        except PatientNotFoundError:
            patient_detail.setText(f"El paciente {patient_id} ya no existe.")
            return

        patient_detail.setText(
            "\n".join(
                [
                    f"Paciente: {summary.patient_id}",
                    f"Formatos crudos: {summary.raw_consultation_count}",
                    f"Formatos médicos: {summary.medical_consultation_count}",
                    f"Index: {summary.index_file}",
                    f"Log: {summary.log_file}",
                ]
            )
        )
