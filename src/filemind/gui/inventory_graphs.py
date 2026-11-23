"""Interactive views of a completed inventory's category totals."""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QBoxLayout, QButtonGroup, QHeaderView, QHBoxLayout, QLabel,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from filemind.gui.components import FeedbackButton, SurfaceCard, divider, reveal
from filemind.gui.file_model import format_size
from filemind.gui.motion import ScanProgress
from filemind.gui.theme import ACTIVE, TEXT, TRACK


COLORS = (
    ACTIVE, "#499d7e", "#34705c", "#426455", "#72b9a4", "#87acd1",
    "#c5aa78", "#a18ac5", "#6ba5a4", "#c98780", "#83a374", "#aab1d4",
)


class CategoryChart(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(208, 196)
        self.setMaximumSize(405, 196)
        self.entries = []
        self.mode = "Donut"
        self.total_label = ""
        self.setAccessibleName("Category chart")

    def paintEvent(self, event):
        if not self.entries:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(4, 2, -4, -2)
        if self.mode == "Donut":
            self._draw_donut(painter, bounds)
        elif self.mode == "Bar":
            self._draw_bars(painter, bounds)
        else:
            self._draw_treemap(painter, bounds, self.entries)

    def _draw_donut(self, painter, bounds):
        total = sum(value for _, value, _ in self.entries)
        diameter = min(bounds.width(), bounds.height()) - 2
        ring = QRectF(0, 0, diameter - 27, diameter - 27)
        ring.moveCenter(bounds.center())
        angle = 90 * 16
        accumulated = 0
        for _, value, color in self.entries:
            accumulated += value
            end = 90 * 16 - round(accumulated / total * 360 * 16)
            pen = QPen(QColor(color), 27)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            painter.setPen(pen)
            span = angle - end
            gap = min(9, span // 3) if len(self.entries) > 1 else 0
            painter.drawArc(ring, angle - gap, gap - span)
            angle = end
        font = painter.font()
        font.setPointSize(17)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(TEXT))
        painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, self.total_label)

    def _draw_bars(self, painter, bounds):
        step = min(34, bounds.height() / len(self.entries))
        top = bounds.center().y() - step * len(self.entries) / 2
        height = min(16.0, step * 0.60)
        largest = self.entries[0][1]
        painter.setPen(Qt.PenStyle.NoPen)
        for index, (_, value, color) in enumerate(self.entries):
            track = QRectF(bounds.left(), top + (index + 0.5) * step - height / 2,
                           bounds.width(), height)
            painter.setBrush(QColor(TRACK))
            painter.drawRoundedRect(track, height / 2, height / 2)
            track.setWidth(max(2.0, track.width() * value / largest))
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(track, height / 2, height / 2)

    def _draw_treemap(self, painter, bounds, entries):
        if len(entries) == 1:
            name, _, color = entries[0]
            tile = bounds.adjusted(0.75, 0.75, -0.75, -0.75)
            if tile.isEmpty():
                return
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(tile, 4, 4)
            if tile.height() >= 24 and tile.width() >= 44:
                painter.setPen(QColor("#081711" if QColor(color).lightness() > 110 else TEXT))
                label = painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight,
                                                         int(tile.width()) - 12)
                painter.drawText(tile.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter, label)
            return
        total = sum(value for _, value, _ in entries)
        split, first = 1, entries[0][1]
        while split < len(entries) - 1 and first + entries[split][1] / 2 < total / 2:
            first += entries[split][1]
            split += 1
        a, b = QRectF(bounds), QRectF(bounds)
        if bounds.width() >= bounds.height():
            a.setWidth(bounds.width() * first / total)
            b.setLeft(a.right())
        else:
            a.setHeight(bounds.height() * first / total)
            b.setTop(a.bottom())
        self._draw_treemap(painter, a, entries[:split])
        self._draw_treemap(painter, b, entries[split:])


class InventoryGraphs(SurfaceCard):
    def __init__(self):
        super().__init__()
        self.setObjectName("GraphsCard")
        self._totals = {}
        heading = QLabel("Graphs")
        heading.setObjectName("GraphTitle")
        self._heading = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._heading.addWidget(heading, 1)
        self._controls = QHBoxLayout()
        self._controls.setSpacing(11)
        self._metric = self._add_choices("Metric", ("Storage", "File count"), "Storage")
        self._controls.addWidget(divider(vertical=True))
        self._mode = self._add_choices("Chart type", ("Bar", "Donut", "Treemap"), "Donut")
        self._heading.addLayout(self._controls)
        self.content_layout.addLayout(self._heading)
        self.content_layout.addWidget(divider())

        self.canvas = CategoryChart()
        self.legend = QTreeWidget()
        self.legend.setObjectName("ChartLegend")
        self.legend.setAccessibleName("Chart categories and values")
        self.legend.setColumnCount(2)
        self.legend.setHeaderHidden(True)
        self.legend.setRootIsDecorated(False)
        self.legend.setUniformRowHeights(True)
        self.legend.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.legend.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.legend.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.legend.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.legend.setIconSize(QSize(20, 16))
        self.legend.setFixedWidth(253)
        chart = QWidget()
        chart_layout = QHBoxLayout(chart)
        chart_layout.setContentsMargins(0, 0, 20, 0)
        chart_layout.setSpacing(22)
        chart_layout.addStretch(1)
        chart_layout.addWidget(self.canvas, 4)
        chart_layout.addWidget(self.legend, 0, Qt.AlignmentFlag.AlignVCenter)
        chart_layout.addStretch(1)

        self.insight = QLabel()
        self.insight.setObjectName("ChartInsight")
        self.insight.setWordWrap(True)
        self.insight.setTextFormat(Qt.TextFormat.PlainText)
        self.share = ScanProgress(width=None, height=19)
        self.share.setAccessibleName("Largest category share")
        insight = QWidget()
        insight_layout = QVBoxLayout(insight)
        insight_layout.setContentsMargins(25, 27, 15, 4)
        insight_layout.setSpacing(14)
        insight_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        insight_layout.addWidget(self.insight)
        insight_layout.addWidget(self.share)

        self.empty = QLabel()
        self.empty.setObjectName("MutedText")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setMinimumHeight(196)
        self.content_layout.addWidget(self.empty)
        self._body = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._body.setSpacing(16)
        self._body.addWidget(chart, 8)
        self._separator = divider(vertical=True)
        self._body.addWidget(self._separator)
        self._body.addWidget(insight, 3)
        self.content_layout.addLayout(self._body)
        self._body_widgets = chart, insight

    def _add_choices(self, label, choices, default):
        self._controls.addWidget(QLabel(label))
        group = QButtonGroup(self)
        segments = QWidget()
        segments.setObjectName("ChartSegments")
        row = QHBoxLayout(segments)
        row.setContentsMargins(1, 1, 1, 1)
        row.setSpacing(0)
        for choice in choices:
            button = FeedbackButton(choice)
            button.setCheckable(True)
            button.setChecked(choice == default)
            button.setObjectName("ChartSegment")
            group.addButton(button)
            row.addWidget(button)
        group.buttonClicked.connect(self._refresh)
        self._controls.addWidget(segments)
        return group

    def resizeEvent(self, event):
        super().resizeEvent(event)
        horizontal = QBoxLayout.Direction.LeftToRight
        vertical = QBoxLayout.Direction.TopToBottom
        self._heading.setDirection(horizontal if self.width() >= 710 else vertical)
        wide = self.width() >= 810
        self._body.setDirection(horizontal if wide else vertical)
        self._separator.setVisible(wide and bool(self.canvas.entries))

    def set_totals(self, totals):
        self._totals = totals
        self._refresh()

    def _refresh(self):
        storage = self._metric.checkedButton().text() == "Storage"
        metric_column = 1 if storage else 0
        format_value = format_size if storage else lambda value: f"{value:,}"
        rank = sorted(((name, values[metric_column]) for name, values in self._totals.items()
                       if values[metric_column]), key=lambda entry: (-entry[1], entry[0]))
        self.canvas.entries = [(name, value, COLORS[i % len(COLORS)])
                               for i, (name, value) in enumerate(rank)]
        self.canvas.mode = self._mode.checkedButton().text()
        self.canvas.setMaximumWidth(267 if self.canvas.mode == "Donut" else 405)
        total = sum(value for _, value in rank)
        self.canvas.total_label = format_value(total)
        self.canvas.setAccessibleDescription(f"{self.canvas.mode} chart, {self.canvas.total_label} "
                                             f"{'known storage' if storage else 'files'}")
        self.legend.clear()
        for name, value, color in self.canvas.entries:
            swatch = QPixmap(20, 14)
            swatch.fill(Qt.GlobalColor.transparent)
            painter = QPainter(swatch)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(swatch.rect(), 4, 4)
            painter.end()
            row = QTreeWidgetItem((name, format_value(value)))
            row.setIcon(0, QIcon(swatch))
            row.setSizeHint(0, QSize(0, 34))
            row.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.legend.addTopLevelItem(row)
        self.legend.setFixedHeight(min(196, 34 * len(rank) + 2))
        for widget in self._body_widgets:
            widget.setVisible(bool(rank))
        self._separator.setVisible(self.width() >= 810 and bool(rank))
        self.empty.setVisible(not rank)
        if rank:
            name, value = rank[0]
            share = value / total
            self.insight.setText(f"{name} uses {share:.0%} of\nscanned storage" if storage
                                 else f"{share:.0%} of scanned files\nare in {name}")
            if self.share.isHidden():
                self.share.begin(1000)
            self.share.report(round(share * 1000), 1000)
            self.canvas.update()
            reveal(self.canvas, 180, 0.45)
        else:
            self.empty.setText("No known storage to chart. Try File count." if storage
                               else "No files in the completed inventory.")
