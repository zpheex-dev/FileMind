import os
from pathlib import Path

import pytest

from filemind.analyzer.metadata import analyze_file
from filemind.categorizer.classifier import ClassifiedFile, RuleBasedClassifier
from filemind.organizer import filesystem
from filemind.organizer.organizer import MoveJournal
from filemind.organizer.planner import propose_organization


def user_file(path, content):
    path.write_text(content)
    if os.name == "nt":
        # Elevated CI accounts can default new files to the Administrators group.
        import win32api
        import win32con
        import win32security as security
        token = security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
        try:
            user, _ = security.GetTokenInformation(token, security.TokenUser)
        finally:
            token.Close()
        security.SetNamedSecurityInfo(str(path), security.SE_FILE_OBJECT,
                                      security.OWNER_SECURITY_INFORMATION, user, None, None, None)


def classified(path):
    record = analyze_file(path, extract_content=False)
    return ClassifiedFile(record, RuleBasedClassifier().classify(record))


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    root = tmp_path / "Downloads"
    root.mkdir()
    files = []
    for name in ("a.txt", "b.txt", "c.txt"):
        path = root / name
        user_file(path, name)
        files.append(classified(path))
    return (MoveJournal(tmp_path / "history.db"), root, propose_organization(root, files),
            {item.metadata.path: item.metadata for item in files})


def test_selection_partial_failure_and_reopened_undo(workspace):
    journal, root, proposals, metadata = workspace
    first, second, unchecked = proposals
    second.destination.parent.mkdir(parents=True)
    second.destination.write_text("taken")
    journal.apply(root, [second, first], metadata)
    assert second.current_path.read_text() == "b.txt"
    assert second.destination.read_text() == "taken"
    assert unchecked.current_path.exists() and not unchecked.destination.exists()
    assert first.destination.read_text() == "a.txt" and not first.current_path.exists()
    reopened = MoveJournal(journal.database)
    reopened.reconcile()
    moved, skipped = reopened.history()
    assert skipped["status"] == "skipped" and skipped["reason"]
    reopened.undo([moved["id"]])
    assert first.current_path.read_text() == "a.txt" and not first.destination.exists()
    assert reopened.history()[0]["status"] == "undone"


@pytest.mark.parametrize("conflict", ["occupied", "edited", "replaced"])
def test_undo_conflicts(workspace, conflict):
    journal, root, rows, metadata = workspace
    p = rows[0]
    journal.apply(root, [p], metadata)
    if conflict == "occupied":
        p.current_path.write_text("new occupant")
    else:
        before = p.destination.stat()
        if conflict == "replaced":
            other = root / "replacement"
            user_file(other, "a.txt")
            other.replace(p.destination)
        else:
            user_file(p.destination, "x.txt")
        os.utime(p.destination, ns=(before.st_atime_ns, before.st_mtime_ns))
    journal.undo([journal.history()[0]["id"]])
    assert journal.history()[0]["status"] == "moved"
    assert "Undo blocked" in journal.history()[0]["reason"]
    assert p.destination.read_text() == ("x.txt" if conflict == "edited" else "a.txt")
    if conflict == "occupied":
        assert p.current_path.read_text() == "new occupant"
    else:
        assert not p.current_path.exists()


@pytest.mark.parametrize("undo", [False, True])
@pytest.mark.parametrize("after_rename", [False, True])
def test_interruption_recovery(workspace, monkeypatch, undo, after_rename):
    journal, root, rows, metadata = workspace
    if undo:
        journal.apply(root, rows[:1], metadata)
    real = filesystem.rename_new

    def interrupt(*args):
        if after_rename:
            real(*args)
        raise KeyboardInterrupt

    monkeypatch.setattr(filesystem, "rename_new", interrupt)
    with pytest.raises(KeyboardInterrupt):
        if undo:
            journal.undo([journal.history()[0]["id"]])
        else:
            journal.apply(root, rows, metadata)
    reopened = MoveJournal(journal.database)
    reopened.reconcile()
    states = {Path(r["original"]).name: r["status"] for r in reopened.history()}
    assert states["a.txt"] == (("undone" if after_rename else "moved") if undo
                               else ("moved" if after_rename else "skipped"))
    if not undo:
        assert states["b.txt"] == states["c.txt"] == "skipped"


def test_collision_at_rename_and_stale_source(workspace, monkeypatch):
    journal, root, rows, metadata = workspace
    first, second, _ = rows
    real = filesystem.rename_new
    def occupy(*args):
        first.destination.write_text("late arrival")
        real(*args)
    second.current_path.unlink()
    monkeypatch.setattr(filesystem, "rename_new", occupy)
    journal.apply(root, rows[:2], metadata)
    assert all(row["status"] == "skipped" and row["reason"] for row in journal.history())
    assert first.current_path.read_text() == "a.txt"
    assert first.destination.read_text() == "late arrival"


def test_protected_paths_and_conflicts(workspace):
    journal, root, rows, metadata = workspace
    from dataclasses import replace
    hidden = root / ".private"
    hidden.mkdir()
    path = hidden / "a.txt"
    user_file(path, "private")
    record = classified(path)
    protected = propose_organization(root, [record])[0]
    metadata[path] = record.metadata
    journal.apply(root, [protected, replace(rows[0], conflicts=("conflict",))], metadata)
    assert len(journal.history()) == 1 and journal.history()[0]["status"] == "skipped"
    assert path.read_text() == "private" and not (root / "Organized").exists()


def test_symlink_destination_cannot_redirect_moves(workspace):
    journal, root, rows, metadata = workspace
    try:
        (root / "Organized").symlink_to(root.parent, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable")
    journal.apply(root, rows[:1], metadata)
    assert journal.history()[0]["status"] == "skipped"
    assert not (root.parent / "Documents").exists()


def test_different_volume_refusal_preserves_source(workspace, monkeypatch):
    import errno
    journal, root, rows, metadata = workspace
    def refuse(*args):
        raise OSError(errno.EXDEV, "Cross-device rename")
    monkeypatch.setattr(filesystem, "rename_new", refuse)
    journal.apply(root, rows[:1], metadata)
    assert rows[0].current_path.exists() and not rows[0].destination.exists()
    assert journal.history()[0]["status"] == "skipped"


def test_interrupted_move_with_both_paths_needs_review(workspace, monkeypatch):
    journal, root, rows, metadata = workspace
    rename = filesystem.rename_new
    def interrupt(*args):
        rename(*args)
        rows[0].current_path.write_text("new occupant")
        raise KeyboardInterrupt
    monkeypatch.setattr(filesystem, "rename_new", interrupt)
    with pytest.raises(KeyboardInterrupt):
        journal.apply(root, rows[:1], metadata)
    journal.reconcile()
    assert journal.history()[0]["status"] == "needs review"
    assert rows[0].current_path.read_text() == "new occupant"
    assert rows[0].destination.read_text() == "a.txt"


def test_second_instance_cannot_reconcile_live_batch(workspace, monkeypatch):
    journal, root, rows, metadata = workspace
    other = MoveJournal(journal.database)
    rename = filesystem.rename_new

    def reopen_during_move(*args):
        other.reconcile()
        rename(*args)

    monkeypatch.setattr(filesystem, "rename_new", reopen_during_move)
    journal.apply(root, rows, metadata)
    assert all(row["status"] == "moved" for row in journal.history())
