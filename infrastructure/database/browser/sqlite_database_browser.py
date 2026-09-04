import sys
from pathlib import Path

from PyQt6.QtSql import QSqlDatabase, QSqlQuery, QSqlTableModel
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)


DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "device_network.db"


class SQLiteDatabaseBrowser(QMainWindow):
    def __init__(self, db_path=None):
        super().__init__()

        self.setWindowTitle("SQLite Database Browser")
        self.resize(1100, 650)

        self.db = None
        self.model = None
        self.connection_name = "sqlite_database_browser_connection"

        self.init_ui()
        if db_path:
            self.open_database_path(str(db_path))

    def init_ui(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: white;
                color: #222;
                font-size: 14px;
            }
            QPushButton {
                background-color: #f3f3f3;
                border: 1px solid #cccccc;
                padding: 7px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QListWidget {
                border: 1px solid #dddddd;
                border-radius: 6px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                background-color: #dbeafe;
                color: #111;
            }
            QTableView {
                border: 1px solid #dddddd;
                border-radius: 6px;
                gridline-color: #eeeeee;
                selection-background-color: #dbeafe;
                selection-color: #111;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #222;
                padding: 6px;
                border: 1px solid #dddddd;
                font-weight: bold;
            }
        """)

        self.btn_open = QPushButton("Open Database")
        self.btn_open.clicked.connect(self.open_database)

        self.lbl_db_path = QLabel("No database selected")

        self.table_list = QListWidget()
        self.table_list.currentTextChanged.connect(self.load_table)

        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)

        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Tables"))
        left_layout.addWidget(self.table_list)

        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Table Content"))
        right_layout.addWidget(self.table_view)

        content_layout = QHBoxLayout()
        content_layout.addWidget(left_panel, 1)
        content_layout.addWidget(right_panel, 4)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.btn_open)
        main_layout.addWidget(self.lbl_db_path)
        main_layout.addLayout(content_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def open_database(self):
        db_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open SQLite Database",
            "",
            "SQLite Database (*.db *.sqlite *.sqlite3);;All Files (*)",
        )
        if db_path:
            self.open_database_path(db_path)

    def open_database_path(self, db_path):
        self.close_database()

        self.db = QSqlDatabase.addDatabase("QSQLITE", self.connection_name)
        self.db.setDatabaseName(db_path)

        if not self.db.open():
            QMessageBox.critical(self, "Database Error", self.db.lastError().text())
            return

        self.lbl_db_path.setText(db_path)
        self.load_tables()

    def close_database(self):
        if self.db:
            self.table_view.setModel(None)
            self.model = None
            self.db.close()
            QSqlDatabase.removeDatabase(self.connection_name)
            self.db = None

    def load_tables(self):
        self.table_list.clear()

        query = QSqlQuery(self.db)
        query.exec("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
        """)

        while query.next():
            self.table_list.addItem(query.value(0))

        if self.table_list.count() > 0:
            self.table_list.setCurrentRow(0)

    def load_table(self, table_name):
        if not table_name or not self.db:
            return

        self.model = QSqlTableModel(db=self.db)
        self.model.setTable(table_name)
        self.model.select()

        self.table_view.setModel(self.model)
        self.table_view.resizeColumnsToContents()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    window = SQLiteDatabaseBrowser(db_path if db_path.exists() else None)
    window.show()
    sys.exit(app.exec())
