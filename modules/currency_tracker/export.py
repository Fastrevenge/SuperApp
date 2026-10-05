"""Экспорт графиков и данных."""
from __future__ import annotations

from typing import Iterable, Tuple

import pyqtgraph as pg


def export_plot_png(plot_widget: pg.PlotWidget, filepath: str) -> None:
    exporter = pg.exporters.ImageExporter(plot_widget.plotItem)
    exporter.export(filepath)


def export_series_csv(
    filepath: str, columns: Iterable[Tuple[str, Iterable[float]]]
) -> None:
    import csv

    cols = list(columns)
    if not cols:
        raise ValueError("Нет данных для экспорта")

    length = len(list(cols[0][1]))
    for name, values in cols:
        if len(list(values)) != length:
            raise ValueError("Колонки разной длины")

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([name for name, _ in cols])
        col_values = [list(vals) for _, vals in cols]
        for i in range(length):
            writer.writerow([col_values[j][i] for j in range(len(cols))])