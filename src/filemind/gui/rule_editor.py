"""Edit ordered rules for one Organizer folder profile."""
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from filemind.organizer.rules import RULE_FIELDS, validate_rule


def edit_rules(parent, rules):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Organizer rules")
    dialog.resize(940, 360)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("First matching row wins. Empty conditions match all. "
                            "Use * in patterns and <year> for the modification year."))
    table = QTableWidget(0, len(RULE_FIELDS))
    table.setHorizontalHeaderLabels(("Rule name", "Extension", "Filename pattern", "Min age (days)",
                                     "Min bytes", "Source folder pattern", "Destination"))
    layout.addWidget(table)

    def insert(row, values):
        table.insertRow(row)
        for col, key in enumerate(RULE_FIELDS):
            table.setItem(row, col, QTableWidgetItem(values.get(key, "")))
        table.setCurrentCell(row, 0)

    def values(row):
        return {key: table.item(row, col).text().strip() for col, key in enumerate(RULE_FIELDS)}

    def reorder(offset):
        row = table.currentRow()
        if row >= 0 and 0 <= row + offset < table.rowCount():
            rule = values(row)
            table.removeRow(row)
            insert(row + offset, rule)

    for rule in rules:
        insert(table.rowCount(), rule)
    buttons = QHBoxLayout()
    layout.addLayout(buttons)
    for label, action in (("Add", lambda: insert(table.rowCount(), {})),
                          ("Remove", lambda: table.removeRow(table.currentRow())),
                          ("Up", lambda: reorder(-1)), ("Down", lambda: reorder(1))):
        button = QPushButton(label)
        button.clicked.connect(action)
        buttons.addWidget(button)
    controls = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
    layout.addWidget(controls)

    def save():
        try:
            for row in range(table.rowCount()):
                validate_rule(values(row))
        except ValueError as error:
            QMessageBox.warning(dialog, "Invalid rule", str(error))
            return
        dialog.accept()

    controls.accepted.connect(save)
    controls.rejected.connect(dialog.reject)
    if dialog.exec():
        return [values(row) for row in range(table.rowCount())]
