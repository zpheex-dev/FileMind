"""Personal-file validation and same-volume, no-replace renames."""

from filemind.organizer.rules import validate_folder

import ctypes
import hashlib
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path
import stat
import sys


FILE_ERRORS = (OSError, ValueError)
if os.name == "nt":
    import pywintypes
    FILE_ERRORS += (pywintypes.error,)


def _personal(info):
    if os.name != "nt" and (info.st_uid != os.getuid() or info.st_uid == 0):
        raise PermissionError("Only files and folders owned by the current user can be organized")
    attributes = getattr(info, "st_file_attributes", 0)
    if attributes & (stat.FILE_ATTRIBUTE_REPARSE_POINT | stat.FILE_ATTRIBUTE_SYSTEM | stat.FILE_ATTRIBUTE_HIDDEN):
        raise PermissionError("System files, hidden files and links cannot be organized")


def personal_parts(path, home):
    if not path.is_absolute() or not path.is_relative_to(home):
        raise PermissionError("Choose a folder inside your user profile")
    parts = path.relative_to(home).parts
    if any(part.startswith(".") or ":" in part for part in parts):
        raise PermissionError("Hidden folders, hidden files and special paths are excluded")
    if os.name == "nt" and parts and parts[0].lower() == "appdata":
        raise PermissionError("Application data is excluded")
    return parts


@contextmanager
def parent_handle(path, home, create_from=None, on_create=None):
    """Pin directories while checking and renaming. Only Apply creates category folders."""
    parts = personal_parts(path, home)
    current = home
    with ExitStack() as stack:
        if os.name == "nt":
            import win32file

            def pin(directory):
                _personal(directory.lstat())
                handle = win32file.CreateFile(
                    str(directory), 0,
                    win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE, None,
                    win32file.OPEN_EXISTING, win32file.FILE_FLAG_BACKUP_SEMANTICS |
                    win32file.FILE_FLAG_OPEN_REPARSE_POINT, None,
                )
                stack.callback(handle.Close)
                info = directory.lstat()
                _personal(info)
                if not stat.S_ISDIR(info.st_mode):
                    raise NotADirectoryError(directory)
                return info
            pin(home)
            for part in parts:
                current /= part
                created = False
                if create_from and current.is_relative_to(create_from):
                    try:
                        current.mkdir()
                    except FileExistsError:
                        pass
                    else:
                        created = True
                info = pin(current)
                if created and on_create is not None:
                    on_create(current, info)
            yield current
        else:
            flags = os.O_DIRECTORY | os.O_NOFOLLOW | os.O_RDONLY
            fd = os.open(home, flags)
            stack.callback(os.close, fd)
            _personal(os.fstat(fd))
            for part in parts:
                current /= part
                created = False
                if create_from and current.is_relative_to(create_from):
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                    else:
                        created = True
                fd = os.open(part, flags, dir_fd=fd)
                stack.callback(os.close, fd)
                info = os.fstat(fd)
                _personal(info)
                if created and on_create is not None:
                    on_create(current, info)
            yield fd


@contextmanager
def pinned_directory(path):
    """Pin an explicitly selected directory, including directories on removable drives."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Choose an absolute directory")
    with ExitStack() as stack:
        if os.name == "nt":
            import win32file
            for directory in (*reversed(path.parents), path):
                handle = win32file.CreateFile(
                    str(directory), 0, win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE, None,
                    win32file.OPEN_EXISTING, win32file.FILE_FLAG_BACKUP_SEMANTICS |
                    win32file.FILE_FLAG_OPEN_REPARSE_POINT, None)
                stack.callback(handle.Close)
                info = directory.lstat()
                if not stat.S_ISDIR(info.st_mode) or info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise ValueError("Transfer and cleanup directories must not be links")
            yield path
        else:
            flags = os.O_DIRECTORY | os.O_NOFOLLOW | os.O_RDONLY
            fd = os.open(path.anchor, flags)
            stack.callback(os.close, fd)
            for part in path.parts[1:]:
                fd = os.open(part, flags, dir_fd=fd)
                stack.callback(os.close, fd)
            yield fd


def _entry(parent, name):
    if os.name == "nt":
        return (parent / name).lstat()
    return os.stat(name, dir_fd=parent, follow_symlinks=False)


def directory_volume(path, home):
    with parent_handle(path, home) as parent:
        return _parent_volume(parent)


def _parent_volume(parent):
    return parent.stat().st_dev if os.name == "nt" else os.fstat(parent).st_dev


def directory_identity(info):
    return [info.st_dev, info.st_ino, getattr(info, "st_birthtime_ns", None)]


def remove_empty_directory(path, home, identity):
    """Remove one recorded directory under a pinned parent."""
    with parent_handle(path.parent, home) as parent:
        info = _entry(parent, path.name)
        _personal(info)
        if not stat.S_ISDIR(info.st_mode) or directory_identity(info) != identity:
            return False
        if os.name == "nt":
            (parent / path.name).rmdir()
        else:
            os.rmdir(path.name, dir_fd=parent)
        return True


def signature(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]


def validate(parent, name, expected):
    info = _entry(parent, name)
    _personal(info)
    if not stat.S_ISREG(info.st_mode) or signature(info) != expected or not info.st_ino:
        raise ValueError("File changed or was replaced since it was recorded")
    if os.name == "nt":
        import win32api
        import win32con
        import win32security as security
        owner = security.GetNamedSecurityInfo(
            str(parent / name), security.SE_FILE_OBJECT, security.OWNER_SECURITY_INFORMATION
        ).GetSecurityDescriptorOwner()
        token = security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
        try:
            user, _ = security.GetTokenInformation(token, security.TokenUser)
        finally:
            token.Close()
        if owner != user:
            raise PermissionError("Only files owned by the current Windows user can be organized")
    return info


def digest(parent, name, expected):
    entry = validate(parent, name, expected)
    if os.name == "nt":
        stream = (parent / name).open("rb")
    else:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        stream = os.fdopen(fd, "rb")
    with stream:
        before = os.fstat(stream.fileno())
        if signature(before) != expected:
            raise ValueError("File changed before reading")
        value = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.fstat(stream.fileno())
        if signature(after) != expected or after.st_ctime_ns != before.st_ctime_ns:
            raise ValueError("File changed while reading")
    # Compare path timestamps to path timestamps. On Windows, stat and
    # fstat can expose different meanings for ctime on the same NTFS file.
    return value, entry.st_ctime_ns


def rename_new(source, name, destination, target):
    if os.name == "nt":
        os.rename(source / name, destination / target)
    elif sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        if not hasattr(libc, "renameat2"):
            raise OSError("This system does not provide no-overwrite rename")
        if libc.renameat2(source, os.fsencode(name), destination, os.fsencode(target), 1):
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), target)
    else:
        raise OSError("Safe moves are supported on Linux and Windows")


def move(root, home, original, organized, expected, checksum, undo=False, on_create=None,
         *, personal_folder=False):
    personal_parts(root, home)
    personal_parts(original, home)
    personal_parts(organized, home)
    if not original.is_relative_to(root):
        raise PermissionError("Path outside scanned folder")
    if not personal_folder:
        folders = organized.parent.relative_to(root / "Organized").parts
        if not folders:
            raise ValueError("Invalid proposed destination")
        for part in folders:
            validate_folder(part)
    if organized.name != original.name:
        validate_folder(organized.name)
    source, dest = (organized, original) if undo else (original, organized)
    with parent_handle(source.parent, home) as src:
        value, change_time = digest(src, source.name, expected)
        if value != checksum:
            raise ValueError("File contents have changed")
        create_from = None if undo or personal_folder else root / "Organized"
        with parent_handle(dest.parent, home, create_from, on_create) as dst:
            if _parent_volume(dst) != expected[0]:
                raise ValueError("Destination is on a different filesystem")
            try:
                _entry(dst, dest.name)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError("Destination already exists")
            current = validate(src, source.name, expected)
            if current.st_ctime_ns != change_time:
                raise ValueError("File changed before rename")
            rename_new(src, source.name, dst, dest.name)
