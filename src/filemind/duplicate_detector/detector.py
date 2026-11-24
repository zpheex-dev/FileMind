"""Local SHA-256 detection of exact duplicate files."""

import hashlib
import os
import stat
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, Iterable

from filemind.analyzer.metadata import FileMetadata


HASH_CHUNK_SIZE = 1024 * 1024
PROGRESS_BYTE_INTERVAL = 8 * 1024 * 1024


@dataclass(frozen=True)
class DuplicateGroup:
    sha256: str
    files: tuple[Path, ...]
    size_bytes: int
    redundant_bytes: int


@dataclass(frozen=True)
class DuplicateIssue:
    path: Path
    message: str


@dataclass(frozen=True)
class DuplicateProgress:
    files_processed: int
    total_files: int
    bytes_hashed: int
    total_bytes: int


@dataclass(frozen=True)
class DuplicateResult:
    groups: tuple[DuplicateGroup, ...]
    issues: tuple[DuplicateIssue, ...]
    files_hashed: int
    cancelled: bool


def find_duplicates(
    files: Iterable[FileMetadata],
    *,
    progress_callback: Callable[[DuplicateProgress], None] | None = None,
    cancellation_event: Event | None = None,
) -> DuplicateResult:
    """Hash only same-size candidates and return groups of identical content."""
    size_groups: dict[int, list[FileMetadata]] = defaultdict(list)
    issues: list[DuplicateIssue] = []
    seen_paths: set[str] = set()
    for metadata in files:
        if cancellation_event is not None and cancellation_event.is_set():
            return DuplicateResult((), tuple(issues), 0, True)
        key = os.path.normcase(str(metadata.path.absolute()))
        if key in seen_paths:
            continue
        seen_paths.add(key)
        if metadata.size_bytes is None:
            issues.append(
                DuplicateIssue(metadata.path, "File size is unavailable; skipped.")
            )
        else:
            size_groups[metadata.size_bytes].append(metadata)

    candidates = [
        metadata
        for same_size_files in size_groups.values()
        if len(same_size_files) > 1
        for metadata in same_size_files
    ]
    total_bytes = sum(metadata.size_bytes or 0 for metadata in candidates)
    hashes: dict[tuple[int, str], list[FileMetadata]] = defaultdict(list)
    identities: dict[Path, tuple[int, int]] = {}
    bytes_hashed = 0
    last_progress_bytes = 0
    files_hashed = 0

    for index, metadata in enumerate(candidates, start=1):
        if cancellation_event is not None and cancellation_event.is_set():
            return DuplicateResult((), tuple(issues), files_hashed, True)

        try:
            before = metadata.path.stat(follow_symlinks=False)
            if (
                before.st_size != metadata.size_bytes
                or (
                    metadata.modified_at_ns is not None
                    and before.st_mtime_ns != metadata.modified_at_ns
                )
                or not stat.S_ISREG(before.st_mode)
                or (metadata.identity is not None and (before.st_dev, before.st_ino) != metadata.identity)
            ):
                issues.append(
                    DuplicateIssue(
                        metadata.path,
                        "File changed or was replaced since scanning; skipped.",
                    )
                )
                continue

            digest = hashlib.sha256()
            file_bytes_read = 0
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            with os.fdopen(os.open(metadata.path, flags), "rb") as file:
                opened = os.fstat(file.fileno())
                if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(before, opened):
                    raise OSError("File changed before hashing; skipped.")
                while True:
                    if cancellation_event is not None and cancellation_event.is_set():
                        return DuplicateResult(
                            (),
                            tuple(issues),
                            files_hashed,
                            True,
                        )
                    chunk = file.read(HASH_CHUNK_SIZE)
                    if not chunk:
                        break
                    file_bytes_read += len(chunk)
                    if file_bytes_read > before.st_size:
                        raise OSError("File grew while hashing; skipped.")
                    digest.update(chunk)
                    bytes_hashed += len(chunk)
                    if (
                        progress_callback is not None
                        and bytes_hashed - last_progress_bytes
                        >= PROGRESS_BYTE_INTERVAL
                    ):
                        progress_callback(
                            DuplicateProgress(
                                index - 1,
                                len(candidates),
                                bytes_hashed,
                                total_bytes,
                            )
                        )
                        last_progress_bytes = bytes_hashed

            after = metadata.path.stat(follow_symlinks=False)
            if (
                before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
            ):
                issues.append(
                    DuplicateIssue(
                        metadata.path,
                        "File changed while hashing; skipped.",
                    )
                )
                continue
        except OSError as error:
            issues.append(DuplicateIssue(metadata.path, str(error)))
        else:
            size_bytes = metadata.size_bytes
            if size_bytes is not None:
                identities[metadata.path] = (after.st_dev, after.st_ino)
                hashes[(size_bytes, digest.hexdigest())].append(metadata)
                files_hashed += 1
        finally:
            if progress_callback is not None:
                progress_callback(
                    DuplicateProgress(
                        index,
                        len(candidates),
                        bytes_hashed,
                        total_bytes,
                    )
                )

    groups = []
    for (size_bytes, checksum), matching_files in hashes.items():
        if cancellation_event is not None and cancellation_event.is_set():
            return DuplicateResult((), tuple(issues), files_hashed, True)
        if len(matching_files) < 2:
            continue
        matching_files.sort(key=lambda item: item.path.as_posix().casefold())
        groups.append(
            DuplicateGroup(
                sha256=checksum,
                files=tuple(item.path for item in matching_files),
                size_bytes=size_bytes,
                redundant_bytes=size_bytes * (len({identities[item.path] for item in matching_files}) - 1),
            )
        )

    groups.sort(
        key=lambda group: (-group.redundant_bytes, group.sha256)
    )
    if cancellation_event is not None and cancellation_event.is_set():
        return DuplicateResult((), tuple(issues), files_hashed, True)
    return DuplicateResult(
        groups=tuple(groups),
        issues=tuple(issues),
        files_hashed=files_hashed,
        cancelled=False,
    )
