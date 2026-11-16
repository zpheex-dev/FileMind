# FileMind

FileMind is a local-first desktop file organizer in early development. Its long-term
goal is to help users understand and organize files while keeping file processing
on their own computer.

## Current status

The PySide6 desktop shell can recursively scan a selected directory in a background
thread, report progress, and cancel a scan. My Files displays file names, types,
sizes, modification times, and extracted text previews for supported files.
Transparent extension-based classification with explanations is also available.
The Duplicate Finder uses local SHA-256 hashing to report exact duplicates from
the latest scan. It hashes only same-size candidates, runs in a background
thread, and can be cancelled. It never deletes or changes files.
Machine-learning classification, recommendations, database-backed history, and
safe move/undo workflows have not been implemented.

Scanning and analysis are read-only. Text extraction supports TXT, Markdown,
Python, CSV, JSON, and log files, plus PDFs through PyMuPDF. Extraction is bounded
to protect responsiveness and memory use; oversized files are skipped with an
explanation. Unsupported files still appear in the file list.

The current classifier uses explicit extension rules. Its displayed score is a
heuristic rule strength, not a trained model probability. Unknown extensions are
categorized as **Other** with a low score and an explanation.

## Requirements

- Windows 10 or later (primary development platform)
- Python 3.11 or later

## Install for development

From the project directory, create and activate a virtual environment, then
install the project and development dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

The `requirements.txt` file contains runtime dependencies. The development
requirements also install pytest.

## Run FileMind

Start the desktop application:

```powershell
filemind
```

The scanner is also available as a command:

```powershell
filemind-scan "C:\Users\YourName\Documents"
```

In the GUI, use **Scan folder** to choose a directory. Use **Cancel scan** while
discovery or analysis is in progress. Existing results remain available if a scan
is cancelled. After a successful scan, open **Duplicate Finder** and choose
**Find duplicates** to check exact content matches. A new successful scan
replaces the duplicate check's source list; cancelling a duplicate check keeps
the previous complete results.

## Run tests

```powershell
python -m pytest
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for module responsibilities,
current implementation status, and the planned development sequence.