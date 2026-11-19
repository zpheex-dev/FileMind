"""Read-only organization proposals based on a completed, classified scan."""

import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from filemind.categorizer.classifier import ClassifiedFile
from filemind.organizer.filesystem import FILE_ERRORS, parent_handle, personal_parts, validate


@dataclass(frozen=True)
class OrganizationProposal:
    current_path: Path
    destination: Path
    reason: str
    conflicts: tuple[str, ...]

    @property
    def has_conflict(self) -> bool:
        return bool(self.conflicts)


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def _destination_conflicts(destination: Path, root: Path) -> list[str]:
    """Inspect destinations without creating or resolving directories."""
    conflicts = []
    try:
        destination.lstat()  # Also catches dangling symlinks.
    except (FileNotFoundError, NotADirectoryError):
        pass
    except OSError:
        conflicts.append("Destination cannot be checked")
    else:
        conflicts.append("Destination already exists")
    for parent in (root, destination.parent):
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            conflicts.append("Destination folder cannot be checked")
            break
        if parent.is_symlink() or not parent.is_dir():
            conflicts.append("Destination folder is not a regular directory")
            break
    return conflicts


def validate_folder(folder):
    if (not folder or folder.startswith(".") or folder.rstrip(" .") != folder
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', folder)
            or re.fullmatch(r"(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|(?:COM|LPT)[1-9¹²³])",
                            folder.split(".")[0].rstrip(" "), re.IGNORECASE)):
        raise ValueError("Use a visible folder name valid on both Windows and Linux.")


def propose_organization(
    directory: Path, files: Iterable[ClassifiedFile],
    folder_names: dict[str, str] | None = None,
) -> tuple[OrganizationProposal, ...]:
    """Suggest root/Organized/category/basename using existing rule-based classifications.

    A proposal is a snapshot, never permission to perform a move. Both disk
    occupancy and competing proposals are reported, with no filesystem writes.
    """
    directory = Path(os.path.abspath(directory))
    organized_root = directory / "Organized"
    home = Path.home()
    candidates = []
    seen = set()
    for item in files:
        source = Path(os.path.abspath(item.metadata.path))
        source_key = _path_key(source)
        if source_key in seen:
            continue
        seen.add(source_key)
        source.relative_to(directory)  # Reject inputs outside the scan root.
        category = item.classification.category
        if category in ("", ".", "..") or "/" in category or "\\" in category:
            raise ValueError("Category must be a single folder name")
        folder = (folder_names or {}).get(category, category)
        validate_folder(folder)
        destination = organized_root / folder / source.name
        if source_key == _path_key(destination):
            continue
        candidates.append((source, destination, item))
    counts = Counter(_path_key(destination) for _, destination, _ in candidates)
    proposals = []
    for source, destination, item in candidates:
        conflicts = _destination_conflicts(destination, organized_root)
        try:
            personal_parts(source, home)
            record = item.metadata
            expected = [*(record.identity or (None, None)), record.size_bytes, record.modified_at_ns]
            with parent_handle(source.parent, home) as parent:
                validate(parent, source.name, expected)
            ancestor = destination.parent
            while ancestor != directory and not ancestor.exists():
                ancestor = ancestor.parent
            with parent_handle(ancestor, home):
                if ancestor.stat().st_dev != expected[0]:
                    raise ValueError("Destination is on a different filesystem")
        except FILE_ERRORS as error:
            conflicts.append(str(error))
        if counts[_path_key(destination)] > 1:
            conflicts.append("Multiple files propose this destination")
        proposals.append(OrganizationProposal(source, destination, item.classification.explanation, tuple(conflicts)))
    return tuple(proposals)
