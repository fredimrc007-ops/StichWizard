"""Garnvorrat: welche Garne hast du zu Hause? Designs lassen sich dann mit einem Klick auf die
vorhandenen Farben umstellen (nächste Farbe nach Farbabstand im Lab-Raum)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout)

from . import icons, threads


def _key(chart, num, color):
    return f"{chart}|{num}|{color.upper()}"


def stock_colors(stock):
    """[(anzeigename, hex)] aus dem gespeicherten Vorrat."""
    out = []
    for it in stock or []:
        try:
            label = ((it.get("num") or "") + " " + (it.get("name") or "")).strip()
            out.append((f"{label} ({it.get('chart') or 'Standard'})", it["color"]))
        except (AttributeError, KeyError):
            continue
    return out


def nearest(hex_color, stock):
    """Nächstes Garn aus dem Vorrat: (eintrag, abstand) oder (None, None)."""
    if not stock:
        return None, None
    L = threads._lab(hex_color)
    best = min(stock, key=lambda it: sum((p - q) ** 2 for p, q in zip(threads._lab(it["color"]), L)))
    d = sum((p - q) ** 2 for p, q in zip(threads._lab(best["color"]), L)) ** 0.5
    return best, d


class ThreadStockDialog(QDialog):
    def __init__(self, stock, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mein Garnvorrat")
        self.resize(560, 640)
        self.stock = {_key(i.get("chart", ""), i.get("num", ""), i["color"]): dict(i)
                      for i in (stock or []) if isinstance(i, dict) and i.get("color")}
        v = QVBoxLayout(self)
        intro = QLabel("Hake die Garne an, die du besitzt. Danach kannst du jedes Design unten in "
                       "der Garnleiste mit »Anpassen ▾ › An meinen Garnvorrat« auf deine Garne "
                       "umstellen.")
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        v.addWidget(intro)
        row = QHBoxLayout()
        self.chart = QComboBox()
        self.chart.addItem("StichWizard-Standard", "")
        for n in threads.chart_names():
            self.chart.addItem(n, n)
        if threads.CURRENT_CHART:
            self.chart.setCurrentIndex(max(0, self.chart.findData(threads.CURRENT_CHART)))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen: Nummer oder Name …")
        self.only = QComboBox()
        self.only.addItems(["Alle Farben", "Nur mein Vorrat"])
        row.addWidget(self.chart, 2)
        row.addWidget(self.search, 2)
        row.addWidget(self.only, 1)
        v.addLayout(row)
        self.list = QListWidget()
        v.addWidget(self.list, 1)
        self.count = QLabel()
        v.addWidget(self.count)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        clear = QPushButton("Vorrat leeren")
        bb.addButton(clear, QDialogButtonBox.ResetRole)
        clear.clicked.connect(self._clear)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.chart.currentIndexChanged.connect(self._fill)
        self.search.textChanged.connect(self._fill)
        self.only.currentIndexChanged.connect(self._fill)
        self.list.itemChanged.connect(self._toggled)
        self._fill()

    def _rows(self):
        chart = self.chart.currentData()
        if chart:
            return [(chart, num, name, col) for name, num, col in threads.charts()[chart]]
        return [("", "", name, col) for name, col in threads.THREADS]

    def _fill(self, *_):
        q = self.search.text().strip().lower()
        only = self.only.currentIndex() == 1
        self.list.blockSignals(True)
        self.list.clear()
        if only:
            rows = [(i.get("chart", ""), i.get("num", ""), i.get("name", ""), i["color"])
                    for i in self.stock.values()]
        else:
            rows = self._rows()
        for chart, num, name, col in rows:
            label = (f"{num} " if num else "") + name + (f"   · {chart}" if only and chart else "")
            if q and q not in label.lower():
                continue
            it = QListWidgetItem(icons.swatch(col, 18), label)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            k = _key(chart, num, col)
            it.setData(Qt.UserRole, {"chart": chart, "num": num, "name": name, "color": col.upper()})
            it.setCheckState(Qt.Checked if k in self.stock else Qt.Unchecked)
            self.list.addItem(it)
        self.list.blockSignals(False)
        self._update_count()

    def _toggled(self, it):
        d = it.data(Qt.UserRole)
        k = _key(d["chart"], d["num"], d["color"])
        if it.checkState() == Qt.Checked:
            self.stock[k] = d
        else:
            self.stock.pop(k, None)
        self._update_count()

    def _clear(self):
        self.stock.clear()
        self._fill()

    def _update_count(self):
        self.count.setText(f"{len(self.stock)} Garne im Vorrat")

    def result_stock(self):
        return list(self.stock.values())
