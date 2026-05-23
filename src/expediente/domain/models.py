from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    medico_dir: Path
    patients_dir: Path
    global_index_file: Path
    agents_file: Path


@dataclass(frozen=True)
class PatientPaths:
    patient_id: str
    root: Path
    index_file: Path
    log_file: Path
    raw_dir: Path
    medical_dir: Path


@dataclass(frozen=True)
class PatientSummary:
    patient_id: str
    raw_consultation_count: int
    medical_consultation_count: int
    index_file: Path
    log_file: Path


@dataclass(frozen=True)
class ConsultationPaths:
    raw_file: Path
    medical_file: Path
    filename: str


@dataclass(frozen=True)
class MedicalConsultationDocument:
    consultation_date: date
    file: Path
    body: str


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime
    agent: str
    action: str
    location: str
    reason: str


@dataclass(frozen=True)
class ConsultationKey:
    patient_id: str
    consultation_date: date
