from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt, pyqtProperty, pyqtSignal, pyqtSlot

from .file_model import format_size


@dataclass(slots=True)
class TransferItem:
    task_id: str
    name: str
    direction: str
    status: str = "Waiting"
    current: int = 0
    total: int = 0
    started_at: float = 0.0


class TransferModel(QAbstractListModel):
    countChanged = pyqtSignal()
    IdRole = Qt.ItemDataRole.UserRole + 1
    NameRole = Qt.ItemDataRole.UserRole + 2
    DirectionRole = Qt.ItemDataRole.UserRole + 3
    StatusRole = Qt.ItemDataRole.UserRole + 4
    ProgressRole = Qt.ItemDataRole.UserRole + 5
    DetailRole = Qt.ItemDataRole.UserRole + 6

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[TransferItem] = []

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.IdRole: b"taskId",
            self.NameRole: b"name",
            self.DirectionRole: b"direction",
            self.StatusRole: b"status",
            self.ProgressRole: b"progress",
            self.DetailRole: b"detail",
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    @pyqtProperty(int, notify=countChanged)
    def count(self) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        progress = item.current / item.total if item.total else 0.0
        elapsed = time.monotonic() - item.started_at if item.started_at else 0.0
        speed = format_size(int(item.current / elapsed)) + "/s" if elapsed > 0 else "0 B/s"
        return {
            self.IdRole: item.task_id,
            self.NameRole: item.name,
            self.DirectionRole: item.direction,
            self.StatusRole: item.status,
            self.ProgressRole: progress,
            self.DetailRole: (
                f"{format_size(item.current)} / {format_size(item.total)} · {speed}"
            ),
        }.get(role)

    def add(self, item: TransferItem) -> None:
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(item)
        self.endInsertRows()
        self.countChanged.emit()

    def update(
        self,
        task_id: str,
        *,
        current: int | None = None,
        total: int | None = None,
        status: str | None = None,
    ) -> None:
        for row, item in enumerate(self._items):
            if item.task_id != task_id:
                continue
            if current is not None:
                if current > 0 and not item.started_at:
                    item.started_at = time.monotonic()
                item.current = current
            if total is not None:
                item.total = total
            if status is not None:
                item.status = status
            index = self.index(row)
            self.dataChanged.emit(index, index, list(self.roleNames()))
            return

    @pyqtSlot()
    def clearFinished(self) -> None:
        active = {"Waiting", "Transferring", "Cancelling"}
        remaining = [item for item in self._items if item.status in active]
        self.beginResetModel()
        self._items = remaining
        self.endResetModel()
        self.countChanged.emit()
