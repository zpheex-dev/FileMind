# FileMind architecture

## Inventory and inspection

`scanner.scan_directory` enumerates regular files with `os.scandir`. An enumeration
error at the root fails the attempt. An error below the root records a path and
continues. The scanner skips symlinks and checks the Windows mount-point reparse tag
to skip junctions on Python 3.11 and later.

`DirectoryScanWorker` collects metadata and classifies each discovered file.
Only its completed signal replaces the inventory, graph totals, duplicate candidates
and Organizer plan. A readable empty root produces a completed empty inventory.
Overview keeps the report for the latest attempt alongside the last completed
inventory. Chart shapes and the keyboard-accessible legend use the same category
navigation signal as the category table.

My Files uses a sortable Qt table model with a debounced filename/location filter.
The preview worker loads the selected file on demand and checks cached identity,
size, modification time and readability. The bounded extractor supports UTF-8 text
(TXT, MD, PY, CSV, JSON, LOG) up to 2 MiB and PDFs up to 20 MiB or 50 pages.
Extracted text is capped at 100,000 characters. Classification uses extension rules
behind the `Classifier` protocol.

## Organizer and History

The folder profile in QSettings holds exclusions, category folders and an ordered
list of rules. The planner evaluates all populated conditions in a row and uses the
first match. The category mapping is the fallback. Nested destination components
and edited names must pass portable filename validation. The local modification year
expands `<year>`. A missing year blocks that proposal. A PlanWorker builds the entire
dry run after each edit, checking disk occupancy, parent directories, batch collisions
and scanned signatures. Generation numbers discard obsolete worker results.

Apply captures selected proposals and their metadata before confirmation. A journal
worker passes those routes to `MoveJournal`. Same-volume Organizer moves stay within
the user profile and use pinned directories and a no-replace rename. The journal
records filesystem identities and a SHA-256 checksum in SQLite. Undo checks the
recorded paths and content, restores the original filename and removes only empty,
recorded destination directories with matching identities. Legacy move rows use
the same execution and recovery path. A process lock serializes mutations and recovery.

## Snapshots, folder comparison and full-text search

The tools under My Files operate on the completed scan. Each dialog runs disk I/O
in a QThread. A snapshot persists the root, relative paths, file identity, size,
nanosecond mtime and discovery gaps in the per-user `inventory.sqlite3`. Snapshot
comparisons also detect identity replacement. Two-folder comparison uses relative
paths, size and mtime across volumes. Missing metadata and unreadable subtrees are
reported explicitly. Optional SHA-256 verification reopens both apparent matches,
checks their scanned signatures and tests cancellation between chunks.

The FTS5 index shares the inventory database. Each row of bounded text is associated
with one root, relative path, extension and scanned signature. Explicit index refresh
uses a transaction, reads changed files through a checked open descriptor, skips
unchanged signatures and removes confirmed stale paths. A cancelled refresh rolls
back. Previous entries beneath discovery gaps are retained. Search quotes literal
terms, intersects them and returns ranked snippets for the chosen root and type.
The inspector uses the selected path in the current inventory. Builds without FTS5
can still scan, compare snapshots and organize files.

## Duplicates and cleanup

Duplicate Finder hashes same-size candidates, checking identities and timestamps
around the read. Cancellation during hashing, grouping or worker publication keeps
the last completed result. Cleanup reuses duplicate detection and also computes
subfolder sizes and old Downloads candidates. The user chooses paths and a keeper
per duplicate group. Savings count an inode once if all its recorded links are
selected. The estimate is logical file size after emptying Trash. It excludes
filesystem compression, allocation overhead and blocks shared between distinct inodes.

Cleanup confirms the selected count, pins parent directories, checks the selected
file against its inventory and rehashes the duplicate and keeper before invoking
Qt's system Trash operation. Batch results report each success or refusal. A busy
FileMind operation holds the same process lock. Trash recovery belongs to the OS.

## Verified transfers

Explicit copy and move use a companion `transfers` table keyed by the existing
`moves` journal ID. Both selected parent directories are pinned. Their persisted
identities prevent an unavailable or replacement mount from being treated as the
recorded drive. FileMind writes a unique temporary file on the target volume,
flushes it, checks its SHA-256 against the recorded source, and commits its signature
before publishing with a no-replace rename. Linux syncs the containing directory.
Windows requests write-through publication.

A move isolates the recorded source under a journaled holding name, rechecks the
held file and published copy, then unlinks the held file. Undo of a move follows
the same verified-copy procedure back to an unoccupied original path. Undo of a
copy requires the original to pass verification before removing the destination.
Regular files with extended attributes or named streams are outside this transfer
format. The copy is independent of other hard links and inherits destination ACLs.

On startup the journal checks interrupted stages. When a verified holding entry can
be returned to its unoccupied name, recovery restores it. With both valid paths,
the operation is recorded as a copy and can be undone. With only a verified move
destination it is recorded as moved. Recovery leaves ambiguous or unavailable
locations pending. An incomplete destination temporary file may remain, with its
name reported in History. Reopening FileMind retries pending records. These checks
assume a filesystem that honors flush requests. Concurrent edits by other programs
can block an operation.

Published platform builds are available from [FileMind Releases](https://github.com/zpheex-dev/FileMind/releases).
