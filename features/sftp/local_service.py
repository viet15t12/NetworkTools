from __future__ import annotations

from pathlib import Path

from .file_model import FileItem


class LocalFileService:
    @staticmethod
    def home_path() -> str:
        return str(Path.home())

    @staticmethod
    def normalize(path: str) -> str:
        return str(Path(path).expanduser().resolve())

    def list_directory(self, path: str) -> list[FileItem]:
        directory = Path(path).expanduser().resolve()
        if not directory.is_dir():
            raise NotADirectoryError(f"Local directory does not exist: {directory}")
        items: list[FileItem] = []
        for entry in directory.iterdir():
            try:
                is_directory = entry.is_dir()
                info = entry.stat()
            except OSError:
                is_directory = False
                info = None
            items.append(
                FileItem(
                    name=entry.name,
                    path=str(entry),
                    is_directory=is_directory,
                    size=None if is_directory or info is None else info.st_size,
                    modified_time=info.st_mtime if info is not None else 0,
                )
            )
        return sorted(items, key=lambda item: (not item.is_directory, item.name.casefold()))

    @staticmethod
    def create_directory(parent: str, name: str) -> None:
        Path(parent, name).mkdir()

    @staticmethod
    def rename(path: str, new_name: str) -> None:
        source = Path(path)
        source.rename(source.with_name(new_name))

    @staticmethod
    def delete(path: str) -> None:
        target = Path(path)
        if target.is_dir():
            # Deliberately refuse recursive deletion from the file-transfer UI.
            target.rmdir()
        else:
            target.unlink()

    @staticmethod
    def parent(path: str) -> str:
        current = Path(path).resolve()
        parent = current.parent
        return str(parent if parent != current else current)
