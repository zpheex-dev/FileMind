"""Read a recorded regular file and reject changes before or during the read."""
from contextlib import contextmanager
import hashlib
import os
import stat


def signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def metadata_signature(record):
    return (*(record.identity or (None, None)), record.size_bytes, record.modified_at_ns)


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise InterruptedError("Cancelled")


@contextmanager
def recorded_stream(path, expected):
    def check(info):
        if (not stat.S_ISREG(info.st_mode) or signature(info) != tuple(expected)
                or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError(f"File changed: {path}")

    before = path.lstat()
    check(before)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        check(opened)
        yield stream
        after = os.fstat(stream.fileno())
        check(after)
        current = path.lstat()
        check(current)
        if opened.st_ctime_ns != after.st_ctime_ns or before.st_ctime_ns != current.st_ctime_ns:
            raise ValueError(f"File changed during read: {path}")


def hash_file(path, expected, cancel=None, output=None):
    digest = hashlib.sha256()
    total = 0
    with recorded_stream(path, expected) as stream:
        while True:
            check_cancel(cancel)
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > expected[2]:
                raise ValueError(f"File grew during read: {path}")
            digest.update(chunk)
            if output is not None:
                output.write(chunk)
    if total != expected[2]:
        raise ValueError(f"File size changed during read: {path}")
    return digest.hexdigest()
