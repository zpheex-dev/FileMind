"""Cleanup candidates and estimated bytes released after emptying Trash."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from filemind.analyzer.metadata import FileMetadata
from filemind.analyzer.verified import check_cancel, hash_file, metadata_signature, signature
from filemind.duplicate_detector.detector import find_duplicates


@dataclass
class Candidate:
    record: FileMetadata
    reasons: list
    links: int
    group: str | None = None


def candidates(root, records, downloads, cancel):
    result = find_duplicates(records, cancellation_event=cancel)
    check_cancel(cancel)
    groups = {path: group.sha256 for group in result.groups for path in group.files}
    folder_sizes = Counter()
    seen = set()
    for record in records:
        check_cancel(cancel)
        parent = record.path.parent
        for folder in (parent, *parent.parents):
            if folder == root or not folder.is_relative_to(root):
                break
            key = folder, record.identity or record.path
            if key not in seen:
                seen.add(key)
                folder_sizes[folder] += record.size_bytes or 0
    cutoff = datetime.now() - timedelta(days=90)
    rows = {}
    for record in records:
        check_cancel(cancel)
        path = record.path
        reasons = []
        folder = next((p for p in path.parents if folder_sizes[p] >= 100 * 1024**2), None)
        if folder:
            reasons.append(f"Large folder · {folder.relative_to(root)} ({folder_sizes[folder]:,} bytes)")
        if downloads and path.is_relative_to(downloads) and record.modified_at and record.modified_at < cutoff:
            reasons.append("Download last modified over 90 days ago")
        group = groups.get(path)
        if group:
            reasons.append(f"Exact duplicate · {group[:12]}")
        if reasons:
            try:
                info = path.lstat()
            except OSError:
                continue
            if signature(info) == metadata_signature(record):
                rows[path] = Candidate(record, reasons, info.st_nlink, group)
    return rows, result.issues


def estimated_bytes(rows, selected):
    counts = defaultdict(list)
    for path in set(selected):
        row = rows[path]
        counts[row.record.identity].append(row)
    return sum(group[0].record.size_bytes for group in counts.values()
               if len(group) == group[0].links and group[0].links > 0)


def trash_selected(rows, selected, keepers, trash, cancel):
    from filemind.organizer.filesystem import FILE_ERRORS, pinned_directory, validate

    selected = tuple(dict.fromkeys(selected))
    if set(selected).intersection(keepers.values()):
        raise ValueError("A selected file is marked as a keeper.")
    outcomes = []
    for path in selected:
        if cancel.is_set():
            break
        row = rows[path]
        try:
            expected = metadata_signature(row.record)
            with pinned_directory(path.parent) as parent:
                validate(parent, path.name, list(expected))
                if row.group:
                    keeper = keepers[row.group]
                    if keeper == path or rows[keeper].group != row.group:
                        raise ValueError("Choose another verified copy to keep.")
                    with pinned_directory(keeper.parent):
                        if hash_file(path, expected, cancel) != row.group or hash_file(
                                keeper, metadata_signature(rows[keeper].record), cancel) != row.group:
                            raise ValueError("The selected copy or keeper has changed.")
                validate(parent, path.name, list(expected))
                check_cancel(cancel)
                if not trash(path):
                    raise OSError("System Trash declined the file.")
        except InterruptedError:
            break
        except FILE_ERRORS as error:
            outcomes.append((path, str(error)))
        else:
            outcomes.append((path, "Trashed"))
    return outcomes
