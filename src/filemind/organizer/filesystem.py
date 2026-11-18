"""Personal-file validation and same-volume, no-replace renames."""

import ctypes
import hashlib
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path
import stat
import sys


def _personal(info):
    if os.name != "nt" and (info.st_uid != os.getuid() or info.st_uid == 0):
        raise PermissionError("Only files and folders owned by the current user can be organized")
    attributes = getattr(info, "st_file_attributes", 0)
    if attributes & (stat.FILE_ATTRIBUTE_REPARSE_POINT | stat.FILE_ATTRIBUTE_SYSTEM):
        raise PermissionError("System files and links cannot be organized")


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
def parent_handle(path, home, create_from=None):
    """Pin directories while checking and renaming. Only Apply creates category folders."""
    parts = personal_parts(path, home)
    current = home
    with ExitStack() as stack:
        if os.name == "nt":
            import win32con
            import win32file

            def pin(directory):
                _personal(directory.lstat())
                handle = win32file.CreateFile(
                    str(directory), win32con.FILE_READ_ATTRIBUTES,
                    win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE, None,
                    win32con.OPEN_EXISTING, win32con.FILE_FLAG_BACKUP_SEMANTICS |
                    win32con.FILE_FLAG_OPEN_REPARSE_POINT, None,
                )
                stack.callback(handle.Close)
                _personal(directory.lstat())
            pin(home)
            for part in parts:
                current /= part
                if create_from and current.is_relative_to(create_from):
                    current.mkdir(exist_ok=True)
                pin(current)
            yield current
        else:
            flags = os.O_DIRECTORY | os.O_NOFOLLOW | os.O_RDONLY
            fd = os.open(home, flags)
            stack.callback(os.close, fd)
            _personal(os.fstat(fd))
            for part in parts:
                current /= part
                if create_from and current.is_relative_to(create_from):
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                fd = os.open(part, flags, dir_fd=fd)
                stack.callback(os.close, fd)
                _personal(os.fstat(fd))
            yield fd


def _entry(parent, name):
    if os.name == "nt":
        return (parent / name).lstat()
    return os.stat(name, dir_fd=parent, follow_symlinks=False)


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
    validate(parent, name, expected)
    if os.name == "nt":
        stream = (parent / name).open("rb")
    else:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        stream = os.fdopen(fd, "rb")
    with stream:
        if signature(os.fstat(stream.fileno())) != expected:
            raise ValueError("File changed before reading")
        value = hashlib.file_digest(stream, "sha256").hexdigest()
        if signature(os.fstat(stream.fileno())) != expected:
            raise ValueError("File changed while reading")
    return value


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


def move(root, home, original, organized, expected, checksum, undo=False):
    personal_parts(root, home)
    for path in (original, organized):
        personal_parts(path, home)
        if not path.is_relative_to(root):
            raise PermissionError("Path outside scanned folder")
    if organized.parent.parent != root / "Organized" or organized.name != original.name:
        raise ValueError("Invalid proposed destination")
    source, dest = (organized, original) if undo else (original, organized)
    with parent_handle(source.parent, home) as src:
        if digest(src, source.name, expected) != checksum:
            raise ValueError("File contents have changed")
        create_from = None if undo else root / "Organized"
        with parent_handle(dest.parent, home, create_from) as dst:
            volume = dst.stat().st_dev if os.name == "nt" else os.fstat(dst).st_dev
            if volume != expected[0]:
                raise ValueError("Destination is on a different filesystem")
            try:
                _entry(dst, dest.name)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError("Destination already exists")
            validate(src, source.name, expected)
            rename_new(src, source.name, dst, dest.name)
