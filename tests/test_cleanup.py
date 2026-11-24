import os
import time
from threading import Event

from filemind.analyzer.metadata import analyze_file
from filemind.cleanup import candidates, estimated_bytes, trash_selected
from test_moves import user_file


def test_cleanup_keeper_and_hardlinks(tmp_path):
    a, b, c = (tmp_path / n for n in ("a", "b", "c"))
    user_file(a, "same")
    os.link(a, b)
    user_file(c, "same")
    old = time.time() - 91 * 86400
    os.utime(c, (old, old))
    rows, _ = candidates(tmp_path, list(map(analyze_file, (a, b, c))), tmp_path, Event())
    assert "90 days" in " ".join(rows[c].reasons)
    assert estimated_bytes(rows, [a]) == 0 and estimated_bytes(rows, [a,b]) == 4
    called = []
    keep = {rows[a].group: c}
    c.write_text("changed keeper")
    assert trash_selected(rows, [a], keep, called.append, Event())[0][1] != "Trashed"
    assert not called and a.exists()
    keep[rows[a].group] = b
    assert trash_selected(rows, [a], keep, lambda p: called.append(p) or True, Event()) == [(a, "Trashed")]
    assert called == [a]


def test_large_folder_has_reason_and_no_automatic_selection(tmp_path):
    path = tmp_path / "large" / "sparse"
    path.parent.mkdir()
    with path.open("wb") as stream:
        stream.truncate(101 * 1024**2)
    rows, _ = candidates(tmp_path, [analyze_file(path, extract_content=False)], None, Event())
    assert "Large folder · large" in rows[path].reasons[0]
    assert estimated_bytes(rows, []) == 0
