"""Точка входа SuperApp."""
import os
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt5")

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor

from core.app_controller import AppController
from core.logger import setup_logger


LIGHT_STYLESHEET = """
    QWidget { color: #111827; }
    QLabel { color: #111827; background: transparent; }
    QPushButton {
        color: #111827;
        background: #e5e7eb;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 6px 12px;
    }
    QPushButton:hover { background: #d1d5db; }
    QPushButton:pressed { background: #9ca3af; }
    QPushButton:checked { background: #2563eb; color: #ffffff; }
    QComboBox {
        color: #111827;
        background: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 4px 8px;
    }
    QComboBox QAbstractItemView {
        color: #111827;
        background: #ffffff;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
    }
    QDateEdit {
        color: #111827;
        background: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 4px 8px;
    }
    QLineEdit {
        color: #111827;
        background: #ffffff;
    }
    QMenuBar { background: #e5e7eb; color: #111827; }
    QMenuBar::item:selected { background: #2563eb; color: #ffffff; }
    QMenu { background: #ffffff; color: #111827; border: 1px solid #d1d5db; }
    QMenu::item:selected { background: #2563eb; color: #ffffff; }
    QMessageBox { background: #f9fafb; }
    QMessageBox QLabel { color: #111827; }
"""


def apply_light_theme(app: QApplication) -> None:
    """Принудительно светлая тема, независимо от системной."""
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#f3f4f6"))
    palette.setColor(QPalette.WindowText, QColor("#111827"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f9fafb"))
    palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipText, QColor("#111827"))
    palette.setColor(QPalette.Text, QColor("#111827"))
    palette.setColor(QPalette.Button, QColor("#e5e7eb"))
    palette.setColor(QPalette.ButtonText, QColor("#111827"))
    palette.setColor(QPalette.BrightText, QColor("#dc2626"))
    palette.setColor(QPalette.Link, QColor("#2563eb"))
    palette.setColor(QPalette.Highlight, QColor("#2563eb"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#9ca3af"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#9ca3af"))
    app.setPalette(palette)

    app.setStyleSheet(LIGHT_STYLESHEET)


def main() -> int:
    setup_logger()
    app = QApplication(sys.argv)
    app.setApplicationName("SuperApp")
    app.setOrganizationName("SuperApp")

    apply_light_theme(app)

    controller = AppController()
    controller.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())