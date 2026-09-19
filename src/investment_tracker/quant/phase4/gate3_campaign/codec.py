"""Strict wire decoding for existing frozen models, including UTC timestamps."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
import json
import math
import types
from typing import Annotated, Literal, Union, get_args, get_origin

import pandas as pd
from pydantic import BaseModel

from investment_tracker.quant.phase4.preregistration.canonical import canonical_json_bytes


def wire(value):
    if isinstance(value, BaseModel):
        return {name: wire(getattr(value, name)) for name in type(value).model_fields}
    if is_dataclass(value):
        return wire(asdict(value))
    if isinstance(value, pd.Timestamp):
        if value.tz is None or str(value.tz) != 'UTC':
            raise ValueError('NONCANONICAL_TIMESTAMP')
        return value.isoformat()
    if isinstance(value, dict):
        converted = {}
        for key, item in value.items():
            if isinstance(key, str):
                encoded = key
            elif isinstance(key, int) and not isinstance(key, bool):
                encoded = str(key)
            else:
                raise ValueError('NONCANONICAL_MAPPING_KEY')
            converted[encoded] = wire(item)
        return converted
    if isinstance(value, (tuple, list)):
        return [wire(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('NONFINITE_EVIDENCE')
    return value


def canonical_bytes(value) -> bytes:
    return canonical_json_bytes(wire(value))


def digest(value) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def hydrate(annotation, value):
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Annotated:
        return hydrate(args[0], value)
    if origin in (Union, types.UnionType):
        for option in args:
            try:
                return hydrate(option, value)
            except (TypeError, ValueError):
                pass
        raise ValueError('STRICT_UNION_INVALID')
    if origin is Literal:
        if not any(type(value) is type(expected) and value == expected for expected in args):
            raise ValueError('STRICT_LITERAL_INVALID')
        return value
    if origin is tuple:
        if not isinstance(value, (tuple, list)):
            raise ValueError('STRICT_TUPLE_INVALID')
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(hydrate(args[0], item) for item in value)
        if len(value) != len(args):
            raise ValueError('STRICT_TUPLE_LENGTH')
        return tuple(hydrate(kind, item) for kind, item in zip(args, value, strict=True))
    if origin is dict:
        if not isinstance(value, dict):
            raise ValueError('STRICT_DICT_INVALID')
        result = {}
        for key, item in value.items():
            if args[0] is int and isinstance(key, str):
                try:
                    decoded_key = int(key)
                except ValueError as exc:
                    raise ValueError('STRICT_DICT_KEY_INVALID') from exc
                if str(decoded_key) != key:
                    raise ValueError('STRICT_DICT_KEY_INVALID')
            else:
                decoded_key = hydrate(args[0], key)
            result[decoded_key] = hydrate(args[1], item)
        return result
    if annotation is pd.Timestamp:
        if isinstance(value, pd.Timestamp):
            return value
        if not isinstance(value, str):
            raise ValueError('STRICT_TIMESTAMP_INVALID')
        timestamp = pd.Timestamp(value)
        if timestamp.isoformat() != value or timestamp.tz is None or str(timestamp.tz) != 'UTC':
            raise ValueError('NONCANONICAL_TIMESTAMP')
        return timestamp
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if isinstance(value, BaseModel):
            value = {name: getattr(value, name) for name in type(value).model_fields}
        if not isinstance(value, dict) or set(value) - set(annotation.model_fields):
            raise ValueError('EXTRA_OR_UNTYPED_EVIDENCE')
        converted = {name: hydrate(annotation.model_fields[name].annotation, item) for name, item in value.items()}
        return annotation.model_validate(converted, strict=True)
    if annotation in (str, int, float, bool, type(None)):
        if type(value) is not annotation:
            raise ValueError('STRICT_SCALAR_INVALID')
        if annotation is float and not math.isfinite(value):
            raise ValueError('NONFINITE_EVIDENCE')
        return value
    raise TypeError(f'UNSUPPORTED_WIRE_TYPE: {annotation}')


def decode(model, payload: bytes):
    parsed = json.loads(payload)
    return hydrate(model, parsed)
