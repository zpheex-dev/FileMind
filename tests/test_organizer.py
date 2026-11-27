from pathlib import Path

import pytest
from test_moves import set_test_owner


@pytest.fixture(autouse=True)
def personal_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)


from filemind.analyzer.metadata import analyze_file
from filemind.categorizer.classifier import ClassifiedFile, RuleBasedClassifier
from filemind.organizer.planner import propose_organization
from filemind.scanner.scanner import scan_directory


def classified_scan(root):
    import os
    if os.name == "nt":
        for path in scan_directory(root).files:
            # Elevated CI uses a group owner for new files.
            set_test_owner(path)
    classifier = RuleBasedClassifier()
    return [
        ClassifiedFile(metadata, classifier.classify(metadata))
        for metadata in (
            analyze_file(path, extract_content=False)
            for path in scan_directory(root).files
        )
    ]


def snapshot(root):
    return {
        str(path.relative_to(root)): (
            path.is_dir(), None if path.is_dir() else path.read_bytes(),
            path.stat().st_mtime_ns,
        )
        for path in [root, *root.rglob("*")]
    }


def test_proposals_reuse_classification_and_leave_filesystem_untouched(tmp_path):
    (tmp_path / "report.pdf").write_bytes(b"example")
    (tmp_path / "script.py").write_text("print('hello')")
    (tmp_path / "unknown.xyz").write_text("unknown")
    before = snapshot(tmp_path)
    plan = propose_organization(tmp_path, classified_scan(tmp_path))
    by_name = {p.current_path.name: p for p in plan}
    for name, category in (("report.pdf", "Documents"), ("script.py", "Code"),
                           ("unknown.xyz", "Other")):
        proposal = by_name[name]
        assert proposal.destination == tmp_path / "Organized" / category / name
        assert category in proposal.reason
        assert not proposal.has_conflict
    assert snapshot(tmp_path) == before


def test_occupied_destination_and_already_organized_file(tmp_path):
    (tmp_path / "Organized" / "Documents").mkdir(parents=True)
    (tmp_path / "Organized" / "Documents" / "report.txt").write_text("existing")
    (tmp_path / "report.txt").write_text("incoming")
    before = snapshot(tmp_path)
    plan = propose_organization(tmp_path, classified_scan(tmp_path))
    assert len(plan) == 1
    assert plan[0].current_path == tmp_path / "report.txt"
    assert plan[0].conflicts == ("Destination already exists",)
    assert snapshot(tmp_path) == before


def test_competing_proposals_flag_every_source(tmp_path):
    for folder in ("one", "two"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "report.txt").write_text(folder)
    before = snapshot(tmp_path)
    plan = propose_organization(tmp_path, classified_scan(tmp_path))
    assert len(plan) == 2
    assert len({p.destination for p in plan}) == 1
    assert all(p.conflicts == ("Multiple files propose this destination",) for p in plan)
    assert snapshot(tmp_path) == before


def test_correct_location_produces_no_move(tmp_path):
    (tmp_path / "Organized" / "Code").mkdir(parents=True)
    (tmp_path / "Organized" / "Code" / "main.py").write_text("pass")
    assert propose_organization(tmp_path, classified_scan(tmp_path)) == ()


def test_protected_scan_root_cannot_propose_personal_moves(tmp_path):
    protected = tmp_path / ".system"
    documents = tmp_path / "Documents"
    protected.mkdir()
    documents.mkdir()
    (protected / "report.pdf").write_text("example")
    plan = propose_organization(protected, classified_scan(protected),
                                personal_folders={"Documents": documents})
    assert plan[0].has_conflict
    assert not plan[0].personal_folder
    assert not (documents / "report.pdf").exists()


def test_category_folder_blocked_by_file(tmp_path):
    (tmp_path / "Organized").write_text("blocking file")
    (tmp_path / "report.txt").write_text("incoming")
    plan = propose_organization(tmp_path, classified_scan(tmp_path))
    proposal = next(p for p in plan if p.current_path.name == "report.txt")
    assert proposal.has_conflict


def test_both_conflict_types_are_retained(tmp_path):
    (tmp_path / "Organized" / "Documents").mkdir(parents=True)
    (tmp_path / "Organized" / "Documents" / "report.txt").write_text("occupied")
    for folder in ("one", "two"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "report.txt").write_text(folder)
    plan = propose_organization(tmp_path, classified_scan(tmp_path))
    assert len(plan) == 2
    assert all(p.conflicts == ("Destination already exists",
                              "Multiple files propose this destination") for p in plan)


def test_custom_category_folders_recheck_conflicts_and_validate_names(tmp_path):
    import pytest

    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.pdf").write_bytes(b"b")
    files = classified_scan(tmp_path)
    proposals = propose_organization(tmp_path, files, {"Documents": "My documents"})
    assert {p.destination.parent.name for p in proposals} == {"My documents"}
    for unsafe in ("../escape", "/absolute", ".", "bad\\name", "bad:folder", "trailing.", "bad*name", ".private", "con.txt", "LPT1"):
        with pytest.raises(ValueError):
            propose_organization(tmp_path, files, {"Documents": unsafe})


def test_ordered_rules_and_renamed_nested_undo(tmp_path):
    from filemind.organizer.organizer import MoveJournal
    root = tmp_path / "Downloads"
    source = root / "mail" / "invoice.txt"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"bill")
    files = classified_scan(root)
    record = files[0].metadata
    rule = dict(name="Invoices", extension="TXT", pattern="inv*.txt", age_days="0",
                size_bytes="4", source="mail", destination="Documents/Invoices/<year>")
    rules = [rule, dict(name="Other", destination="Second")]
    documents = tmp_path / "Documents"
    documents.mkdir()
    plan = propose_organization(root, files, rules=rules, filenames={source: "paid.txt"},
                                personal_folders={files[0].classification.category: documents})
    assert not plan[0].personal_folder
    dest = root / "Organized" / "Documents" / "Invoices" / str(record.modified_at.year) / "paid.txt"
    assert plan[0].destination == dest and "Invoices" in plan[0].reason
    journal = MoveJournal(tmp_path / "journal.db")
    journal.apply(root, plan, {source: record})
    assert dest.read_bytes() == b"bill" and not source.exists()
    journal.undo([journal.history()[0]["id"]])
    assert source.read_bytes() == b"bill" and not (root / "Organized").exists()
    for key, value in (("extension", "pdf"), ("pattern", "x*"), ("age_days", "30"),
                       ("size_bytes", "5"), ("source", "archive")):
        assert propose_organization(root, files, rules=[{**rule, key: value}])[0].destination.parent.name == "Documents"
