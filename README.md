# FileMind

FileMind is a local-first desktop file organizer in early development. Its long-term
goal is to help users understand and organize files while keeping file processing
on their own computer.

## Launch the desktop app

On Windows, double-click **`dist/FileMind.exe`** after building, or download the
Windows executable from GitHub Releases. Python is not required to run the
standalone executable. `run_filemind.bat` also prefers the built executable.

On Linux, download `FileMind-linux-x86_64`, run `chmod +x FileMind-linux-x86_64`,
then launch it. Linux builds are produced on Linux by the release workflow;
a Windows build cannot run on Linux.

The desktop interface uses Python with Qt/PySide6: compact graphite panels,
cyan accents, sortable file columns, category filters, and a resizable inspector.

## Current status

The PySide6 desktop shell can recursively scan a selected directory in a background
thread, report progress, and cancel a scan. My Files displays file names, types,
sizes and modification times. Supported text previews load in a background
thread when a file is selected. Cached previews are revalidated against size and
nanosecond modification time on reselection; missing or unreadable files show errors.
Transparent extension-based classification with explanations is also available.
The Duplicate Finder uses local SHA-256 hashing to report exact duplicates from
the latest scan. It hashes only same-size candidates, runs in a background
thread, and can be cancelled. Recoverable-byte estimates count distinct filesystem
identities, so hard links do not inflate storage savings. All matching paths remain
visible. It never deletes or changes files.
The Organizer page now shows read-only Proposed Organization suggestions from
the latest completed scan, including explanations and destination conflicts.
Machine-learning classification, database-backed history, and safe move/undo
workflows have not been implemented.

Scanning and analysis are read-only. Directory scans collect metadata without
extracting every document. The file inventory uses a virtual table model,
search is debounced, and only eight extracted previews are cached in memory. Text extraction supports TXT, Markdown,
Python, CSV, JSON, and log files, plus PDFs through PyMuPDF. Extraction is bounded
to protect responsiveness and memory use; oversized files are skipped with an
explanation. Unsupported files still appear in the file list.

The current classifier uses explicit extension rules. Its displayed score is a
heuristic rule strength, not a trained model probability. Unknown extensions are
categorized as **Other** with a low score and an explanation.

## Requirements

- Windows 10 or later (primary development platform)
- Linux x86_64 desktop (packaged executable targets Ubuntu 22.04 or compatible)
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

On Linux, create a virtual environment and install the same requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

## Run FileMind

Start the desktop application:

```powershell
filemind
```

You can also double-click `run_filemind.bat` from the project folder. It uses
the project's `.venv` when available, otherwise it uses the Python launcher or
`python` on your PATH. Install the project dependencies first.

On Linux, run `bash run_filemind.sh`. It uses `.venv` when available, otherwise
it uses `python3` on your PATH. Install the project dependencies first.

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

Open **AI Organizer** to review **Proposed Organization**. Each file is proposed
for an Organized folder inside the scanned root, then a category folder, retaining
its filename (for example, Organized/Documents/report.pdf).
Files already at their destination are omitted. Existing destinations and multiple
files targeting the same destination are flagged. Unknown extensions go to **Other**.
A completed scan replaces the plan, including an empty scan; cancelled or failed
scans retain the previous plan. Conflicts are a snapshot: rescan to refresh them.
Generating a plan never creates folders, moves, overwrites, or deletes files.

## Standalone executables

For a repeatable build on either Windows or Linux:

```bash
python -m pip install ".[build]"
python build_app.py
```

The output is `dist/FileMind.exe` on Windows or `dist/FileMind` on Linux.
The single-file package extracts its runtime at startup, so the first launch
can take a few seconds. `--smoke-test` opens and automatically closes the app
for packaging verification.

The builder includes the SVG from the checkout. Verify the executable and its
rendered icon with `dist/FileMind.exe --smoke-test` on Windows or
`QT_QPA_PLATFORM=offscreen ./dist/FileMind --smoke-test` on Linux.

The Windows output is `dist\FileMind.exe`; the Linux output is `dist/FileMind`.
The Linux release is named `FileMind-linux-x86_64`. Make it executable, then
run it:

```bash
chmod +x FileMind-linux-x86_64
./FileMind-linux-x86_64
```

The Linux release is built on Ubuntu 22.04 for x86_64 and requires glibc 2.35 or
later plus the system libraries required by Qt. To create a GitHub Release with
both platform builds, push a version tag such as `v0.1.0`. Published downloads
will appear on the [Releases page](https://github.com/zpheex-dev/FileMind-vibecoded/releases).

## Run tests

```powershell
python -m pytest
```

Tests run on Windows and Linux for pushes and pull requests. Release builds
run tests before packaging. The suite also fails on unhandled Python exceptions
inside Qt callbacks.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for module responsibilities,
current implementation status, and the planned development sequence.