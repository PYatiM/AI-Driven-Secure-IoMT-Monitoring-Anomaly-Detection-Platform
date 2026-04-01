from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json


@dataclass
class ModelVersionRecord:
    model_name: str
    version: str
    artifact_path: str
    created_at: str
    parent_version: str | None = None
    training_data_path: str | None = None
    training_data_fingerprint: str | None = None
    metrics: dict[str, float | int | None] | None = None


def create_version_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def compute_file_fingerprint(path: str | Path) -> str:
    file_path = Path(path)
    digest = sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ModelRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[ModelVersionRecord]:
        if not self.path.exists():
            return []
        records = json.loads(self.path.read_text(encoding="utf-8"))
        return [ModelVersionRecord(**record) for record in records]

    def save(self, records: list[ModelVersionRecord]) -> None:
        payload = [asdict(record) for record in records]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def register(self, record: ModelVersionRecord) -> None:
        records = self.load()
        records.append(record)
        self.save(records)

    def get_latest(self, model_name: str) -> ModelVersionRecord | None:
        candidates = [record for record in self.load() if record.model_name == model_name]
        if not candidates:
            return None
        return max(candidates, key=lambda record: record.created_at)
