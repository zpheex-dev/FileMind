"""Interactive tools for a completed scan. Disk operations run in a worker."""
from pathlib import Path
from threading import Event

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from filemind.analyzer.metadata import TEXT_EXTENSIONS
from filemind.database.search import refresh, search
from filemind.database.inventory import compare, scan_inventory, snapshot_diff, snapshots


class Task(QThread):
    def __init__(self, parent, operation):
        super().__init__(parent)
        self.operation = operation
        self.cancel = Event()
        self.error = ""
        self.value = None

    def run(self):
        try:
            self.value = self.operation(self.cancel)
        except Exception as error:
            self.error = str(error) or type(error).__name__


class ToolDialog(QDialog):
    def __init__(self, parent, title, columns):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(880, 480)
        self.task = None
        self.layout_box = QVBoxLayout(self)
        self.controls = QWidget()
        self.actions = QHBoxLayout(self.controls)
        self.layout_box.addWidget(self.controls)
        self.table = QTreeWidget()
        self.table.setHeaderLabels(columns)
        self.table.setRootIsDecorated(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.layout_box.addWidget(self.table)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.layout_box.addWidget(self.status)
        self.cancel_button = QPushButton("Cancel operation")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        self.layout_box.addWidget(self.cancel_button)

    def action(self, name, slot):
        button = QPushButton(name)
        self.actions.addWidget(button)
        button.clicked.connect(slot)
        return button

    def cancel(self):
        if self.task:
            self.task.cancel.set()

    def reject(self):
        if self.task:
            self.cancel()
        else:
            super().reject()

    def run_task(self, operation, complete):
        if self.task:
            return
        self.controls.setEnabled(False)
        self.table.setEnabled(False)
        self.cancel_button.show()
        self.status.setText("Working…")
        self.task = Task(self, operation)
        self.complete = complete
        self.task.finished.connect(self.finished_task)
        self.task.start()

    def finished_task(self):
        worker, self.task = self.task, None
        self.controls.setEnabled(True)
        self.table.setEnabled(True)
        self.cancel_button.hide()
        self.status.setText(worker.error)
        if not worker.error:
            self.complete(worker.value)
        worker.deleteLater()

    def show_rows(self, rows):
        self.table.clear()
        self.table.addTopLevelItems([QTreeWidgetItem(["—" if x is None else str(x) for x in row])
                                    for row in rows])
        self.table.resizeColumnToContents(0)
        self.status.setText(f"{len(rows):,} results")


class ComparisonDialog(ToolDialog):
    def __init__(self, parent, view, database):
        super().__init__(parent, "Compare scans and folders",
                         ("Relative path", "Before / left bytes", "After / right bytes", "Byte delta", "Status"))
        self.view = view
        self.database = database
        self.right = None
        self.baseline = QComboBox()
        self.actions.addWidget(self.baseline)
        self.action("Save snapshot", lambda: self.load_snapshots(True))
        self.diff_button = self.action("Compare snapshot", self.diff)
        self.action("Compare folder…", self.choose)
        self.verify = self.action("Verify apparent matches", self.verify_matches)
        self.verify.setEnabled(False)
        self.context = QLabel(str(view.root))
        self.layout_box.insertWidget(0, self.context)
        self.load_snapshots(False)

    def load_snapshots(self, save):
        def loaded(rows):
            self.baseline.clear()
            for entry, created in rows:
                self.baseline.addItem(f"{created} UTC · #{entry}", entry)
            self.diff_button.setEnabled(bool(rows))
            self.status.setText("Snapshot saved" if save else f"{len(rows)} saved snapshots")
        self.run_task(lambda _: snapshots(self.database, self.view, save), loaded)

    def diff(self):
        entry = self.baseline.currentData()
        self.verify.setEnabled(False)
        self.context.setText(f"{self.baseline.currentText()} → current scan of {self.view.root}")
        self.run_task(lambda cancel: snapshot_diff(self.database, self.view, entry, cancel), self.show_rows)

    def choose(self):
        folder = QFileDialog.getExistingDirectory(self, "Compare scanned folder with")
        if not folder:
            return
        def load(cancel):
            right = scan_inventory(Path(folder), cancel)
            return right, compare(self.view, right, cancel)
        def loaded(result):
            self.right, rows = result
            self.context.setText(f"Left: {self.view.root}    Right: {folder}")
            self.verify.setEnabled(True)
            self.show_rows(rows)
        self.run_task(load, loaded)

    def verify_matches(self):
        self.run_task(lambda cancel: compare(self.view, self.right, cancel, verify=True), self.show_rows)


class SearchDialog(ToolDialog):
    def __init__(self, parent, view, database):
        super().__init__(parent, "Content search", ("Relative path", "Matching text"))
        self.view, self.database = view, database
        self.terms = QLineEdit()
        self.terms.setPlaceholderText("Search indexed words")
        self.terms.returnPressed.connect(self.query)
        self.actions.addWidget(self.terms)
        self.extension = QComboBox()
        self.extension.addItems(["All types", *sorted(TEXT_EXTENSIONS | {".pdf"})])
        self.actions.addWidget(self.extension)
        self.action("Search", self.query)
        self.action("Build / refresh local index", self.refresh)
        self.action("Inspect", self.inspect)
        self.table.itemActivated.connect(self.inspect)
        self.path = None
        self.status.setText("Build the index to store searchable document text locally for this folder.")

    def refresh(self):
        self.run_task(lambda cancel: refresh(self.database, self.view, cancel), self.status.setText)

    def query(self):
        terms = self.terms.text()
        ext = self.extension.currentText() if self.extension.currentIndex() else ""
        self.run_task(lambda cancel: search(self.database, self.view.root, terms, ext, cancel), self.show_rows)

    def inspect(self, *_):
        item = self.table.currentItem()
        if item and not self.task:
            if item.text(0) not in self.view.files:
                self.status.setText("This indexed file was inaccessible in the current scan.")
                return
            self.path = self.view.root / item.text(0)
            self.accept()
