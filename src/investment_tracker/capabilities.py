from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


class CanonicalWriteDenied(PermissionError):
    pass


@dataclass(frozen=True)
class CanonicalWriterCapability:
    role: Literal["COORDINATOR"]


def canonical_writer_capability(role: str) -> CanonicalWriterCapability:
    if role.strip().upper() != "COORDINATOR":
        raise CanonicalWriteDenied("workers cannot obtain canonical write capability")
    return CanonicalWriterCapability(role="COORDINATOR")
