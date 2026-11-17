# FileMind architecture

## Design principles

- Keep filesystem scanning, analysis, classification, persistence, and user
  interface responsibilities separate.
- Prefer local processing; do not upload users' files.
- Scanning and analysis must be read-only.
- A future organization operation must be previewed and explicitly confirmed,
  must not overwrite an existing destination, and must be recorded so it can be
  undone safely.
- Keep classification behind a replaceable interface so transparent rules can
  later coexist with a trained model.

## Current package layout

| Package or file | Responsibility | Current state |
| --- | --- | --- |
| `src/filemind/main.py` | `filemind-scan` command-line prototype | Lists files from a user-selected directory |
| `src/filemind/scanner/` | Discover files and collect filesystem paths | Recursively scans without following symlinks; reports progress, cancellation, and per-directory errors |
| `src/filemind/analyzer/metadata.py` | Extract filesystem metadata and supported text | Reads timestamps/size, optionally extracting bounded TXT, Markdown, Python, CSV, JSON, LOG, and PDF content |
| `src/filemind/categorizer/classifier.py` | Categorize files behind a replaceable interface | Extension-based rules return a category, heuristic score, method, and explanation |
| `src/filemind/organizer/` | Build and execute safe organization plans | Placeholder |
| `src/filemind/database/` | Persist scan and operation history | Placeholder |
| `src/filemind/gui/app.py` | Start the PySide6 desktop application | Creates the application and applies the shared theme |
| `src/filemind/gui/window.py` | Persistent navigation and page switching | Connects folder selection, progress, cancellation, and results |
| `src/filemind/duplicate_detector/` | Identify exact duplicate content | Groups same-size candidates by local SHA-256 and reports file issues without modifying files |
| `src/filemind/gui/pages.py` | Dashboard and feature page layouts | Displays recursive scan metadata, local text previews, and duplicate-check results |
| `src/filemind/gui/components.py`, `theme.py` | Shared components and visual design system | Reusable cards, badges, empty states, and dark styling |
| `src/filemind/gui/workers.py` | Run GUI-triggered work outside the main thread | Scans, analyzes, and hashes duplicate candidates in `QThread`s with progress and cancellation; selected-file preview extraction uses a separate worker |

The scanner returns a `ScanResult` containing discovered `pathlib.Path` objects,
per-directory issues, and cancellation status. It never changes file contents.
GUI scans request metadata only; the inspector caches at most eight on-demand text previews.
The file inventory uses a QAbstractTableModel with a sorting/filtering proxy instead of per-cell widgets.
The analyzer returns immutable `FileMetadata` records, including an explicit
content status and any extraction error.

## Current scan and analysis flow

1. The user selects a directory from the dashboard or shared header.
2. A `QThread` recursively discovers regular files without following symlinks.
3. The worker reports scan and analysis progress and can stop between directory entries or files.
4. The analyzer records path, extension, size, and timestamps, then records an on-demand content status. Selected-file previews extract text in a separate worker.
5. The rule-based classifier maps file extensions to broad categories and explains each decision.
6. The dashboard displays file count, total size, and category count; My Files shows metadata, category, heuristic score, and selected text preview.
7. Accessible results are retained while filesystem issues and per-file analysis errors are reported.

Scanning and analysis never change file contents. Text extraction is limited to
2 MiB per supported text file and 20 MiB / 50 pages per PDF, with a 100,000
character preview cap. These limits are deliberate safeguards against very large
documents.

## Exact duplicate detection

The Duplicate Finder uses the metadata from the latest completed scan. It first
groups files by size so singleton sizes do not need to be hashed, then reads
candidate files in 1 MiB chunks and computes SHA-256 locally. It checks size and
modification time before and after each hash; files that disappear, change, or
cannot be read are reported as issues rather than reported as confirmed
duplicates. A result groups only files with both the same size and same hash,
and reports the potentially redundant bytes without taking any file action.

Hashing runs in a cancellable `QThread`. A cancelled check discards partial
groups and leaves the previous complete results visible. A new completed scan
replaces the candidate list and clears old duplicate results. Duplicate
detection never deletes or modifies files.

## Planned data flow

1. A GUI worker recursively scans a user-selected directory without blocking the interface.
2. The analyzer extracts file metadata and supported document text.
3. A classifier returns a category, confidence, and an explanation.
4. The implemented duplicate detector groups same-size files with matching SHA-256 hashes.
5. The recommendation engine creates a reviewable organization plan.
6. Only after explicit user approval does the organizer move selected files.
7. SQLite stores completed operations and original paths for safe undo.

The GUI will call these modules through focused interfaces rather than owning
business logic itself. File movement remains unavailable. Expensive scanning,
hashing, and extraction will run outside the GUI thread.

`Classifier` is a protocol; `RuleBasedClassifier` is the current implementation.
Its confidence-like score is a heuristic rule strength, not a calibrated
probability. A future local model can implement the same interface without
changing the GUI or scan worker.

## Milestones

1. Establish package metadata, basic tests, and architecture documentation.
2. Build the shared PySide6 shell and consistent navigation.
3. Connect dashboard and file explorer views to real data.
4. Add recursive scanning and metadata/content analysis with background work.
5. Add an explainable rule-based classifier and a model-ready interface.
6. Add and integrate SHA-256 exact duplicate detection.
7. Generate explainable organization recommendations and previews.
8. Add confirmation-gated moves, conflict checks, SQLite history, and undo.
9. Expand tests, optimize large scans, and finish user documentation.

Each milestone should be validated before the next begins. File movement remains
out of scope until the user can review and explicitly confirm a plan.
