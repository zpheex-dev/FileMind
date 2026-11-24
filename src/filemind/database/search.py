"""User-triggered, transactional FTS5 indexing of bounded document text."""
from contextlib import closing
import json
import os
import sqlite3

from filemind.analyzer.metadata import TEXT_EXTENSIONS, _extract_text
from filemind.analyzer.verified import check_cancel, recorded_stream, signature
from filemind.database.inventory import connect


def _schema(db):
    try:
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS content_index USING fts5(body)")
    except sqlite3.OperationalError as error:
        if "no such module" in str(error):
            raise ValueError("Content search needs a SQLite build with FTS5.") from error
        raise
    db.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY, root BLOB, path BLOB, ext TEXT, signature TEXT, UNIQUE(root,path))""")


def refresh(database, view, cancel):
    key = os.fsencode(os.path.normcase(view.root))
    updated = skipped = removed = 0
    with closing(connect(database)) as db, db:
        _schema(db)
        db.execute("BEGIN IMMEDIATE")
        old = {os.fsdecode(path): (entry, sig) for path, entry, sig in db.execute(
            "SELECT path,id,signature FROM documents WHERE root=?", (key,))}

        def discard(entry):
            db.execute("DELETE FROM documents WHERE id=?", (entry,))
            db.execute("DELETE FROM content_index WHERE rowid=?", (entry,))

        for name, expected in view.files.items():
            check_cancel(cancel)
            path = view.root / name
            ext = path.suffix.lower()
            if ext not in TEXT_EXTENSIONS and ext != ".pdf":
                continue
            entry, prior = old.pop(name, (None, None))
            sig = json.dumps(expected)
            if expected[2] is None:
                skipped += 1
                continue
            try:
                if prior == sig and signature(path.lstat()) == tuple(expected):
                    continue
                with recorded_stream(path, expected) as stream:
                    body, status, _, _ = _extract_text(path, ext, expected[2], stream)
            except (OSError, ValueError):
                status = "error"
            if entry is not None:
                discard(entry)
            if status != "extracted":
                skipped += 1
                continue
            cursor = db.execute("INSERT INTO documents(root,path,ext,signature) VALUES(?,?,?,?)",
                                (key, os.fsencode(name), ext, sig))
            db.execute("INSERT INTO content_index(rowid,body) VALUES(?,?)", (cursor.lastrowid, body))
            updated += 1
        for name, (entry, _) in old.items():
            check_cancel(cancel)
            if not view.uncertain(name):
                discard(entry)
                removed += 1
        check_cancel(cancel)
    return f"{updated} indexed or updated · {removed} removed · {skipped} skipped"


def search(database, root, terms, extension, cancel):
    words = terms.split()
    if not words:
        return []
    query = " AND ".join('"' + word.replace('"', '""') + '"' for word in words)
    with closing(connect(database)) as db:
        _schema(db)
        db.set_progress_handler(lambda: int(cancel.is_set()), 1000)
        rows = db.execute("""SELECT d.path,snippet(content_index,0,'[',']','…',16)
            FROM content_index JOIN documents d ON d.id=content_index.rowid
            WHERE content_index MATCH ? AND d.root=? AND (?='' OR d.ext=?) ORDER BY rank""",
            (query, os.fsencode(os.path.normcase(root)), extension, extension))
        return [(os.fsdecode(path), snippet) for path, snippet in rows]
