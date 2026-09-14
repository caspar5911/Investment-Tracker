"""Test-only instrumentation for Gate 2 filesystem-boundary assertions."""

from __future__ import annotations

import builtins
import io
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest


class Gate2FilesystemBoundaryGuard:
    """Reject reads and discovery outside the exact Gate 2 test allowlist."""

    def __init__(
        self,
        *,
        root: Path,
        source_paths: Iterable[Path],
        authority_paths: Iterable[Path],
        generated_root: Path,
        source_discovery_roots: Iterable[Path],
    ) -> None:
        self.root = root.resolve()
        self.allowed_reads = {
            path.resolve() for path in (*source_paths, *authority_paths)
        }
        self.generated_root = generated_root.resolve()
        self.source_discovery_roots = {
            path.resolve() for path in source_discovery_roots
        }
        self.read_paths: list[Path] = []
        self.discovery_paths: list[tuple[str, Path]] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        original_path_open = Path.open
        original_read_bytes = Path.read_bytes
        original_read_text = Path.read_text
        original_builtin_open = builtins.open
        original_io_open = io.open
        original_os_open = os.open
        original_iterdir = Path.iterdir
        original_glob = Path.glob
        original_rglob = Path.rglob
        original_scandir = os.scandir
        original_listdir = os.listdir

        def observe_path_open(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
            if _read_mode(mode):
                self._read(path)
            return original_path_open(path, mode, *args, **kwargs)

        def observe_read_bytes(path: Path, *args: Any, **kwargs: Any) -> bytes:
            self._read(path)
            return original_read_bytes(path, *args, **kwargs)

        def observe_read_text(path: Path, *args: Any, **kwargs: Any) -> str:
            self._read(path)
            return original_read_text(path, *args, **kwargs)

        def observe_builtin_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
            if _read_mode(mode):
                self._read_file_argument(file)
            return original_builtin_open(file, mode, *args, **kwargs)

        def observe_io_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
            if _read_mode(mode):
                self._read_file_argument(file)
            return original_io_open(file, mode, *args, **kwargs)

        def observe_os_open(file: Any, flags: int, *args: Any, **kwargs: Any) -> int:
            if (flags & 3) in (os.O_RDONLY, os.O_RDWR):
                self._read_file_argument(file)
            return original_os_open(file, flags, *args, **kwargs)

        def observe_iterdir(path: Path) -> Any:
            self._discovery("iterdir", path)
            return original_iterdir(path)

        def observe_glob(
            path: Path, pattern: str, *args: Any, **kwargs: Any
        ) -> Any:
            self._discovery(f"glob:{pattern}", path)
            return original_glob(path, pattern, *args, **kwargs)

        def observe_rglob(
            path: Path, pattern: str, *args: Any, **kwargs: Any
        ) -> Any:
            self._discovery(f"rglob:{pattern}", path)
            return original_rglob(path, pattern, *args, **kwargs)

        def observe_scandir(path: Any = ".") -> Any:
            self._discovery("scandir", path)
            return original_scandir(path)

        def observe_listdir(path: Any = ".") -> Any:
            self._discovery("listdir", path)
            return original_listdir(path)

        monkeypatch.setattr(Path, "open", observe_path_open)
        monkeypatch.setattr(Path, "read_bytes", observe_read_bytes)
        monkeypatch.setattr(Path, "read_text", observe_read_text)
        monkeypatch.setattr(builtins, "open", observe_builtin_open)
        monkeypatch.setattr(io, "open", observe_io_open)
        monkeypatch.setattr(os, "open", observe_os_open)
        monkeypatch.setattr(Path, "iterdir", observe_iterdir)
        monkeypatch.setattr(Path, "glob", observe_glob)
        monkeypatch.setattr(Path, "rglob", observe_rglob)
        monkeypatch.setattr(os, "scandir", observe_scandir)
        monkeypatch.setattr(os, "listdir", observe_listdir)

    def _read_file_argument(self, value: Any) -> None:
        if isinstance(value, int):
            return
        self._read(Path(value))

    def _read(self, path: Path) -> None:
        resolved = path.resolve()
        self.read_paths.append(resolved)
        if resolved in self.allowed_reads or _within(resolved, self.generated_root):
            return
        raise AssertionError(f"forbidden filesystem read: {resolved}")

    def _discovery(self, operation: str, value: Any) -> None:
        if isinstance(value, int):
            return
        path = Path(value).resolve()
        self.discovery_paths.append((operation, path))
        allowed = path in self.source_discovery_roots and operation in {
            "glob:*.py",
            "scandir",
            "listdir",
        }
        normalized_operation = operation.replace("\\", "/")
        if _within(path, self.generated_root) and normalized_operation in {
            "iterdir",
            "rglob:*",
            "glob:**/*",
            "scandir",
            "listdir",
        }:
            allowed = True
        if not allowed:
            raise AssertionError(f"forbidden filesystem discovery: {operation} {path}")


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _read_mode(mode: str) -> bool:
    return "r" in mode or "+" in mode
