import os
from threading import Event

import pytest

from filemind.database.inventory import Inventory, compare, scan_inventory, snapshot_diff, snapshots


def test_snapshot_partial_scan(tmp_path):
    root = tmp_path / "root"
    sig = (1, 2, 10, 400)
    old = Inventory(root, {name: sig for name in ("private/a", "gone", "changed", "unknown")}, set())
    db = tmp_path / "db"
    entry = snapshots(db, old, True)[0][0]
    current = Inventory(root, {"changed": (1, 2, 15, 405), "added": sig,
                               "unknown": (None, None, None, None)}, {"private"})
    result = {row[0]: row[3:] for row in snapshot_diff(db, current, entry, Event())}
    assert result == {"private/a": (None, "Unreadable subtree"), "private": (None, "Unreadable subtree"),
                      "added": (10, "Added"), "gone": (-10, "Removed"), "changed": (5, "Changed"),
                      "unknown": (None, "Metadata unavailable")}
    assert not snapshots(db, Inventory(tmp_path, {}, set()))


def test_side_by_side_hash_and_cancellation(tmp_path):
    cancel = Event()
    views = []
    for name, content in (("left", b"one"), ("right", b"two")):
        root = tmp_path / name
        root.mkdir()
        for path, data in ((root / "a", content), (root / "b", b"same")):
            path.write_bytes(data)
            os.utime(path, ns=(123000000000, 123000000000))
        views.append(scan_inventory(root, cancel))
    assert [r[-1] for r in compare(*views, cancel)] == ["Apparently matching"] * 2
    assert [r[-1] for r in compare(*views, cancel, verify=True)] == ["Changed (SHA-256)", "SHA-256 match"]
    cancel.set()
    with pytest.raises(InterruptedError):
        compare(*views, cancel, verify=True)
