"""Command-line entry point for the current FileMind scanner prototype."""

import argparse
from pathlib import Path

from filemind.scanner.scanner import scan_directory


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List files recursively inside a directory."
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory to scan",
    )
    args = parser.parse_args()

    try:
        result = scan_directory(args.directory)
    except (FileNotFoundError, NotADirectoryError) as error:
        parser.error(str(error))

    print(f"Found {len(result.files)} files in {args.directory}:\n")

    for file_path in result.files:
        print(file_path.name)

    for issue in result.issues:
        print(f"Warning: could not scan {issue.path}: {issue.message}")


if __name__ == "__main__":
    main()
