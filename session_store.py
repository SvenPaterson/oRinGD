import base64
import datetime as dt
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from rating import Crack

## Major version change indicates breaking changes, Major.Minor.Patch
APP_VERSION = "1.0.2" # new PRs require minor version bump
SESSION_SCHEMA_VERSION = 1 ## Increment this version number when the session file format changes, it will break .orngd compatibility
SESSION_JSON_FILENAME = "session.json"


class SessionFileError(Exception):
    """Raised when a session file cannot be read or written."""


class SessionVersionError(SessionFileError):
    """Raised when the session file version is incompatible with this build."""


@dataclass
class SessionAnalysis:
    index: int
    image_name: str
    image_path: str
    completed_at: dt.datetime
    crack_count: int
    total_pct: float
    rating: int
    result: str
    cracks: List[Crack]
    snapshot_png: Optional[bytes] = None


@dataclass
class SessionMetadata:
    rdms_project_number: str
    project_name: str
    technician_name: str
    project_code: str
    created_at: dt.datetime
    updated_at: dt.datetime
    schema_version: int = SESSION_SCHEMA_VERSION
    app_version: str = APP_VERSION

    @property
    def banner_text(self) -> str:
        return (
            f"{self.project_code} | RDMS {self.rdms_project_number} | "
            f"Technician: {self.technician_name}"
        )


@dataclass
class SessionState:
    metadata: SessionMetadata
    records: List[SessionAnalysis]
    file_path: str


def _now() -> dt.datetime:
    return dt.datetime.now()


def _iso(dt_value: dt.datetime) -> str:
    return dt_value.isoformat(timespec="seconds")


def _parse_iso(value: Optional[str]) -> dt.datetime:
    if not value:
        return _now()
    return dt.datetime.fromisoformat(value)


def _slugify_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", name.strip())
    return cleaned.strip("-") or "PROJECT"


def generate_project_code(rdms_number: str, project_name: str, when: Optional[dt.datetime] = None) -> str:
    when = when or _now()
    slug = _slugify_name(project_name)
    return f"RT-{rdms_number}_{slug}_{when.strftime('%Y%m%d')}"


def create_session_metadata(rdms_number: str, project_name: str, technician_name: str) -> SessionMetadata:
    created = _now()
    project_code = generate_project_code(rdms_number, project_name, created)
    return SessionMetadata(
        rdms_project_number=rdms_number,
        project_name=project_name.strip(),
        technician_name=technician_name.strip(),
        project_code=project_code,
        created_at=created,
        updated_at=created,
    )


def _cracks_to_json(cracks: Sequence[Crack]) -> List[Tuple[str, float]]:
    return [(ctype, float(length)) for ctype, length in cracks]


def _cracks_from_json(data: Sequence[Sequence]) -> List[Crack]:
    cracks: List[Crack] = []
    for entry in data:
        if len(entry) != 2:
            continue
        cracks.append((str(entry[0]), float(entry[1])))
    return cracks


def _record_to_dict(record: SessionAnalysis) -> dict:
    payload = {
        "index": record.index,
        "image_name": record.image_name,
        "image_path": record.image_path,
        "completed_at": _iso(record.completed_at),
        "crack_count": record.crack_count,
        "total_pct": record.total_pct,
        "rating": record.rating,
        "result": record.result,
        "cracks": _cracks_to_json(record.cracks),
        "snapshot_png": None,
    }
    if record.snapshot_png:
        payload["snapshot_png"] = base64.b64encode(record.snapshot_png).decode("ascii")
    return payload


def _record_from_dict(data: dict) -> SessionAnalysis:
    snapshot = data.get("snapshot_png")
    return SessionAnalysis(
        index=int(data.get("index", 0)),
        image_name=str(data.get("image_name", "")),
        image_path=str(data.get("image_path", "")),
        completed_at=_parse_iso(data.get("completed_at")),
        crack_count=int(data.get("crack_count", 0)),
        total_pct=float(data.get("total_pct", 0.0)),
        rating=int(data.get("rating", 0)),
        result=str(data.get("result", "")),
        cracks=_cracks_from_json(data.get("cracks", [])),
        snapshot_png=base64.b64decode(snapshot) if snapshot else None,
    )


def _metadata_to_dict(metadata: SessionMetadata) -> dict:
    return {
        "rdms_project_number": metadata.rdms_project_number,
        "project_name": metadata.project_name,
        "technician_name": metadata.technician_name,
        "project_code": metadata.project_code,
        "created_at": _iso(metadata.created_at),
        "updated_at": _iso(metadata.updated_at),
        "schema_version": metadata.schema_version,
        "app_version": metadata.app_version,
    }


def _metadata_from_dict(data: dict) -> SessionMetadata:
    return SessionMetadata(
        rdms_project_number=str(data.get("rdms_project_number", "")),
        project_name=str(data.get("project_name", "")),
        technician_name=str(data.get("technician_name", "")),
        project_code=str(data.get("project_code", "")),
        created_at=_parse_iso(data.get("created_at")),
        updated_at=_parse_iso(data.get("updated_at")),
        schema_version=int(data.get("schema_version", SESSION_SCHEMA_VERSION)),
        app_version=str(data.get("app_version", APP_VERSION)),
    )


def _ensure_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _parse_version(value: str) -> Tuple[int, int, int]:
    try:
        parts = [int(part) for part in value.split(".")[:3]]
    except ValueError as exc:
        raise SessionVersionError(f"Invalid version string: {value}") from exc
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)  # type: ignore[return-value]


def save_session_file(path: str, metadata: SessionMetadata, records: List[SessionAnalysis]) -> None:
    output_path = _ensure_path(path)
    metadata.updated_at = _now()
    payload = {
        "schema_version": SESSION_SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "metadata": _metadata_to_dict(metadata),
        "analyses": [_record_to_dict(record) for record in records],
    }
    try:
        with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(SESSION_JSON_FILENAME, json.dumps(payload, indent=2).encode("utf-8"))
    except OSError as exc:
        raise SessionFileError(f"Failed to write session file: {exc}") from exc


def load_session_file(path: str) -> SessionState:
    input_path = _ensure_path(path)
    try:
        with zipfile.ZipFile(input_path, mode="r") as zf:
            with zf.open(SESSION_JSON_FILENAME) as fp:
                payload = json.load(fp)
    except FileNotFoundError as exc:
        raise SessionFileError(f"Session file not found: {path}") from exc
    except KeyError as exc:
        raise SessionFileError("Session archive missing session.json") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionFileError(f"Failed to read session file: {exc}") from exc

    schema_version = int(payload.get("schema_version", 0))
    if schema_version > SESSION_SCHEMA_VERSION:
        raise SessionVersionError(
            f"Session file schema {schema_version} is newer than supported {SESSION_SCHEMA_VERSION}."
        )

    file_version = str(payload.get("app_version", APP_VERSION))
    file_major, _, _ = _parse_version(file_version)
    current_major, _, _ = _parse_version(APP_VERSION)
    if file_major > current_major:
        raise SessionVersionError(
            "Session file was created with a newer major version of oRinGD. Please update the app."
        )

    metadata = _metadata_from_dict(payload.get("metadata", {}))
    analyses = [_record_from_dict(item) for item in payload.get("analyses", [])]
    for idx, record in enumerate(analyses, start=1):
        record.index = idx

    return SessionState(metadata=metadata, records=analyses, file_path=str(input_path))
