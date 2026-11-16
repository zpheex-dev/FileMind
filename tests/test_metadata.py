from pathlib import Path

import pymupdf
import pytest

import filemind.analyzer.metadata as metadata_module
from filemind.analyzer.metadata import analyze_file


def test_analyze_text_file_extracts_metadata_and_content(tmp_path: Path) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text("A local note", encoding="utf-8")

    result = analyze_file(file_path)

    assert result.path == file_path
    assert result.name == "notes.txt"
    assert result.extension == ".txt"
    assert result.size_bytes == len("A local note")
    assert result.modified_at is not None
    assert result.extracted_text == "A local note"
    assert result.content_status == "extracted"
    assert result.analysis_error is None


def test_analyze_pdf_extracts_page_text(tmp_path: Path) -> None:
    file_path = tmp_path / "document.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Local PDF content")
    document.save(file_path)
    document.close()

    result = analyze_file(file_path)

    assert result.content_status == "extracted"
    assert result.extracted_text is not None
    assert "Local PDF content" in result.extracted_text


def test_analyze_unsupported_file_does_not_claim_extraction(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(b"image")

    result = analyze_file(file_path)

    assert result.size_bytes == 5
    assert result.content_status == "unsupported"
    assert result.extracted_text is None


def test_analyze_invalid_pdf_returns_an_error_without_crashing(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "invalid.pdf"
    file_path.write_bytes(b"not a pdf")

    result = analyze_file(file_path)

    assert result.content_status == "error"
    assert result.analysis_error is not None


def test_text_extraction_skips_files_above_the_configured_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "large.txt"
    file_path.write_text("more than four bytes", encoding="utf-8")
    monkeypatch.setattr(metadata_module, "MAX_TEXT_BYTES", 4)

    result = analyze_file(file_path)

    assert result.content_status == "skipped"
    assert result.extracted_text is None
    assert "limited to 4 bytes" in (result.analysis_error or "")
