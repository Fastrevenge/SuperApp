"""Реестр модулей (утилит) SuperApp."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from PyQt5.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class BaseModule:
    """Базовый интерфейс утилиты SuperApp."""

    name: str = "Base"
    icon: str = ""

    def build_widget(self) -> QWidget:
        raise NotImplementedError

    def on_activate(self) -> None:
        pass

    def on_deactivate(self) -> None:
        pass


@dataclass
class RegisteredModule:
    key: str
    title: str
    icon: str
    factory: Callable[[], QWidget]
    widget: Optional[QWidget] = field(default=None)


class ModuleRegistry:
    def __init__(self) -> None:
        self._modules: List[RegisteredModule] = []

    def register(
        self,
        key: str,
        title: str,
        factory: Callable[[], QWidget],
        icon: str = "",
    ) -> None:
        if any(m.key == key for m in self._modules):
            raise ValueError("Модуль '{}' уже зарегистрирован".format(key))
        self._modules.append(
            RegisteredModule(key=key, title=title, icon=icon, factory=factory)
        )
        logger.info("Зарегистрирован модуль: %s (%s)", title, key)

    def all(self) -> List[RegisteredModule]:
        return list(self._modules)

    def get_widget(self, key: str) -> QWidget:
        for m in self._modules:
            if m.key == key:
                if m.widget is None:
                    m.widget = m.factory()
                return m.widget
        raise KeyError("Модуль '{}' не найден".format(key))