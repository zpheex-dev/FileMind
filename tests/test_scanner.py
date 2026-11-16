import os
from pathlib import Path
from threading import Event

import pytest

from filemind.scanner.scanner import ScanProgress, scan_directory


def test_scan_directory_recursively_lists_files(tmp_path: Path) -> None:
    first_file = tmp_path / "notes.txt"
    nested_directory = tmp_path / "folder" / "nested"
    nested_directory.mkdir(parents=True)
    nested_file = nested_directory / "image.png"
    first_file.write_text("notes", encoding="utf-8")
    nested_file.write_bytes(b"image")

    result = scan_directory(tmp_path)

    assert set(result.files) == {first_file, nested_file}
    assert result.directories_scanned == 3
    assert not result.issues
    assert not result.cancelled
    assert first_file.read_text(encoding="utf-8") == "notes"


def test_scan_directory_reports_progress(tmp_path: Path) -> None:
    (tmp_path / "one.txt").write_text("one", encoding="utf-8")
    (tmp_path / "two.txt").write_text("two", encoding="utf-8")
    progress: list[ScanProgress] = []

    result = scan_directory(tmp_path, progress_callback=progress.append)

    assert progress
    assert progress[-1].files_found == len(result.files) == 2
    assert progress[-1].directories_scanned == 1


def test_scan_directory_returns_partial_results_on_access_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    readable_file = tmp_path / "readable.txt"
    blocked_directory = tmp_path / "blocked"
    readable_file.write_text("readable", encoding="utf-8")
    blocked_directory.mkdir()
    real_scandir = os.scandir

    def scan_with_blocked_directory(path: str | Path):
        if Path(path) == blocked_directory:
            raise PermissionError("access denied")
        return real_scandir(path)

    monkeypatch.setattr(
        "filemind.scanner.scanner.os.scandir",
        scan_with_blocked_directory,
    )

    result = scan_directory(tmp_path)

    assert readable_file in result.files
    assert len(result.issues) == 1
    assert result.issues[0].path == blocked_directory
    assert "access denied" in result.issues[0].message


def test_scan_directory_can_be_cancelled(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")
    cancellation_event = Event()
    cancellation_event.set()

    result = scan_directory(tmp_path, cancellation_event=cancellation_event)

    assert result.cancelled
    assert not result.files


def test_scan_directory_raises_for_missing_directory(tmp_path: Path) -> None:
    missing_directory = tmp_path / "missing"

    with pytest.raises(FileNotFoundError):
        scan_directory(missing_directory)


def test_scan_directory_raises_for_file_path(tmp_path: Path) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text("notes", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        scan_directory(file_path)
