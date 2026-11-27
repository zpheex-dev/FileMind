"""Durable per-file move intents. Recovery observes paths and never renames them."""

from collections import Counter
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import errno
import json
import logging
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from filemind.activity_log import write_action_log
from filemind.organizer import transfers
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
    def __init__(self, database, personal_folders=()):
        self.database = Path(database)
        self.home = Path.home()
        self.personal_folders = frozenset(personal_folders)
        self.log_directory = self.database.parent / "logs"
        self.log_error = ""

    def _connect(self):
        self.database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = _journal_row
        db.execute("""CREATE TABLE IF NOT EXISTS moves (
            id INTEGER PRIMARY KEY, batch TEXT NOT NULL, root TEXT NOT NULL,
            original TEXT NOT NULL, destination TEXT NOT NULL, signature TEXT NOT NULL,
            checksum TEXT, status TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            personal_folder INTEGER NOT NULL DEFAULT 0)""")
        if "personal_folder" not in {column["name"] for column in db.execute("PRAGMA table_info(moves)")}:
            with db:
                db.execute("BEGIN IMMEDIATE")
                if "personal_folder" not in {column["name"] for column in db.execute("PRAGMA table_info(moves)")}:
                    db.execute("ALTER TABLE moves ADD COLUMN personal_folder INTEGER NOT NULL DEFAULT 0")
        db.execute("""CREATE TABLE IF NOT EXISTS created_folders (
            path TEXT PRIMARY KEY, identity TEXT NOT NULL)""")
        transfers.schema(db)
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

    def apply(self, root, selected, metadata, *, on_progress=None):
        self.log_error = ""
        started = datetime.now(timezone.utc)
        batch = uuid4().hex
        rows = []
        for proposal in selected:
            if proposal.has_conflict:
                continue
            source = proposal.current_path
            record = metadata[source]
            expected = [*(record.identity or (None, None)), record.size_bytes, record.modified_at_ns]
            use_personal = proposal.personal_folder and proposal.destination.parent in self.personal_folders
            rows.append((batch, _stored_text(str(root)), _stored_text(str(source)),
                         _stored_text(str(proposal.destination)), json.dumps(expected), use_personal))
        with self._session() as db:
            with db:
                db.executemany("""INSERT INTO moves(batch,root,original,destination,signature,personal_folder,status)
                               VALUES(?,?,?,?,?,?,'queued')""", rows)
            queued = db.execute("SELECT * FROM moves WHERE batch=? ORDER BY id", (batch,)).fetchall()
            for processed, row in enumerate(queued, start=1):
                try:
                    checksum = self._digest(Path(row["original"]), json.loads(row["signature"]))
                except FILE_ERRORS as error:
                    LOGGER.warning("Skipping %s: %s", row["original"], error)
                    with db:
                        db.execute("UPDATE moves SET status='skipped',reason=? WHERE id=? AND status='queued'",
                                   (_stored_text(str(error)), row["id"]))
                else:
                    with db:
                        db.execute("UPDATE moves SET status='moving',checksum=? WHERE id=? AND status='queued'",
                                   (checksum, row["id"]))
                    self._finish(db, row["id"], undo=False)
                if on_progress is not None:
                    on_progress(processed, len(queued))
            report = db.execute("SELECT * FROM moves WHERE batch=? ORDER BY id", (batch,))
            self._log_moves("organize", started, report, batch=batch, scan_root=str(root))
        return batch

    def transfer(self, source, destination, metadata, kind):
        with self._session() as db:
            return transfers.start(db, source, destination, metadata, kind)

    def undo(self, ids, *, on_progress=None):
        ids = tuple(ids)
        self.log_error = ""
        started = datetime.now(timezone.utc)
        report = []
        with self._session() as db:
            for processed, entry_id in enumerate(ids, start=1):
                if db.execute('SELECT 1 FROM transfers WHERE id=?', (entry_id,)).fetchone():
                    transfers.undo(db, entry_id)
                    report.append(db.execute("SELECT * FROM moves WHERE id=?", (entry_id,)).fetchone())
                else:
                    with db:
                        eligible = db.execute(
                            "UPDATE moves SET status='undoing',reason='' WHERE id=? AND status='moved'",
                            (entry_id,),
                        ).rowcount
                    if eligible:
                        self._finish(db, entry_id, undo=True)
                        report.append(db.execute("SELECT * FROM moves WHERE id=?", (entry_id,)).fetchone())
                if on_progress is not None:
                    on_progress(processed, len(ids))
            self._log_moves("undo", started, report)

    def _log_moves(self, action, started, rows, **details):
        moves = []
        for row in rows:
            original, destination = row["original"], row["destination"]
            status = row["status"]
            if action == "undo":
                original, destination = destination, original
                if status in ("moved", "copied"):
                    status = "blocked"
            moves.append({
                "source": original, "destination": destination,
                "status": status, "reason": row["reason"],
            })
        try:
            write_action_log(self.log_directory, action, started_at=started.isoformat(),
                             outcomes=dict(Counter(move["status"] for move in moves)),
                             files=moves, **details)
        except OSError as error:
            self.log_error = f"Could not save the activity log: {error}"
            LOGGER.warning("%s", self.log_error)

    def _record_folder(self, db, path, info):
        if info.st_ino:
            db.execute("INSERT OR REPLACE INTO created_folders VALUES (?,?)",
                       (_stored_text(os.path.normcase(path)), json.dumps(directory_identity(info))))

    def _remove_empty_folders(self, db, category, root):
        for folder in (category, *category.parents):
            if not folder.is_relative_to(root / "Organized"):
                break
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
                     on_create=lambda path, info: self._record_folder(db, path, info),
                     personal_folder=bool(row["personal_folder"]))
            except FILE_ERRORS as error:
                status, reason = ("moved" if undo else "skipped"), str(error)
                if undo:
                    reason = "Undo blocked: " + reason
                LOGGER.warning("%s: %s", row["original"], reason)
            else:
                status, reason = ("undone" if undo else "moved"), ""
                if undo and not row["personal_folder"]:
                    self._remove_empty_folders(db, destination.parent, Path(row["root"]))
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
                db.commit()
                for row in db.execute("SELECT id FROM moves WHERE status='transfer pending'").fetchall():
                    transfers.recover(db, row['id'])
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
            if status == "undone" and not row["personal_folder"]:
                category = Path(row["destination"]).parent
                self._remove_empty_folders(db, category, Path(row["root"]))
            db.execute("UPDATE moves SET status=?,reason='Recovered after interruption' WHERE id=?",
                       (status, row["id"]))
