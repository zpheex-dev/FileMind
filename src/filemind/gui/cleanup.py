from pathlib import Path

from PySide6.QtCore import QFile, Qt
from PySide6.QtWidgets import QMessageBox, QTreeWidgetItem

from filemind.cleanup import candidates, estimated_bytes, trash_selected
from filemind.gui.file_model import format_size
from filemind.gui.inventory_tools import ToolDialog


class CleanupDialog(ToolDialog):
    def __init__(self, parent, root, records, downloads, journal):
        super().__init__(parent, "Cleanup", ("File", "Reason", "Size", "Duplicate keeper"))
        self.root = root
        self.journal = journal
        self.rows = {}
        self.keepers = {}
        self.items = {}
        self.changed = False
        self.action("Keep highlighted copy", self.keep)
        self.action("Trash checked files…", self.trash)
        self.table.itemChanged.connect(self.summary)
        self.run_task(lambda cancel: candidates(root, records, downloads, cancel), self.loaded)

    def loaded(self, result):
        self.rows, issues = result
        self.issues = len(issues)
        self.table.blockSignals(True)
        self.table.clear()
        self.items.clear()
        for path, row in self.rows.items():
            if row.group:
                self.keepers.setdefault(row.group, path)
            item = QTreeWidgetItem((str(path.relative_to(self.root)), " · ".join(row.reasons),
                                    format_size(row.record.size_bytes), ""))
            item.setData(0, Qt.UserRole, str(path))
            item.setCheckState(0, Qt.Unchecked)
            self.table.addTopLevelItem(item)
            self.items[path] = item
        self.table.blockSignals(False)
        self.update_keepers()

    def keep(self):
        item = self.table.currentItem()
        if item:
            path = Path(item.data(0, Qt.UserRole))
            group = self.rows[path].group
            if group:
                self.keepers[group] = path
                self.update_keepers()

    def update_keepers(self):
        self.table.blockSignals(True)
        for path, item in self.items.items():
            keep = self.keepers.get(self.rows[path].group) == path
            item.setText(3, "Keep" if keep else "")
            if keep:
                item.setCheckState(0, Qt.Unchecked)
                item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            else:
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        self.table.blockSignals(False)
        self.summary()

    def selected(self):
        return [path for path, item in self.items.items() if item.checkState(0) == Qt.Checked]

    def summary(self, *_):
        selected = self.selected()
        self.status.setText(f"{len(selected)} selected · {format_size(estimated_bytes(self.rows, selected))} "
                            f"estimated after emptying Trash · {self.issues} duplicate check warnings")

    def trash(self):
        selected = self.selected()
        if not selected or QMessageBox.question(self, "Confirm cleanup",
                f"Move {len(selected)} checked files to system Trash?", QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No) != QMessageBox.Yes:
            return
        def finished(outcomes):
            self.changed = any(state == "Trashed" for _, state in outcomes)
            self.table.itemChanged.disconnect(self.summary)
            self.table.setHeaderLabels(("File", "Outcome", "", ""))
            self.show_rows(outcomes)
            self.controls.setEnabled(False)
            self.status.setText(f"{sum(state == 'Trashed' for _, state in outcomes)} of {len(selected)} trashed")
        keepers = dict(self.keepers)
        def apply(cancel):
            # Serialize FileMind instances that might have selected opposite keepers.
            with self.journal._session():
                return trash_selected(self.rows, selected, keepers,
                                      lambda path: QFile(str(path)).moveToTrash(), cancel)
        self.run_task(apply, finished)
