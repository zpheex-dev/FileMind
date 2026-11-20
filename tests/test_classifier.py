from pathlib import Path

import pytest
from PySide6.QtTest import QSignalSpy

from filemind.analyzer.metadata import FileMetadata, analyze_file
from filemind.categorizer.classifier import (
    ClassifiedFile,
    ClassificationResult,
    RuleBasedClassifier,
)
from filemind.gui.workers import DirectoryScanWorker


@pytest.mark.parametrize(
    ("filename", "expected_category"),
    [
        ("report.pdf", "Documents"),
        ("budget.xlsx", "Spreadsheets"),
        ("photo.jpg", "Images"),
        ("organizer.py", "Code"),
        ("movie.mp4", "Video"),
        ("archive.zip", "Archives"),
        ("preferences.toml", "Configuration"),
        ("catalog.sqlite3", "Databases"),
        ("mockup.psd", "Design"),
        ("backup.iso", "Disk Images"),
        ("novel.epub", "E-books"),
        ("family.WOFF2", "Fonts"),
        ("setup.msi", "Software"),
        ("captions.srt", "Subtitles"),
        ("model.glb", "3D Models"),
    ],
)
def test_rule_classifier_maps_known_extensions(
    tmp_path: Path,
    filename: str,
    expected_category: str,
) -> None:
    file_path = tmp_path / filename
    file_path.write_bytes(b"test")
    result = RuleBasedClassifier().classify(analyze_file(file_path))

    assert result.category == expected_category
    assert result.confidence == 0.95
    assert result.method == "rule-based"
    assert "extension" in result.explanation


def test_rule_classifier_explains_unknown_extensions(tmp_path: Path) -> None:
    file_path = tmp_path / "unknown.bin"
    file_path.write_bytes(b"test")

    result = RuleBasedClassifier().classify(analyze_file(file_path))

    assert result.category == "Other"
    assert result.confidence == 0.2
    assert "No extension rule matches .bin" in result.explanation


def test_classification_result_validates_confidence() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        ClassificationResult(
            category="Other",
            confidence=1.1,
            explanation="Invalid score",
            method="test",
        )


def test_scan_worker_accepts_a_classifier_implementation(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text("A note", encoding="utf-8")

    class FixedClassifier:
        def classify(self, file_metadata: FileMetadata) -> ClassificationResult:
            return ClassificationResult(
                category="Reviewed",
                confidence=0.7,
                explanation=f"Reviewed {file_metadata.name}.",
                method="test",
            )

    worker = DirectoryScanWorker(tmp_path, classifier=FixedClassifier())
    completed = QSignalSpy(worker.completed)
    worker.run()

    assert completed.count() == 1
    files = completed.at(0)[1]
    assert isinstance(files[0], ClassifiedFile)
    assert files[0].classification.category == "Reviewed"
