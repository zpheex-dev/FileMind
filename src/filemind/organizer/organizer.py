"""Durable per-file move intents. Recovery observes paths and never renames them."""

from contextlib import closing, contextmanager
import errno
import json
import logging
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from filemind.organizer.filesystem import (
    FILE_ERRORS, digest, directory_identity, move, parent_handle, personal_parts,
    remove_empty_directory,
)

LOGGER = logging.getLogger(__name__)

def _stored_text(text):
    # SQLite TEXT requires UTF-8. Preserve other POSIX filenames as raw bytes.
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return os.fsencode(text)
    return text


def _journal_row(cursor, values):
    return sqlite3.Row(cursor, tuple(os.fsdecode(value) if isinstance(value, bytes) else value
                                     for value in values))


class JournalBusyError(RuntimeError):
    pass


class MoveJournal:
    def __init__(self, database):
        self.database = Path(database)
        self.home = Path.home()

    def _connect(self):
        self.database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = _journal_row
        db.execute("""CREATE TABLE IF NOT EXISTS moves (
            id INTEGER PRIMARY KEY, batch TEXT NOT NULL, root TEXT NOT NULL,
            original TEXT NOT NULL, destination TEXT NOT NULL, signature TEXT NOT NULL,
            checksum TEXT, status TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        db.execute("""CREATE TABLE IF NOT EXISTS created_folders (
            path TEXT PRIMARY KEY, identity TEXT NOT NULL)""")
        return db

    @contextmanager
    def _session(self):
        # Hold a process lock across the commits on either side of each rename.
        # Closing the file (including process termination) releases the lock.
        self.database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.database.with_suffix(".lock").open("a+b") as lock:
            try:
                if os.name == "nt":
                    import msvcrt
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise JournalBusyError("Another FileMind instance is processing moves") from error
            with closing(self._connect()) as db:
                yield db

    def history(self):
        if not self.database.exists():
            return []
        with closing(self._connect()) as db:
            return db.execute("SELECT * FROM moves ORDER BY id DESC").fetchall()

    def _digest(self, path, expected):
        personal_parts(path, self.home)
        with parent_handle(path.parent, self.home) as directory:
            checksum, _ = digest(directory, path.name, expected)
            return checksum

    def apply(self, root, selected, metadata):
        batch = uuid4().hex
        rows = []
        for proposal in selected:
            if proposal.has_conflict:
                continue
            source = proposal.current_path
            record = metadata[source]
            expected = [*(record.identity or (None, None)), record.size_bytes, record.modified_at_ns]
            rows.append((batch, _stored_text(str(root)), _stored_text(str(source)),
                         _stored_text(str(proposal.destination)), json.dumps(expected)))
        with self._session() as db:
            with db:
                db.executemany("""INSERT INTO moves(batch,root,original,destination,signature,status)
                               VALUES(?,?,?,?,?,'queued')""", rows)
            for row in db.execute("SELECT * FROM moves WHERE batch=? ORDER BY id", (batch,)).fetchall():
                try:
                    checksum = self._digest(Path(row["original"]), json.loads(row["signature"]))
                except FILE_ERRORS as error:
                    LOGGER.warning("Skipping %s: %s", row["original"], error)
                    with db:
                        db.execute("UPDATE moves SET status='skipped',reason=? WHERE id=? AND status='queued'",
                                   (_stored_text(str(error)), row["id"]))
                    continue
                with db:
                    db.execute("UPDATE moves SET status='moving',checksum=? WHERE id=? AND status='queued'",
                               (checksum, row["id"]))
                self._finish(db, row["id"], undo=False)
        return batch

    def undo(self, ids):
        with self._session() as db:
            for entry_id in ids:
                with db:
                    eligible = db.execute("UPDATE moves SET status='undoing',reason='' WHERE id=? AND status='moved'",
                                          (entry_id,)).rowcount
                if eligible:
                    self._finish(db, entry_id, undo=True)

    def _record_folder(self, db, path, info):
        if info.st_ino:
            db.execute("INSERT OR REPLACE INTO created_folders VALUES (?,?)",
                       (_stored_text(os.path.normcase(path)), json.dumps(directory_identity(info))))

    def _remove_empty_folders(self, db, category):
        # Walk only the two destination levels. Existing user folders have no record.
        for folder in (category, category.parent):
            key = _stored_text(os.path.normcase(folder))
            record = db.execute("SELECT identity FROM created_folders WHERE path=?", (key,)).fetchone()
            if record is None:
                break
            try:
                removed = remove_empty_directory(folder, self.home, json.loads(record["identity"]))
            except FileNotFoundError:
                removed = True
            except FILE_ERRORS as error:
                if getattr(error, "errno", None) not in (errno.ENOTEMPTY, errno.EEXIST):
                    LOGGER.info("Could not remove empty folder %s: %s", folder, error)
                break
            if not removed:
                break
            db.execute("DELETE FROM created_folders WHERE path=?", (key,))

    def _finish(self, db, entry_id, undo):
        # The intent is already committed. Hold the writer lock across rename and
        # status update so another instance cannot reconcile between those steps.
        with db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM moves WHERE id=?", (entry_id,)).fetchone()
            if row["status"] != ("undoing" if undo else "moving"):
                return
            destination = Path(row["destination"])
            try:
                move(Path(row["root"]), self.home, Path(row["original"]), destination,
                     json.loads(row["signature"]), row["checksum"], undo,
                     on_create=lambda path, info: self._record_folder(db, path, info))
            except FILE_ERRORS as error:
                status, reason = ("moved" if undo else "skipped"), str(error)
                if undo:
                    reason = "Undo blocked: " + reason
                LOGGER.warning("%s: %s", row["original"], reason)
            else:
                status, reason = ("undone" if undo else "moved"), ""
                if undo:
                    self._remove_empty_folders(db, destination.parent)
            db.execute("UPDATE moves SET status=?,reason=? WHERE id=?", (status, _stored_text(reason), entry_id))

    def _location(self, path, row):
        try:
            checksum = self._digest(Path(path), json.loads(row["signature"]))
        except FileNotFoundError:
            return "absent"
        except FILE_ERRORS:
            return "unknown"
        return "matches" if checksum == row["checksum"] else "unknown"

    def reconcile(self):
        if not self.database.exists():
            return
        try:
            with self._session() as db, db:
                self._recover(db)
        except JournalBusyError:
            # The other instance still owns its intents.
            return

    def _recover(self, db):
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE moves SET status='skipped',reason='Interrupted before move' WHERE status='queued'")
        for row in db.execute("SELECT * FROM moves WHERE status IN ('moving','undoing')").fetchall():
            locations = self._location(row["original"], row), self._location(row["destination"], row)
            if locations == ("absent", "matches"):
                status = "moved"
            elif locations == ("matches", "absent"):
                status = "undone" if row["status"] == "undoing" else "skipped"
            else:
                status = "needs review"
            if status == "undone":
                category = Path(row["destination"]).parent
                if category.parent == Path(row["root"]) / "Organized":
                    self._remove_empty_folders(db, category)
            db.execute("UPDATE moves SET status=?,reason='Recovered after interruption' WHERE id=?",
                       (status, row["id"]))
