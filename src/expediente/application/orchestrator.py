from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from expediente.domain.models import LogEntry, PatientPaths, PatientSummary, WorkspacePaths
from expediente.llm.gateway import ModelGateway
from expediente.storage.filesystem import FilesystemWorkspaceRepository


@dataclass
class OrchestratorService:
    repository: FilesystemWorkspaceRepository
    model_gateway: ModelGateway | None = None

    def bootstrap_workspace(self) -> WorkspacePaths:
        return self.repository.bootstrap_workspace()

    def create_patient(self, patient_id: str) -> PatientPaths:
        patient = self.repository.create_patient(patient_id)
        self.record_operation(
            patient_id=patient_id,
            agent="Orquestador",
            action="Creación de expediente de paciente",
            location=str(patient.root),
            reason="Paciente nuevo registrado desde el dashboard",
        )
        return patient

    def list_patients(self) -> list[str]:
        return self.repository.list_patient_ids()

    def get_patient_summary(self, patient_id: str) -> PatientSummary:
        return self.repository.patient_summary(patient_id)

    def create_raw_consultation(
        self,
        *,
        patient_id: str,
        medico_id: str,
        consultation_date: date,
        content: str,
    ) -> Path:
        consultation_number = self.repository.patient_summary(patient_id).raw_consultation_count + 1
        raw_file = self.repository.create_raw_consultation(
            patient_id=patient_id,
            medico_id=medico_id,
            consultation_date=consultation_date,
            consultation_number=consultation_number,
            content=content,
        )
        self.record_operation(
            patient_id=patient_id,
            agent="Orquestador",
            action="Creación de Formato Crudo",
            location=str(raw_file),
            reason="Texto crudo ingresado desde el dashboard",
        )
        return raw_file

    def generate_medical_draft(self, *, patient_id: str, consultation_date: date) -> str:
        template = self.repository.read_doctor_template()
        raw_body = self.repository.read_raw_consultation_body(
            patient_id=patient_id,
            consultation_date=consultation_date,
        )
        if self.model_gateway is not None:
            return self.model_gateway.complete(
                system=(
                    "Sos el Formateador de Expediente Vivo. Generá un borrador de Formato Médico "
                    "siguiendo la plantilla del médico. No inventes datos; si falta información, dejá el campo vacío."
                ),
                user=(
                    f"Paciente: {patient_id}\n"
                    f"Fecha: {consultation_date.isoformat()}\n\n"
                    f"Plantilla:\n{template}\n\n"
                    f"Formato Crudo:\n{raw_body}"
                ),
            )
        return (
            f"# Borrador de Formato Médico — Paciente {patient_id}\n\n"
            "Este borrador es determinístico y requiere revisión médica antes de guardarse como definitivo.\n\n"
            "## Plantilla\n\n"
            f"{template}\n\n"
            "## Fuente — Formato Crudo\n\n"
            f"{raw_body}\n"
        )

    def save_medical_consultation(
        self,
        *,
        patient_id: str,
        medico_id: str,
        consultation_date: date,
        content: str,
    ) -> Path:
        consultation_number = self.repository.patient_summary(patient_id).medical_consultation_count + 1
        medical_file = self.repository.create_medical_consultation(
            patient_id=patient_id,
            medico_id=medico_id,
            consultation_date=consultation_date,
            consultation_number=consultation_number,
            content=content,
        )
        self.record_operation(
            patient_id=patient_id,
            agent="Formateador",
            action="Creación de Formato Médico",
            location=str(medical_file),
            reason="Borrador aprobado por el médico desde el dashboard",
        )
        return medical_file

    def answer_patient_question(self, *, patient_id: str, question: str) -> str:
        question = question.strip()
        if not question:
            raise ValueError("question is required")

        documents = self.repository.list_medical_consultations(patient_id)
        if not documents:
            return f"No hay Formatos Médicos definitivos disponibles para el paciente {patient_id}."

        source_context = "\n\n".join(
            [
                f"Consulta {document.consultation_date.isoformat()}\nReferencia: {document.file}\n{document.body}"
                for document in documents
            ]
        )
        if self.model_gateway is not None:
            return self.model_gateway.complete(
                system=(
                    "Sos el Investigador de Expediente Vivo. Respondé solo con información presente "
                    "en los Formatos Médicos provistos e incluí referencias por fecha y archivo."
                ),
                user=f"Paciente: {patient_id}\nPregunta: {question}\n\nDocumentos:\n{source_context}",
            )

        sections = [
            f"Respuesta basada en {len(documents)} Formato(s) Médico(s) definitivo(s) para {patient_id}.",
            f"Pregunta: {question}",
            "",
        ]
        for document in documents:
            sections.extend(
                [
                    f"## Consulta {document.consultation_date.isoformat()}",
                    f"Referencia: {document.file}",
                    document.body,
                    "",
                ]
            )
        return "\n".join(sections).strip()

    def record_operation(
        self,
        *,
        patient_id: str,
        agent: str,
        action: str,
        location: str,
        reason: str,
        timestamp: datetime | None = None,
    ) -> None:
        entry = LogEntry(
            timestamp=timestamp or datetime.now(),
            agent=agent,
            action=action,
            location=location,
            reason=reason,
        )
        self.repository.append_patient_log(patient_id, entry)
