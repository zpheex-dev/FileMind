import os
from pathlib import Path
import tempfile

import pytest

from filemind.analyzer.metadata import analyze_file
from filemind.organizer import transfers
from filemind.organizer.organizer import MoveJournal
from test_moves import user_file


@pytest.fixture
def route(tmp_path):
    source = tmp_path / "source"
    user_file(source, "payload")
    dest = tmp_path / "target" / "copy"
    dest.parent.mkdir()
    return MoveJournal(tmp_path / "journal"), source, dest


@pytest.mark.parametrize("kind", ["copy", "move"])
def test_verified_roundtrip(route, kind):
    journal, source, dest = route
    journal.transfer(source, dest, analyze_file(source), kind)
    row, = journal.history()
    assert row["status"] == ("copied" if kind == "copy" else "moved"), row["reason"]
    assert dest.read_bytes() == b"payload" and source.exists() == (kind == "copy")
    journal.undo([row["id"]])
    assert journal.history()[0]["status"] == "undone"
    assert source.read_bytes() == b"payload" and not dest.exists()


@pytest.mark.parametrize("kind", ["copy", "move"])
def test_interruption_after_publication_preserves_source_and_allows_undo(route, kind, monkeypatch):
    journal, source, dest = route
    publish = transfers.publish
    class Crash(BaseException):
        pass
    def interrupt(*args):
        publish(*args)
        raise Crash()
    with monkeypatch.context() as patch:
        patch.setattr(transfers, "publish", interrupt)
        with pytest.raises(Crash):
            journal.transfer(source, dest, analyze_file(source), kind)
    reopened = MoveJournal(journal.database)
    reopened.reconcile()
    row, = reopened.history()
    assert row["status"] == "copied" and source.read_bytes() == dest.read_bytes()
    reopened.undo([row["id"]])
    assert source.read_bytes() == b"payload" and not dest.exists()


def test_missing_drive_and_undo_of_sole_copy(route):
    journal, src, dest = route
    journal.transfer(src, dest, analyze_file(src), "copy")
    row, = journal.history()
    src.unlink()
    journal.undo([row["id"]])
    assert dest.read_bytes() == b"payload" and journal.history()[0]["status"] == "copied"
    with pytest.raises(FileNotFoundError):
        journal.transfer(src, dest, analyze_file(src), "move")


def test_transfer_conflict_never_overwrites(route):
    journal, src, dest = route
    dest.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        journal.transfer(src, dest, analyze_file(src), "move")
    assert src.read_bytes() == b"payload" and dest.read_bytes() == b"existing"


@pytest.mark.parametrize("kind", ["copy", "move"])
def test_interrupted_undo_reconciles_after_removal(route, kind, monkeypatch):
    journal, src, dest = route
    journal.transfer(src, dest, analyze_file(src), kind)
    row, = journal.history()
    finish = transfers.outcome
    def interrupt(db, entry, state, reason=""):
        if state == "undone":
            raise KeyboardInterrupt()
        finish(db, entry, state, reason)
    with monkeypatch.context() as patch:
        patch.setattr(transfers, "outcome", interrupt)
        with pytest.raises(KeyboardInterrupt):
            journal.undo([row["id"]])
    journal.reconcile()
    assert journal.history()[0]["status"] == "undone"
    assert src.read_bytes() == b"payload" and not dest.exists()


def test_two_volumes_when_available(tmp_path):
    other = os.environ.get("FILEMIND_TEST_SECOND_VOLUME")
    if not other:
        pytest.skip("Set FILEMIND_TEST_SECOND_VOLUME to a writable directory on a second volume")
    with tempfile.TemporaryDirectory(dir=Path(other).resolve()) as directory:
        assert Path(directory).stat().st_dev != tmp_path.stat().st_dev
        source = tmp_path / "source"
        target = Path(directory) / "target"
        journal = MoveJournal(tmp_path / "db")
        for kind in ("copy", "move"):
            user_file(source, "payload")
            journal.transfer(source, target, analyze_file(source), kind)
            assert target.read_bytes() == b"payload"
            journal.undo([journal.history()[0]["id"]])
            assert not target.exists() and source.read_bytes() == b"payload"


def test_disconnected_volume_recovery_waits_for_same_directory(route, monkeypatch):
    journal, src, dest = route
    publish = transfers.publish
    def crash(*args):
        publish(*args)
        raise SystemExit()
    with monkeypatch.context() as patch:
        patch.setattr(transfers, "publish", crash)
        with pytest.raises(SystemExit):
            journal.transfer(src, dest, analyze_file(src), "move")
    offline = dest.parent.with_name("offline")
    dest.parent.rename(offline)
    dest.parent.mkdir()
    journal.reconcile()
    assert journal.history()[0]["status"] == "transfer pending" and src.read_bytes() == b"payload"
    dest.parent.rmdir()
    offline.rename(dest.parent)
    journal.reconcile()
    assert journal.history()[0]["status"] == "copied"
    assert src.read_bytes() == dest.read_bytes() == b"payload"


def test_recovery_restores_verified_holding_file(route, monkeypatch):
    journal, src, dest = route
    rename = transfers.rename_new
    def crash_after_isolation(parent, name, target_parent, target):
        rename(parent, name, target_parent, target)
        if target.endswith(".holding"):
            raise SystemExit()
    with monkeypatch.context() as patch:
        patch.setattr(transfers, "rename_new", crash_after_isolation)
        with pytest.raises(SystemExit):
            journal.transfer(src, dest, analyze_file(src), "move")
    assert not src.exists() and dest.exists()
    journal.reconcile()
    assert src.read_bytes() == dest.read_bytes() and journal.history()[0]["status"] == "copied"


def test_failed_verification_leaves_source_and_target_untouched(route, monkeypatch):
    journal, src, dest = route
    hash_file = transfers.hash_file
    def corrupt(path, expected, **kwargs):
        digest = hash_file(path, expected, **kwargs)
        if kwargs.get("output"):
            kwargs["output"].write(b"corruption")
        return digest
    monkeypatch.setattr(transfers, "hash_file", corrupt)
    journal.transfer(src, dest, analyze_file(src), "move")
    row, = journal.history()
    assert src.read_bytes() == b"payload" and not dest.exists()
    assert row["status"] == "skipped" and "verification" in row["reason"]
