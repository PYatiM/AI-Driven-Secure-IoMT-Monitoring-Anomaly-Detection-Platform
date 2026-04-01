from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any


class PredictionLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _serialize(self, value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if is_dataclass(value):
            return {key: self._serialize(item) for key, item in asdict(value).items()}
        if isinstance(value, dict):
            return {str(key): self._serialize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._serialize(item) for item in value]
        return value

    def log(self, input_record: dict, prediction_result: Any) -> None:
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "input": self._serialize(input_record),
            "prediction": self._serialize(prediction_result),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
