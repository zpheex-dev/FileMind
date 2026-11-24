"""Folder-local inventory comparisons and explicit SQLite snapshots."""
from contextlib import closing
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sqlite3

from filemind.analyzer.metadata import analyze_file
from filemind.analyzer.verified import check_cancel, hash_file, metadata_signature
from filemind.scanner.scanner import scan_directory


@dataclass
class Inventory:
    root: Path
    files: dict
    gaps: set

    def uncertain(self, name):
        path = Path(name)
        return any(part.as_posix() in self.gaps for part in (path, *path.parents))


def inventory(root, records, issues):
    return Inventory(root, {m.path.relative_to(root).as_posix(): metadata_signature(m) for m in records},
                     {i.path.relative_to(root).as_posix() for i in issues})


def scan_inventory(root, cancel):
    scan = scan_directory(root, cancellation_event=cancel)
    def records():
        for path in scan.files:
            check_cancel(cancel)
            yield analyze_file(path, extract_content=False)
    check_cancel(cancel)
    return inventory(root, records(), scan.issues)


def compare(left, right, cancel, verify=False, snapshots=False):
    rows = []
    for name in sorted(left.files.keys() | right.files.keys()):
        check_cancel(cancel)
        a, b = left.files.get(name), right.files.get(name)
        size_a, size_b = a[2] if a else None, b[2] if b else None
        delta = size_b - size_a if None not in (size_a, size_b) else None
        if a is None or b is None:
            absent = left if a is None else right
            if absent.uncertain(name):
                status = "Unreadable subtree"
            else:
                status = "Added" if a is None else "Removed"
                delta = size_b if a is None else (-size_a if size_a is not None else None)
        elif None in (size_a, size_b, a[3], b[3]):
            status = "Metadata unavailable"
        else:
            status = "Apparently matching" if a[2:] == b[2:] else "Changed"
            if snapshots and a[:2] != b[:2]:
                status = "Changed"
            if verify and status == "Apparently matching":
                try:
                    one = hash_file(left.root / name, a, cancel)
                    two = hash_file(right.root / name, b, cancel)
                except InterruptedError:
                    raise
                except (OSError, ValueError) as error:
                    status = f"Unverified · {error}"
                else:
                    status = "SHA-256 match" if one == two else "Changed (SHA-256)"
        if not snapshots or status != "Apparently matching":
            rows.append((name, size_a, size_b, delta, status))
    for gap in sorted(left.gaps | right.gaps):
        if gap not in left.files and gap not in right.files:
            rows.append((gap, None, None, None, "Unreadable subtree"))
    check_cancel(cancel)
    return rows


def connect(database):
    database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return sqlite3.connect(database, timeout=10)


def snapshots(database, view, save=False):
    key = os.fsencode(os.path.normcase(view.root))
    with closing(connect(database)) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS snapshots
                   (id INTEGER PRIMARY KEY, root BLOB, created TEXT DEFAULT CURRENT_TIMESTAMP, data TEXT)""")
        if save:
            db.execute("INSERT INTO snapshots(root,data) VALUES(?,?)",
                       (key, json.dumps([view.files, sorted(view.gaps)])))
        return db.execute("SELECT id,created FROM snapshots WHERE root=? ORDER BY id DESC", (key,)).fetchall()


def snapshot_diff(database, view, entry, cancel):
    with closing(connect(database)) as db:
        data, = db.execute("SELECT data FROM snapshots WHERE root=? AND id=?",
                           (os.fsencode(os.path.normcase(view.root)), entry)).fetchone()
    files, gaps = json.loads(data)
    return compare(Inventory(view.root, {k: tuple(v) for k,v in files.items()}, set(gaps)),
                   view, cancel, snapshots=True)
