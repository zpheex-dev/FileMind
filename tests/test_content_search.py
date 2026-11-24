from threading import Event
import sqlite3

import pytest

from filemind.database.inventory import scan_inventory
from filemind.database.search import refresh, search


def test_refresh_search_type_stale_partial_and_cancel(tmp_path, monkeypatch):
    root = tmp_path / "docs"
    root.mkdir()
    a, b = root / "a.txt", root / "b.md"
    a.write_text("local alpha")
    b.write_text("beta alpha")
    db, event = tmp_path / "db", Event()
    view = scan_inventory(root, event)
    refresh(db, view, event)
    with monkeypatch.context() as patch:
        patch.setattr("filemind.database.search._extract_text", lambda *a: pytest.fail("unchanged extraction"))
        refresh(db, view, event)
    assert search(db, root, "alpha", ".md", event) == [("b.md", "beta [alpha]")]
    a.unlink()
    b.write_text("replacement")
    view = scan_inventory(root, event)
    view.gaps.add("a.txt")
    event.set()
    with pytest.raises(InterruptedError):
        refresh(db, view, event)
    event.clear()
    assert len(search(db, root, "alpha", "", event)) == 2
    refresh(db, view, event)
    assert [r[0] for r in search(db, root, "alpha", "", event)] == ["a.txt"]
    view.gaps.clear()
    refresh(db, view, event)
    assert not search(db, root, "alpha", "", event)
    assert search(db, root, "replacement", "", event)


def test_unavailable_fts5():
    from filemind.database.search import _schema
    class Missing:
        def execute(self, statement):
            raise sqlite3.OperationalError("no such module: fts5")
    with pytest.raises(ValueError, match="FTS5"):
        _schema(Missing())
