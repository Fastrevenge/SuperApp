"""Заглушки для модулей в разработке."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget


def create_placeholder(title: str, description: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setAlignment(Qt.AlignCenter)

    title_label = QLabel(title)
    title_label.setAlignment(Qt.AlignCenter)
    title_label.setStyleSheet(
        "font-size:24px; font-weight:700; color:#374151; margin-bottom:12px;"
    )

    desc_label = QLabel(description)
    desc_label.setAlignment(Qt.AlignCenter)
    desc_label.setStyleSheet("font-size:14px; color:#6b7280;")

    badge = QLabel("В разработке")
    badge.setAlignment(Qt.AlignCenter)
    badge.setStyleSheet(
        "background:#fef3c7; color:#92400e; padding:6px 14px; "
        "border-radius:12px; font-weight:600; margin-top:18px;"
    )

    layout.addWidget(title_label)
    layout.addWidget(desc_label)
    layout.addWidget(badge)
    return widget