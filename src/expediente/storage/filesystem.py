from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from expediente.domain.models import (
    ConsultationPaths,
    LogEntry,
    MedicalConsultationDocument,
    PatientPaths,
    PatientSummary,
    WorkspacePaths,
)


AGENTS_MD_TEMPLATE = """# AGENTS.md — Expediente Vivo

## Estructura
- Cada paciente vive en `expedientes/pacientes/{paciente_id}/`
- Formato Crudo usa `Formato crudo/YYYY-MM-DD_consulta.md`
- Formato Médico usa `Formato médico/YYYY-MM-DD_consulta.md`
- Los archivos de consulta son inmutables una vez creados
- Solo `index.md` y `log.md` son superficies mutables
- `log.md` es append-only y solo lo escribe el Orquestador
"""

DOCTOR_TEMPLATE = """# Plantilla del médico

## Motivo de consulta

## Resumen clínico

## Plan
"""

GLOBAL_INDEX_TEMPLATE = "# Pacientes registrados\n\n"


class PatientAlreadyExistsError(FileExistsError):
    """Raised when a patient directory already exists."""


class PatientNotFoundError(FileNotFoundError):
    """Raised when a patient directory does not exist."""


class ConsultationAlreadyExistsError(FileExistsError):
    """Raised when a consultation document already exists."""


class ConsultationNotFoundError(FileNotFoundError):
    """Raised when a consultation document does not exist."""


@dataclass
class FilesystemWorkspaceRepository:
    root: Path

    def workspace_paths(self) -> WorkspacePaths:
        medico_dir = self.root / "medico"
        patients_dir = self.root / "pacientes"
        return WorkspacePaths(
            root=self.root,
            medico_dir=medico_dir,
            patients_dir=patients_dir,
            global_index_file=self.root / "index_global.md",
            agents_file=self.root / "AGENTS.md",
        )

    def bootstrap_workspace(self) -> WorkspacePaths:
        paths = self.workspace_paths()
        paths.medico_dir.mkdir(parents=True, exist_ok=True)
        paths.patients_dir.mkdir(parents=True, exist_ok=True)

        self._write_if_missing(paths.medico_dir / "plantilla.md", DOCTOR_TEMPLATE)
        self._write_if_missing(paths.global_index_file, GLOBAL_INDEX_TEMPLATE)
        self._write_if_missing(paths.agents_file, AGENTS_MD_TEMPLATE)
        return paths

    def patient_paths(self, patient_id: str) -> PatientPaths:
        self._validate_patient_id(patient_id)
        root = self.workspace_paths().patients_dir / patient_id
        return PatientPaths(
            patient_id=patient_id,
            root=root,
            index_file=root / "index.md",
            log_file=root / "log.md",
            raw_dir=root / "Formato crudo",
            medical_dir=root / "Formato médico",
        )

    def create_patient(self, patient_id: str) -> PatientPaths:
        self.bootstrap_workspace()
        paths = self.patient_paths(patient_id)
        if paths.root.exists():
            raise PatientAlreadyExistsError(f"Patient '{patient_id}' already exists")

        paths.raw_dir.mkdir(parents=True, exist_ok=False)
        paths.medical_dir.mkdir(parents=True, exist_ok=False)
        self._write_text(paths.index_file, f"# Expediente — Paciente {patient_id}\n\n")
        self._write_text(paths.log_file, "# Registro de operaciones\n\n")
        return paths

    def list_patient_ids(self) -> list[str]:
        patients_dir = self.workspace_paths().patients_dir
        if not patients_dir.exists():
            return []
        return sorted(path.name for path in patients_dir.iterdir() if path.is_dir())

    def patient_summary(self, patient_id: str) -> PatientSummary:
        paths = self.patient_paths(patient_id)
        if not paths.root.exists():
            raise PatientNotFoundError(f"Patient '{patient_id}' does not exist")

        return PatientSummary(
            patient_id=patient_id,
            raw_consultation_count=self._markdown_file_count(paths.raw_dir),
            medical_consultation_count=self._markdown_file_count(paths.medical_dir),
            index_file=paths.index_file,
            log_file=paths.log_file,
        )

    def build_consultation_paths(self, patient_id: str, consultation_date: date) -> ConsultationPaths:
        paths = self.patient_paths(patient_id)
        filename = f"{consultation_date.isoformat()}_consulta.md"
        return ConsultationPaths(
            raw_file=paths.raw_dir / filename,
            medical_file=paths.medical_dir / filename,
            filename=filename,
        )

    def create_raw_consultation(
        self,
        *,
        patient_id: str,
        medico_id: str,
        consultation_date: date,
        consultation_number: int,
        content: str,
        input_type: str = "voz",
        source_agent: str = "whisper",
    ) -> Path:
        patient_paths = self.patient_paths(patient_id)
        if not patient_paths.root.exists():
            raise PatientNotFoundError(f"Patient '{patient_id}' does not exist")
        if not content.strip():
            raise ValueError("raw consultation content is required")
        if consultation_number < 1:
            raise ValueError("consultation_number must be greater than zero")

        paths = self.build_consultation_paths(patient_id, consultation_date)
        if paths.raw_file.exists():
            raise ConsultationAlreadyExistsError(f"Raw consultation already exists: {paths.raw_file}")

        document = self._render_raw_consultation(
            patient_id=patient_id,
            medico_id=medico_id,
            consultation_date=consultation_date,
            consultation_number=consultation_number,
            input_type=input_type,
            source_agent=source_agent,
            content=content.strip(),
        )
        self._write_text(paths.raw_file, document)
        return paths.raw_file

    def create_medical_consultation(
        self,
        *,
        patient_id: str,
        medico_id: str,
        consultation_date: date,
        consultation_number: int,
        content: str,
        input_type: str = "voz",
        source_agent: str = "formateador",
    ) -> Path:
        patient_paths = self.patient_paths(patient_id)
        if not patient_paths.root.exists():
            raise PatientNotFoundError(f"Patient '{patient_id}' does not exist")
        if not content.strip():
            raise ValueError("medical consultation content is required")
        if consultation_number < 1:
            raise ValueError("consultation_number must be greater than zero")

        paths = self.build_consultation_paths(patient_id, consultation_date)
        if not paths.raw_file.exists():
            raise ConsultationNotFoundError(f"Raw consultation does not exist: {paths.raw_file}")
        if paths.medical_file.exists():
            raise ConsultationAlreadyExistsError(f"Medical consultation already exists: {paths.medical_file}")

        document = self._render_medical_consultation(
            patient_id=patient_id,
            medico_id=medico_id,
            consultation_date=consultation_date,
            consultation_number=consultation_number,
            input_type=input_type,
            source_agent=source_agent,
            content=content.strip(),
        )
        self._write_text(paths.medical_file, document)
        self._append_patient_index(
            patient_paths=patient_paths,
            consultation_number=consultation_number,
            consultation_date=consultation_date,
            input_type=input_type,
            raw_file=paths.raw_file,
            medical_file=paths.medical_file,
        )
        return paths.medical_file

    def read_raw_consultation_body(self, *, patient_id: str, consultation_date: date) -> str:
        paths = self.build_consultation_paths(patient_id, consultation_date)
        if not paths.raw_file.exists():
            raise ConsultationNotFoundError(f"Raw consultation does not exist: {paths.raw_file}")

        content = paths.raw_file.read_text(encoding="utf-8")
        return self._strip_frontmatter(content).strip()

    def read_doctor_template(self) -> str:
        template_file = self.workspace_paths().medico_dir / "plantilla.md"
        if not template_file.exists():
            self.bootstrap_workspace()
        return template_file.read_text(encoding="utf-8").strip()

    def list_medical_consultations(self, patient_id: str) -> list[MedicalConsultationDocument]:
        paths = self.patient_paths(patient_id)
        if not paths.root.exists():
            raise PatientNotFoundError(f"Patient '{patient_id}' does not exist")

        documents: list[MedicalConsultationDocument] = []
        for medical_file in sorted(paths.medical_dir.glob("*_consulta.md")):
            date_text = medical_file.name.removesuffix("_consulta.md")
            try:
                consultation_date = date.fromisoformat(date_text)
            except ValueError:
                continue
            body = self._strip_frontmatter(medical_file.read_text(encoding="utf-8")).strip()
            documents.append(
                MedicalConsultationDocument(
                    consultation_date=consultation_date,
                    file=medical_file,
                    body=body,
                )
            )
        return documents

    def append_patient_log(self, patient_id: str, entry: LogEntry) -> Path:
        paths = self.patient_paths(patient_id)
        if not paths.root.exists():
            raise PatientNotFoundError(f"Patient '{patient_id}' does not exist")

        rendered = self._render_log_entry(entry)
        with paths.log_file.open("a", encoding="utf-8") as handle:
            handle.write(rendered)
        return paths.log_file

    def _render_log_entry(self, entry: LogEntry) -> str:
        stamp = entry.timestamp.strftime("%Y-%m-%d %H:%M")
        return (
            f"## {stamp} — {entry.action}\n\n"
            f"- **Agente:** {entry.agent}\n"
            f"- **Qué:** {entry.action}\n"
            f"- **Dónde:** {entry.location}\n"
            f"- **Por qué:** {entry.reason}\n\n"
            "---\n\n"
        )

    def _render_raw_consultation(
        self,
        *,
        patient_id: str,
        medico_id: str,
        consultation_date: date,
        consultation_number: int,
        input_type: str,
        source_agent: str,
        content: str,
    ) -> str:
        return (
            "---\n"
            f"paciente_id: {patient_id}\n"
            f"medico_id: {medico_id}\n"
            f"fecha_consulta: {consultation_date.isoformat()}\n"
            f"numero_consulta: {consultation_number}\n"
            f"tipo_entrada: {input_type}\n"
            f"agente_origen: {source_agent}\n"
            "tipo_documento: crudo\n"
            "---\n\n"
            "# Formato Crudo\n\n"
            f"{content}\n"
        )

    def _render_medical_consultation(
        self,
        *,
        patient_id: str,
        medico_id: str,
        consultation_date: date,
        consultation_number: int,
        input_type: str,
        source_agent: str,
        content: str,
    ) -> str:
        return (
            "---\n"
            f"paciente_id: {patient_id}\n"
            f"medico_id: {medico_id}\n"
            f"fecha_consulta: {consultation_date.isoformat()}\n"
            f"numero_consulta: {consultation_number}\n"
            f"tipo_entrada: {input_type}\n"
            f"agente_origen: {source_agent}\n"
            "tipo_documento: medico\n"
            "---\n\n"
            f"{content}\n"
        )

    def _append_patient_index(
        self,
        *,
        patient_paths: PatientPaths,
        consultation_number: int,
        consultation_date: date,
        input_type: str,
        raw_file: Path,
        medical_file: Path,
    ) -> None:
        if "| # | Fecha | Entrada | Motivo | Archivos |" not in patient_paths.index_file.read_text(encoding="utf-8"):
            with patient_paths.index_file.open("a", encoding="utf-8") as handle:
                handle.write("| # | Fecha | Entrada | Motivo | Archivos |\n")
                handle.write("|---|-------|---------|--------|---------|\n")

        raw_link = raw_file.relative_to(patient_paths.root)
        medical_link = medical_file.relative_to(patient_paths.root)
        row = (
            f"| {consultation_number} | {consultation_date.isoformat()} | {input_type} |  | "
            f"[crudo]({raw_link}) · [médico]({medical_link}) |\n"
        )
        with patient_paths.index_file.open("a", encoding="utf-8") as handle:
            handle.write(row)

    def _strip_frontmatter(self, content: str) -> str:
        if not content.startswith("---\n"):
            return content
        marker = "\n---\n\n"
        _, separator, body = content.partition(marker)
        return body if separator else content

    def _write_if_missing(self, path: Path, content: str) -> None:
        if not path.exists():
            self._write_text(path, content)

    def _write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _markdown_file_count(self, path: Path) -> int:
        if not path.exists():
            return 0
        return sum(1 for child in path.iterdir() if child.is_file() and child.suffix == ".md")

    def _validate_patient_id(self, patient_id: str) -> None:
        if not patient_id or patient_id.strip() != patient_id:
            raise ValueError("patient_id must be a non-empty trimmed string")
        if any(separator in patient_id for separator in ("/", "\\")):
            raise ValueError("patient_id must not contain path separators")
