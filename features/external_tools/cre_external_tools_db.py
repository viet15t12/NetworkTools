from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from pathlib import Path

DB_NAME = "external_tools.db"

class ExternalToolsDB:
    def __init__(self, db_path: str | Path = DB_NAME):
        self.db_path = Path(db_path)

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_database(self):
        """Tạo database và bảng apps nếu chưa tồn tại."""

        with closing(self.connect()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS apps (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    app         TEXT NOT NULL UNIQUE,
                    type        TEXT NOT NULL,
                    executable  TEXT NOT NULL,
                    arguments   TEXT DEFAULT '',
                    enabled     INTEGER DEFAULT 1,
                    description TEXT DEFAULT ''
                );
            """)
            conn.commit()

    def insert_app(
        self,
        app: str,
        app_type: str,
        executable: str,
        arguments: str = "",
        enabled: int = 1,
        description: str = "",
    ):
        """Thêm một ứng dụng."""

        with closing(self.connect()) as conn:
            conn.execute(
                """
                INSERT INTO apps
                (app, type, executable, arguments, enabled, description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    app,
                    app_type,
                    executable,
                    arguments,
                    enabled,
                    description,
                ),
            )
            conn.commit()

    def get_apps(self):
        """Lấy toàn bộ ứng dụng."""

        with closing(self.connect()) as conn:
            cur = conn.execute(
                "SELECT * FROM apps ORDER BY type, app"
            )
            return cur.fetchall()

    def get_apps_by_type(self, app_type: str):
        """Lấy ứng dụng theo loại."""

        with closing(self.connect()) as conn:
            cur = conn.execute(
                "SELECT * FROM apps WHERE type=? ORDER BY app",
                (app_type,),
            )
            return cur.fetchall()

    def delete_app(self, app: str):
        """Xóa ứng dụng."""

        with closing(self.connect()) as conn:
            conn.execute(
                "DELETE FROM apps WHERE app=?",
                (app,),
            )
            conn.commit()

    def update_path(self, app: str, executable: str):
        """Cập nhật đường dẫn."""

        with closing(self.connect()) as conn:
            conn.execute(
                """
                UPDATE apps
                SET executable=?
                WHERE app=?
                """,
                (executable, app),
            )
            conn.commit()

    def get_app(self, app: str):
        """Lấy một ứng dụng cụ thể."""
        with closing(self.connect()) as conn:
            cur = conn.execute(
                "SELECT * FROM apps WHERE app=?",
                (app,)
            )
            return cur.fetchone()

    def update_app(
        self,
        app: str,
        app_type: str,
        executable: str,
        arguments: str = "",
        enabled: int = 1,
        description: str = "",
    ):
        """Cập nhật toàn bộ thông tin ứng dụng."""
        with closing(self.connect()) as conn:
            conn.execute(
                """
                UPDATE apps
                SET type=?, executable=?, arguments=?, enabled=?, description=?
                WHERE app=?
                """,
                (app_type, executable, arguments, enabled, description, app)
            )
            conn.commit()
