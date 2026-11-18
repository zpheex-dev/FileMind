"""Build the standalone executable on Windows or Linux: python build_app.py."""

from pathlib import Path
import subprocess
import sys


def main() -> None:
    root = Path(__file__).resolve().parent
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--onefile", "--windowed", "--name", "FileMind", "--paths", "src",
         "--collect-all", "pymupdf", "--collect-data", "filemind", "--specpath", "build/pyinstaller",
         "--workpath", "build/pyinstaller/work", "--distpath", "dist",
         "src/filemind/gui/app.py"],
        cwd=root, check=True,
    )
    print(f"Executable: {root / 'dist' / ('FileMind.exe' if sys.platform == 'win32' else 'FileMind')}")


if __name__ == "__main__":
    main()
