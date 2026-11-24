"""Verified transfers. Commit copy identities before publication and remove only after verification."""
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
from uuid import uuid4

from filemind.analyzer.verified import hash_file, metadata_signature, signature
from filemind.organizer.filesystem import FILE_ERRORS, pinned_directory, rename_new, validate


def schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS transfers (
        id INTEGER PRIMARY KEY REFERENCES moves(id), kind TEXT, stage TEXT,
        source_dir TEXT, target_dir TEXT, temp TEXT, temp_sig TEXT, dest_sig TEXT, restored_sig TEXT,
        holding TEXT)""")


def update(db, entry, stage, **values):
    values["stage"] = stage
    with db:
        db.execute("UPDATE transfers SET " + ",".join(f"{key}=?" for key in values) + " WHERE id=?",
                   (*values.values(), entry))


def outcome(db, entry, status, reason=""):
    from filemind.organizer.organizer import _stored_text
    with db:
        db.execute("UPDATE moves SET status=?,reason=? WHERE id=?", (status, _stored_text(reason), entry))


def record(db, entry):
    return db.execute("SELECT m.*, t.* FROM moves m JOIN transfers t USING(id) WHERE m.id=?", (entry,)).fetchone()


def parent_id(parent):
    info = parent.stat() if os.name == "nt" else os.fstat(parent)
    if not info.st_ino:
        raise ValueError("The volume does not provide stable directory identities")
    return json.dumps([info.st_dev, info.st_ino])


def member(parent, name):
    # A pinned directory descriptor keeps I/O on the selected Linux volume after a mount change.
    return (parent if os.name == "nt" else Path("/proc/self/fd") / str(parent)) / name


def sync_dir(parent):
    if os.name != "nt":
        os.fsync(parent)


def publish(parent, name, dest):
    if os.name == "nt":
        import win32file
        win32file.MoveFileEx(str(parent / name), str(parent / dest), 8)  # MOVEFILE_WRITE_THROUGH
    else:
        rename_new(parent, name, parent, dest)
        sync_dir(parent)


@contextmanager
def locations(row):
    original, dest = Path(row["original"]), Path(row["destination"])
    with pinned_directory(original.parent) as src, pinned_directory(dest.parent) as dst:
        if parent_id(src) != row["source_dir"] or parent_id(dst) != row["target_dir"]:
            raise ValueError("A recorded drive or folder has been replaced")
        yield src, original.name, dst, dest.name


def require_absent(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return
    raise FileExistsError(f"Destination already exists: {path.name}")


def verified_publish(db, row, src, name, expected, dst, target, restoring=False):
    entry = row["id"]
    temp_name = f".filemind-{uuid4().hex}.part"
    path, temp = member(src, name), member(dst, temp_name)
    require_absent(member(dst, target))
    update(db, entry, "restoring" if restoring else "copying", temp=temp_name, temp_sig=None, holding=None)
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        checksum = hash_file(path, expected, output=stream)
        stream.flush()
        if os.name != 'nt':
            os.fchmod(stream.fileno(), path.stat().st_mode & 0o777)
        os.utime(temp, ns=(expected[3], expected[3]))
        os.fsync(stream.fileno())
    copied = signature(temp.lstat())
    if (checksum != row["checksum"] or copied[2] != expected[2] or not copied[1]
            or hash_file(temp, copied) != checksum):
        raise ValueError("Temporary copy failed verification")
    update(db, entry, "restore verified" if restoring else "verified", temp_sig=json.dumps(copied))
    publish(dst, temp_name, target)
    if hash_file(member(dst, target), copied) != checksum:
        raise ValueError("Published file failed verification")
    field = "restored_sig" if restoring else "dest_sig"
    update(db, entry, "restored" if restoring else "published", **{field: json.dumps(copied)})
    return copied


def check_extra_data(path):
    if os.name == "nt":
        import win32file
        import pywintypes
        try:
            streams = win32file.FindStreams(str(path))
        except pywintypes.error as error:
            if error.winerror not in (38, 87):  # EOF or volume without named streams
                raise
        else:
            if any(name != "::$DATA" for _, name in streams):
                raise ValueError("File contains additional Windows data streams")
    elif os.listxattr(path):
        raise ValueError("File has extended attributes that cannot be verified by this transfer")


def remove_verified(db, row, src, name, expected, keep, keeper, keep_sig, undo):
    """Isolate the exact entry, then recheck both copies before unlinking."""
    checksum, entry = row["checksum"], row["id"]
    path, kept = member(src, name), member(keep, keeper)
    holding = f".filemind-{uuid4().hex}.holding"
    held = member(src, holding)
    if hash_file(path, expected) != checksum or hash_file(kept, keep_sig) != checksum:
        raise ValueError("Contents changed before removal")
    update(db, entry, "undo removing" if undo else "removing", holding=holding)
    rename_new(src, name, src, holding)
    try:
        with ExitStack() as locks:
            if os.name == "nt":
                import win32file
                handle = win32file.CreateFile(str(kept), win32file.GENERIC_READ,
                    win32file.FILE_SHARE_READ, None, win32file.OPEN_EXISTING, 0, None)
                locks.callback(handle.Close)
            if hash_file(held, expected) != checksum or hash_file(kept, keep_sig) != checksum:
                raise ValueError("Verification failed before removal")
            if signature(held.lstat()) != tuple(expected) or signature(kept.lstat()) != tuple(keep_sig):
                raise ValueError("File replaced before removal")
            check_extra_data(held)
            held.unlink()
    except BaseException:
        if held.exists():
            rename_new(src, holding, src, name)
        raise
    sync_dir(src)


def start(db, source, destination, metadata, kind):
    from filemind.organizer.organizer import _stored_text
    if kind not in ("copy", "move") or source != metadata.path or source == destination:
        raise ValueError("Invalid transfer")
    batch = uuid4().hex
    expected = metadata_signature(metadata)
    with pinned_directory(source.parent) as src, pinned_directory(destination.parent) as dst:
        validate(src, source.name, list(expected))
        check_extra_data(member(src, source.name))
        require_absent(member(dst, destination.name))
        checksum = hash_file(member(src, source.name), expected)
        with db:
            cursor = db.execute("""INSERT INTO moves(batch,root,original,destination,signature,checksum,status)
                VALUES(?,?,?,?,?,?,'transfer pending')""",
                (batch, _stored_text(str(source.parent)), _stored_text(str(source)), _stored_text(str(destination)),
                 json.dumps(expected), checksum))
            entry = cursor.lastrowid
            db.execute("INSERT INTO transfers(id,kind,stage,source_dir,target_dir) VALUES(?,?,?,?,?)",
                       (entry, kind, "queued", parent_id(src), parent_id(dst)))
        row = record(db, entry)
        try:
            copied = verified_publish(db, row, src, source.name, expected, dst, destination.name)
            if kind == "move":
                remove_verified(db, row, src, source.name, expected, dst, destination.name, copied, False)
            outcome(db, entry, "moved" if kind == "move" else "copied")
        except FILE_ERRORS as error:
            recover(db, entry, str(error))
    return batch


def state(path, expected, checksum):
    try:
        path.lstat()
    except FileNotFoundError:
        return "absent"
    if not expected:
        return "other"
    return "valid" if hash_file(path, json.loads(expected)) == checksum else "other"


def recover(db, entry, reason="Interrupted transfer"):
    row = record(db, entry)
    stage = row["stage"]
    undoing = stage.startswith(("undo", "restor"))
    status = "transfer pending"
    try:
        with locations(row) as (src, name, dst, target):
            holding_parent = dst if undoing else src
            if row["holding"] and member(holding_parent, row["holding"]).exists():
                held = member(holding_parent, row["holding"])
                expected = row["dest_sig"] if undoing else row["signature"]
                if state(held, expected, row["checksum"]) != "valid":
                    raise ValueError(f"Inspect retained file {row['holding']}")
                rename_new(holding_parent, row["holding"], holding_parent, target if undoing else name)
                sync_dir(holding_parent)
            if row["temp"] and member(src if undoing else dst, row["temp"]).exists():
                reason += f" · retained temporary file {row['temp']}"
            dest_sig = row["dest_sig"] or (row["temp_sig"] if stage == "verified" else None)
            original_sig = row["restored_sig"] or (row["temp_sig"] if stage == "restore verified" else row["signature"])
            a = state(member(src, name), original_sig, row["checksum"])
            b = state(member(dst, target), dest_sig, row["checksum"])
            if b == "valid" and not row["dest_sig"]:
                update(db, entry, stage, dest_sig=dest_sig)
            if undoing:
                if a == "valid" and b == "absent":
                    status = "undone"
                elif a == "valid" and b == "valid":
                    status = "copied"
                    update(db, entry, stage, restored_sig=original_sig)
                elif a == "absent" and b == "valid" and row["kind"] == "move":
                    status = "moved"
            elif b == "valid" and a == "absent" and row["kind"] == "move":
                status = "moved"
            elif a == "valid" and b == "valid":
                status = "copied"
                if row["kind"] == "move":
                    reason += " · source retained"
            elif a == "valid" and b == "absent":
                status = "skipped"
    except FILE_ERRORS as error:
        reason += f" · {error}"
    outcome(db, entry, status, reason)


def undo(db, entry):
    row = record(db, entry)
    if row["status"] not in ("copied", "moved"):
        return
    try:
        with locations(row) as (src, name, dst, target):
            copied = json.loads(row["dest_sig"])
            if row["status"] == "copied":
                original = json.loads(row["restored_sig"] or row["signature"])
                if hash_file(member(src, name), original) != row["checksum"]:
                    raise ValueError("Original no longer matches the verified copy")
            else:
                require_absent(member(src, name))
            outcome(db, entry, "transfer pending", "Undo in progress")
            if row["status"] == "moved":
                original = verified_publish(db, row, dst, target, copied, src, name, restoring=True)
            remove_verified(db, row, dst, target, copied, src, name, original, True)
            outcome(db, entry, "undone")
    except FILE_ERRORS as error:
        if record(db, entry)["status"] == "transfer pending":
            recover(db, entry, f"Undo interrupted · {error}")
        else:
            outcome(db, entry, row["status"], f"Undo blocked · {error}")
