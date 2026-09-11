from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def tag_scalar(value: object) -> dict[str, object]:
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, float):
        if math.isnan(value):
            encoded = "nan"
        elif math.isinf(value):
            encoded = "inf" if value > 0 else "-inf"
        else:
            encoded = format(value, ".17g")
        return {"type": "float", "value": encoded}
    if isinstance(value, Decimal):
        return {"type": "decimal", "value": str(value)}
    if isinstance(value, bytes):
        return {"type": "bytes", "value": value.hex()}
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, str):
        return {"type": "str", "value": value}
    return {"type": type(value).__name__, "value": str(value)}


def _json_ready(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _json_ready(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        _json_ready(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()

