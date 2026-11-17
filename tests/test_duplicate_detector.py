import hashlib
from pathlib import Path
from types import SimpleNamespace
from threading import Event

from filemind.analyzer.metadata import analyze_file
from filemind.duplicate_detector.detector import find_duplicates


def test_repeated_path_is_not_a_duplicate_of_itself(tmp_path):
    path = tmp_path / "one.txt"
    path.write_text("content")
    metadata = analyze_file(path)
    result = find_duplicates([metadata, metadata])
    assert not result.groups
    assert result.files_hashed == 0


def test_finds_exact_duplicates_and_skips_singletons(tmp_path: Path) -> None:
    content = b"same content"
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    same_size_different_content = tmp_path / "different.txt"
    singleton = tmp_path / "single.bin"
    first.write_bytes(content)
    second.write_bytes(content)
    same_size_different_content.write_bytes(b"diff content")
    singleton.write_bytes(b"x")
    metadata = [
        analyze_file(path)
        for path in (first, second, same_size_different_content, singleton)
    ]
    progress = []

    result = find_duplicates(metadata, progress_callback=progress.append)

    assert len(result.groups) == 1
    group = result.groups[0]
    assert set(group.files) == {first, second}
    assert group.sha256 == hashlib.sha256(content).hexdigest()
    assert group.size_bytes == len(content)
    assert group.redundant_bytes == len(content)
    assert result.files_hashed == 3
    assert progress[-1].files_processed == 3
    assert progress[-1].bytes_hashed == len(content) * 3
    assert not result.issues
    assert first.read_bytes() == second.read_bytes() == content


def test_empty_files_are_exact_duplicates(tmp_path: Path) -> None:
    first = tmp_path / "empty-one.txt"
    second = tmp_path / "empty-two.txt"
    first.touch()
    second.touch()

    result = find_duplicates([analyze_file(first), analyze_file(second)])

    assert len(result.groups) == 1
    assert result.groups[0].size_bytes == 0
    assert result.groups[0].redundant_bytes == 0


def test_changed_or_missing_files_are_reported_and_not_grouped(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.txt"
    available = tmp_path / "available.txt"
    missing.write_text("same", encoding="utf-8")
    available.write_text("same", encoding="utf-8")
    metadata = [analyze_file(missing), analyze_file(available)]
    missing.unlink()

    progress = []
    result = find_duplicates(metadata, progress_callback=progress.append)

    assert not result.groups
    assert len(result.issues) == 1
    assert result.issues[0].path == missing
    assert result.files_hashed == 1
    assert progress[-1].files_processed == 2


def test_hash_collision_does_not_merge_different_file_sizes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class ConstantDigest:
        def update(self, content: bytes) -> None:
            pass

        def hexdigest(self) -> str:
            return "0" * 64

    files = []
    for name, content in (
        ("small-one.bin", b"four"),
        ("small-two.bin", b"size"),
        ("large-one.bin", b"eight---"),
        ("large-two.bin", b"content!"),
    ):
        path = tmp_path / name
        path.write_bytes(content)
        files.append(analyze_file(path))
    monkeypatch.setattr(
        "filemind.duplicate_detector.detector.hashlib.sha256",
        ConstantDigest,
    )

    result = find_duplicates(files)

    assert sorted(group.size_bytes for group in result.groups) == [4, 8]
    assert all(len(group.files) == 2 for group in result.groups)


def test_file_changed_while_hashing_is_excluded(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("same", encoding="utf-8")
    second.write_text("same", encoding="utf-8")
    metadata = [analyze_file(first), analyze_file(second)]
    original_stat = Path.stat
    stat_calls = 0

    def report_changed_stat(path: Path, *args, **kwargs):
        nonlocal stat_calls
        result = original_stat(path, *args, **kwargs)
        if path == first:
            stat_calls += 1
            if stat_calls == 2:
                return SimpleNamespace(
                    st_size=result.st_size,
                    st_mtime_ns=result.st_mtime_ns + 1,
                )
        return result

    monkeypatch.setattr(Path, "stat", report_changed_stat)

    result = find_duplicates(metadata)

    assert not result.groups
    assert result.files_hashed == 1
    assert len(result.issues) == 1
    assert result.issues[0].path == first


def test_file_changed_since_scan_is_excluded(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("same", encoding="utf-8")
    second.write_text("same", encoding="utf-8")
    metadata = [analyze_file(first), analyze_file(second)]
    original_stat = Path.stat

    def report_modified_since_scan(path: Path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if path == first:
            return SimpleNamespace(
                st_size=result.st_size,
                st_mtime_ns=result.st_mtime_ns + 1,
            )
        return result

    monkeypatch.setattr(Path, "stat", report_modified_since_scan)

    result = find_duplicates(metadata)

    assert not result.groups
    assert result.files_hashed == 1
    assert len(result.issues) == 1
    assert result.issues[0].path == first


def test_duplicate_check_can_be_cancelled_before_hashing(
    tmp_path: Path,
) -> None:
    first = tmp_path / "one.txt"
    second = tmp_path / "two.txt"
    first.write_text("same", encoding="utf-8")
    second.write_text("same", encoding="utf-8")
    cancellation_event = Event()
    cancellation_event.set()

    result = find_duplicates(
        [analyze_file(first), analyze_file(second)],
        cancellation_event=cancellation_event,
    )

    assert result.cancelled
    assert not result.groups
    assert result.files_hashed == 0
