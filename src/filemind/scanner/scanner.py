"""Read-only recursive directory scanning."""

import os
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable


@dataclass(frozen=True)
class ScanProgress:
    directories_scanned: int
    files_found: int


@dataclass(frozen=True)
class ScanIssue:
    path: Path
    message: str


@dataclass(frozen=True)
class ScanResult:
    directory: Path
    files: tuple[Path, ...]
    issues: tuple[ScanIssue, ...]
    directories_scanned: int
    cancelled: bool


def scan_directory(
    directory_path: str | Path,
    *,
    progress_callback: Callable[[ScanProgress], None] | None = None,
    cancellation_event: Event | None = None,
) -> ScanResult:
    """Recursively list regular files without changing the filesystem.

    Symlinks are not followed. Errors encountered below the selected root are
    returned in ``issues`` so accessible parts of the tree can still be scanned.
    """
    directory = Path(directory_path)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    pending_directories = [directory]
    files: list[Path] = []
    issues: list[ScanIssue] = []
    directories_scanned = 0
    cancelled = False

    while pending_directories:
        if cancellation_event is not None and cancellation_event.is_set():
            cancelled = True
            break

        current_directory = pending_directories.pop()
        directories_scanned += 1
        try:
            with os.scandir(current_directory) as entries:
                for entry in entries:
                    if cancellation_event is not None and cancellation_event.is_set():
                        cancelled = True
                        break

                    entry_path = Path(entry.path)
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            pending_directories.append(entry_path)
                        elif entry.is_file(follow_symlinks=False):
                            files.append(entry_path)
                            if (
                                progress_callback is not None
                                and len(files) % 25 == 0
                            ):
                                progress_callback(
                                    ScanProgress(directories_scanned, len(files))
                                )
                    except OSError as error:
                        issues.append(ScanIssue(entry_path, str(error)))
        except OSError as error:
            issues.append(ScanIssue(current_directory, str(error)))

        if progress_callback is not None:
            progress_callback(ScanProgress(directories_scanned, len(files)))
        if cancelled:
            break

    files.sort(key=lambda path: path.as_posix().casefold())
    return ScanResult(
        directory=directory,
        files=tuple(files),
        issues=tuple(issues),
        directories_scanned=directories_scanned,
        cancelled=cancelled,
    )
