from __future__ import annotations

import os
from pathlib import Path
import stat

from .models import Gate3AuthorityError


def is_redirect(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except FileNotFoundError:
        return False


def assert_no_redirect_components(path: Path, *, code: str) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current = current / component
        try:
            redirected = is_redirect(current)
        except OSError as exc:
            raise Gate3AuthorityError(f"{code}: reparse status is unreadable") from exc
        if redirected:
            raise Gate3AuthorityError(f"{code}: filesystem redirect rejected")


def resolve_repository_root(repository: Path, *, code: str) -> Path:
    lexical = Path(os.path.abspath(Path(repository)))
    assert_no_redirect_components(lexical, code=code)
    try:
        root = lexical.resolve(strict=True)
    except OSError as exc:
        raise Gate3AuthorityError(f"{code}: repository root is unavailable") from exc
    if not root.is_dir():
        raise Gate3AuthorityError(f"{code}: repository root is not a directory")
    return root


def contained_path(root: Path, relative_parts: tuple[str, ...], *, code: str) -> Path:
    lexical = root.joinpath(*relative_parts)
    assert_no_redirect_components(lexical, code=code)
    existing = lexical
    while not existing.exists() and existing != root:
        existing = existing.parent
    try:
        existing.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as exc:
        raise Gate3AuthorityError(f"{code}: path escaped repository") from exc
    return lexical
