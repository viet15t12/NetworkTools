from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any

from ..common import log_db_error, normalize_host
from .common import normalize_process
from .save_key_chains import sync_eigrp_key_chains
from .save_processes import (
    CHILD_TABLES,
    archive_eigrp_process,
    insert_eigrp_process,
    load_process_for_compare,
    sync_eigrp_child_table,
    update_eigrp_process_row,
)


def save_eigrp_routing(db: Any, host: str, payload: Any) -> bool:
    host = normalize_host(host)
    if not host:
        return False

    try:
        with closing(db._connect()) as conn:
            existing_ids = {
                row["eigrp_id"]
                for row in conn.execute(
                    """
                    SELECT eigrp_id
                    FROM t04_eigrp_processes
                    WHERE host = ? AND sync_status != 'pending_delete';
                    """,
                    (host,),
                ).fetchall()
            }
            submitted_ids: set[int] = set()

            for process_value in db._as_list(payload):
                process = db._as_dict(process_value)
                eigrp_id = db._int_or_none(process.get("eigrp_id")) or 0
                as_number = db._int_or_none(process.get("as_number"))
                if as_number is None:
                    raise ValueError("EIGRP as_number is required")

                if eigrp_id > 0 and eigrp_id in existing_ids:
                    submitted_ids.add(eigrp_id)
                    current = load_process_for_compare(conn, db, eigrp_id)
                    if current is None:
                        insert_eigrp_process(conn, db, host, process)
                        continue

                    current_as_number = db._int_or_none(current.get("as_number"))
                    if current_as_number != as_number:
                        archive_eigrp_process(conn, eigrp_id)
                        insert_eigrp_process(conn, db, host, process)
                        continue

                    if normalize_process(db, current) != normalize_process(db, process):
                        update_eigrp_process_row(conn, db, eigrp_id, process)
                        for table in CHILD_TABLES:
                            sync_eigrp_child_table(conn, db, eigrp_id, process, table, replace_all=False)
                    else:
                        conn.execute("UPDATE t04_eigrp_processes SET sync_status = 'pending_apply' WHERE eigrp_id = ?;", (eigrp_id,))
                    continue

                insert_eigrp_process(conn, db, host, process)

            for deleted_id in existing_ids - submitted_ids:
                archive_eigrp_process(conn, deleted_id)

            sync_eigrp_key_chains(conn, db, host, payload)
            conn.commit()
        return True
    except (sqlite3.Error, ValueError) as exc:
        log_db_error("saveEigrpRouting", exc)
        return False
