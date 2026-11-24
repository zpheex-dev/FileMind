"""Local file metadata and supported document text extraction."""

import os
import stat as stat_module
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import pymupdf


MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 50
MAX_EXTRACTED_CHARACTERS = 100_000
TEXT_EXTENSIONS = {".txt", ".md", ".py", ".csv", ".json", ".log"}

ContentStatus = Literal["extracted", "unsupported", "skipped", "error", "pending"]


@dataclass(frozen=True)
class FileMetadata:
    path: Path
    name: str
    extension: str
    size_bytes: int | None
    created_at: datetime | None
    modified_at: datetime | None
    extracted_text: str | None
    content_status: ContentStatus
    content_truncated: bool = False
    analysis_error: str | None = None
    modified_at_ns: int | None = None
    identity: tuple[int, int] | None = None


def analyze_file(file_path: str | Path, *, extract_content: bool = True) -> FileMetadata:
    """Extract basic metadata and bounded text content from one local file."""
    path = Path(file_path)
    extension = path.suffix.lower()
    try:
        stat = path.stat()
        if not stat_module.S_ISREG(stat.st_mode):
            raise OSError("Not a regular file")
    except OSError as error:
        return FileMetadata(
            path=path,
            name=path.name,
            extension=extension,
            size_bytes=None,
            created_at=None,
            modified_at=None,
            extracted_text=None,
            content_status="error",
            analysis_error=f"Could not read file metadata: {error}",
            modified_at_ns=None,
        )

    created_at = _creation_time(stat)
    try:
        modified_at = datetime.fromtimestamp(stat.st_mtime)
    except (OSError, OverflowError, ValueError) as error:
        modified_at = None
        metadata_error = f"Could not read modification time: {error}"
    else:
        metadata_error = None

    if extract_content:
        text, status, truncated, content_error = _extract_text(path, extension, stat.st_size)
    else:
        text, status, truncated, content_error = None, "pending", False, None
    errors = [error for error in (metadata_error, content_error) if error]
    return FileMetadata(
        path=path,
        name=path.name,
        extension=extension,
        size_bytes=stat.st_size,
        created_at=created_at,
        modified_at=modified_at,
        extracted_text=text,
        content_status=status,
        content_truncated=truncated,
        analysis_error="; ".join(errors) if errors else None,
        modified_at_ns=stat.st_mtime_ns,
        identity=(stat.st_dev, stat.st_ino),
    )


def _creation_time(stat: os.stat_result) -> datetime | None:
    timestamp = getattr(stat, "st_birthtime", None)
    if timestamp is None and os.name == "nt":
        timestamp = stat.st_ctime
    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(timestamp)
    except (OSError, OverflowError, ValueError):
        return None


def _extract_text(
    path: Path,
    extension: str,
    size_bytes: int,
    stream=None,
) -> tuple[str | None, ContentStatus, bool, str | None]:
    if extension in TEXT_EXTENSIONS:
        if size_bytes > MAX_TEXT_BYTES:
            return (
                None,
                "skipped",
                False,
                f"Text extraction is limited to {MAX_TEXT_BYTES} bytes per file.",
            )
        try:
            with (path.open("rb") if stream is None else nullcontext(stream)) as file:
                data = file.read(MAX_TEXT_BYTES + 1)
        except OSError as error:
            return None, "error", False, f"Could not read text content: {error}"
        if len(data) > MAX_TEXT_BYTES:
            return (
                None,
                "skipped",
                False,
                f"Text extraction is limited to {MAX_TEXT_BYTES} bytes per file.",
            )

        text = data.decode("utf-8-sig", errors="replace")
        truncated = len(text) > MAX_EXTRACTED_CHARACTERS
        return (
            text[:MAX_EXTRACTED_CHARACTERS],
            "extracted",
            truncated,
            None,
        )

    if extension != ".pdf":
        return None, "unsupported", False, None
    if size_bytes > MAX_PDF_BYTES:
        return (
            None,
            "skipped",
            False,
            f"PDF extraction is limited to {MAX_PDF_BYTES} bytes per file.",
        )

    try:
        if stream is None:
            document = pymupdf.open(path)
        else:
            data = stream.read(MAX_PDF_BYTES + 1)
            if len(data) > MAX_PDF_BYTES:
                return None, "skipped", False, "PDF exceeded the extraction limit."
            document = pymupdf.open(stream=data, filetype="pdf")
        with document:
            if document.needs_pass:
                return None, "error", False, "Password-protected PDFs are not read."

            truncated = document.page_count > MAX_PDF_PAGES
            text_parts: list[str] = []
            character_count = 0
            for page_index in range(min(document.page_count, MAX_PDF_PAGES)):
                page_text = document.load_page(page_index).get_text()
                remaining = MAX_EXTRACTED_CHARACTERS - character_count
                if len(page_text) > remaining:
                    text_parts.append(page_text[:remaining])
                    truncated = True
                    break
                text_parts.append(page_text)
                character_count += len(page_text)
            return (
                "".join(text_parts),
                "extracted",
                truncated,
                None,
            )
    except (OSError, RuntimeError, ValueError) as error:
        return None, "error", False, f"Could not extract PDF text: {error}"
