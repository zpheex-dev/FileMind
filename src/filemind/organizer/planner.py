"""Read-only organization proposals based on a completed, classified scan."""

import os
from datetime import datetime
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from filemind.organizer.rules import rule_matches, validate_destination, validate_folder, validate_rule
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
    for parent in destination.parents:
        if not parent.is_relative_to(root):
            break
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



def propose_organization(
    directory: Path, files: Iterable[ClassifiedFile],
    folder_names: dict[str, str] | None = None, rules=(), filenames=None,
) -> tuple[OrganizationProposal, ...]:
    """Suggest root/Organized/category/basename using existing rule-based classifications.

    A proposal is a snapshot, never permission to perform a move. Both disk
    occupancy and competing proposals are reported, with no filesystem writes.
    """
    directory = Path(os.path.abspath(directory))
    organized_root = directory / "Organized"
    home = Path.home()
    for rule in rules:
        validate_rule(rule)
    now = datetime.now()
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
        validate_destination(folder)
        reason = item.classification.explanation
        conflicts = []
        for rule in rules:
            if rule_matches(rule, item.metadata, source.parent.relative_to(directory).as_posix(), now):
                folder = rule["destination"]
                conditions = ", ".join(f"{key}={value}" for key, value in rule.items()
                                       if key not in ("name", "destination") and value)
                reason = f"Rule {rule['name']} · {conditions or 'all files'}"
                break
        if "<year>" in folder:
            modified = item.metadata.modified_at
            if modified is None:
                conflicts.append("Modification year unavailable")
            folder = folder.replace("<year>", str(modified.year) if modified else "unknown")
        name = (filenames or {}).get(source, source.name)
        if name != source.name:
            validate_folder(name)
        destination = organized_root / folder / name
        if source_key == _path_key(destination):
            continue
        candidates.append((source, destination, item, reason, conflicts))
    counts = Counter(_path_key(destination) for _, destination, *_ in candidates)
    folders_needed = {_path_key(parent) for _, dest, *_ in candidates for parent in dest.parents
                      if parent.is_relative_to(organized_root)}
    proposals = []
    for source, destination, item, reason, conflicts in candidates:
        conflicts.extend(_destination_conflicts(destination, organized_root))
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
        if _path_key(destination) in folders_needed or any(_path_key(parent) in counts for parent in destination.parents):
            conflicts.append("Another proposal needs this file path as a directory")
        if counts[_path_key(destination)] > 1:
            conflicts.append("Multiple files propose this destination")
        proposals.append(OrganizationProposal(source, destination, reason, tuple(conflicts)))
    return tuple(proposals)
