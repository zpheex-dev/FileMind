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

Choose **Choose folder** or **Scan Downloads** to start. **Overview** shows the
latest attempt, its timing, and any paths that could not be read. It also keeps
the last completed inventory and its category breakdown visible if a later
scan fails or is cancelled. The **Files by category** chart shows counts for every category.
Expand folders in **File tree** to browse the paths from that inventory.
Select a category to filter **My Files**, or select
a file to inspect its exact size, timestamps, classification, and local preview.
Use **Inspector** to collapse the details pane, or **Rescan** to refresh the
inventory. **About** includes a **Reduce motion** preference.

Open **Organizer** to review each proposed destination. After confirming a move,
FileMind opens **History & undo** and selects the completed moves from that batch.
Use **Undo selected moves** above the table and confirm to restore those files.
You can reopen History later and select individual moved rows.

Organizer remembers custom category destinations and excluded extensions separately
for each scanned folder. Exclusions affect move proposals. Excluded types still
appear in My Files and Duplicate Finder. Select eligible files or clear the selection
in one click, then review the selected and blocked counts before applying moves.

## Current status

The PySide6 desktop shell can recursively scan a selected directory in a background
thread, report progress, and cancel a scan. My Files displays file names, types,
sizes and modification times. Supported text previews load in a background
thread when a file is selected. On reselection FileMind checks file identity, size and nanosecond
modification time. Missing or unreadable files show errors.
Transparent extension-based classification with explanations is also available.
The Duplicate Finder uses local SHA-256 hashing to report exact duplicates from
the latest scan. It hashes only same-size candidates, runs in a background
thread, and can be cancelled. Recoverable-byte estimates count distinct filesystem
identities, so hard links do not inflate storage savings. All matching paths remain
visible. It never deletes or changes files.
The Organizer suggests destinations from the latest scan. You can apply checked moves
after confirmation and undo them from Activity History, including after restarting FileMind.

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

Open **Organizer** to review **Proposed Organization**. Each file is proposed
for an Organized folder inside the scanned root, then a category folder, retaining
its filename (for example, Organized/Documents/report.pdf).
Files already at their destination are omitted. Existing destinations and multiple
files targeting the same destination are flagged. Unknown extensions go to **Other**.
A completed scan replaces the plan, including an empty scan; cancelled or failed
scans retain the previous plan. Conflicts are a snapshot: rescan to refresh them.
Previewing a plan leaves files untouched. To try moving files:

1. Scan a personal folder containing a few test files. Open **Organizer**,
   review destinations and uncheck anything you want to keep in place.
2. Click **Apply selected moves** and confirm the count. FileMind creates the
   required folders under `Organized` and checks each file again before moving it.
3. In **History**, inspect both paths, the status and any skip reason.
   Select moved rows, click **Undo selected moves** and confirm. You can also
   do this after restarting FileMind. Undo removes empty destination folders
   that FileMind recorded creating.

Moves support regular user-owned files within the user profile on the same
filesystem. Hidden paths, links and system files are excluded. Existing files
are never overwritten. Undo verifies the recorded identity, size, timestamp and
SHA-256 digest. If either path conflicts, Activity History explains the reason.
FileMind stores the journal in `moves.sqlite3` in its per-user application data
directory. On startup it checks interrupted operations against both paths and
marks ambiguous results for review without changing files.

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