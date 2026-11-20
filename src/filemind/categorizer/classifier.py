"""Transparent rule-based classification with a replaceable interface."""

from dataclasses import dataclass
from typing import Protocol

from filemind.analyzer.metadata import FileMetadata


CATEGORY_BY_EXTENSION = {
    ".pdf": "Documents",
    ".txt": "Documents",
    ".md": "Documents",
    ".rtf": "Documents",
    ".doc": "Documents",
    ".docx": "Documents",
    ".odt": "Documents",
    ".log": "Documents",
    ".csv": "Spreadsheets",
    ".tsv": "Spreadsheets",
    ".xls": "Spreadsheets",
    ".xlsx": "Spreadsheets",
    ".ods": "Spreadsheets",
    ".ppt": "Presentations",
    ".pptx": "Presentations",
    ".odp": "Presentations",
    ".py": "Code",
    ".ipynb": "Code",
    ".js": "Code",
    ".jsx": "Code",
    ".ts": "Code",
    ".tsx": "Code",
    ".html": "Code",
    ".css": "Code",
    ".java": "Code",
    ".c": "Code",
    ".h": "Code",
    ".cpp": "Code",
    ".cs": "Code",
    ".go": "Code",
    ".rs": "Code",
    ".php": "Code",
    ".sql": "Code",
    ".sh": "Code",
    ".ps1": "Code",
    ".jpg": "Images",
    ".jpeg": "Images",
    ".png": "Images",
    ".gif": "Images",
    ".bmp": "Images",
    ".svg": "Images",
    ".webp": "Images",
    ".tif": "Images",
    ".tiff": "Images",
    ".heic": "Images",
    ".mp3": "Audio",
    ".wav": "Audio",
    ".flac": "Audio",
    ".aac": "Audio",
    ".ogg": "Audio",
    ".m4a": "Audio",
    ".mp4": "Video",
    ".mov": "Video",
    ".avi": "Video",
    ".mkv": "Video",
    ".webm": "Video",
    ".wmv": "Video",
    ".zip": "Archives",
    ".7z": "Archives",
    ".rar": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
    ".bz2": "Archives",
    ".xz": "Archives",
    ".zst": "Archives",
    **dict.fromkeys((".ini", ".cfg", ".conf", ".toml", ".yaml", ".yml"), "Configuration"),
    **dict.fromkeys((".db", ".sqlite", ".sqlite3", ".mdb", ".accdb", ".duckdb"), "Databases"),
    **dict.fromkeys((".psd", ".xcf", ".kra", ".ai", ".fig", ".sketch", ".indd"), "Design"),
    **dict.fromkeys((".iso", ".img", ".dmg", ".vhd", ".vhdx", ".vmdk"), "Disk Images"),
    **dict.fromkeys((".epub", ".mobi", ".azw", ".azw3", ".fb2", ".cbz", ".cbr"), "E-books"),
    **dict.fromkeys((".ttf", ".otf", ".woff", ".woff2"), "Fonts"),
    **dict.fromkeys((".exe", ".msi", ".msix", ".appimage", ".deb", ".rpm", ".apk"), "Software"),
    **dict.fromkeys((".srt", ".vtt", ".ass", ".ssa"), "Subtitles"),
    **dict.fromkeys((".blend", ".obj", ".stl", ".fbx", ".gltf", ".glb", ".3mf"), "3D Models"),
}

KNOWN_CATEGORIES = frozenset(CATEGORY_BY_EXTENSION.values()) | {"Other"}

RULE_CONFIDENCE = 0.95
UNKNOWN_CONFIDENCE = 0.2


@dataclass(frozen=True)
class ClassificationResult:
    """A category decision; rule-based scores are heuristic, not probabilities."""

    category: str
    confidence: float
    explanation: str
    method: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Classification confidence must be between 0 and 1.")


class Classifier(Protocol):
    """Interface implemented by rule-based and future model classifiers."""

    def classify(self, file_metadata: FileMetadata) -> ClassificationResult:
        """Return a category, confidence, and human-readable explanation."""


@dataclass(frozen=True)
class ClassifiedFile:
    metadata: FileMetadata
    classification: ClassificationResult


class RuleBasedClassifier:
    """Assign broad categories; scores indicate rule strength, not probability."""

    def classify(self, file_metadata: FileMetadata) -> ClassificationResult:
        extension = file_metadata.extension.casefold()
        category = CATEGORY_BY_EXTENSION.get(extension)
        if category is not None:
            return ClassificationResult(
                category=category,
                confidence=RULE_CONFIDENCE,
                explanation=(
                    f"Rule-based match: the {extension} extension maps to "
                    f"{category}."
                ),
                method="rule-based",
            )

        extension_label = extension or "no extension"
        return ClassificationResult(
            category="Other",
            confidence=UNKNOWN_CONFIDENCE,
            explanation=(
                f"No extension rule matches {extension_label}; categorized as Other."
            ),
            method="rule-based",
        )
