from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from typing import Any

from ..common import log_db_error, normalize_host
from .common import (
    normalize_process,
    normalize_process_core,
    normalize_without_networks,
)
from .save_helpers import (
    archive_ospf_process,
    describe_process_submission,
    insert_ospf_process,
    is_blank_ospf_process_submission,
    load_process_for_compare,
    sync_ospf_networks,
)
from .validation import validate_ospf_processes


def save_ospf_routing(db: Any, host: str, payload: Any) -> bool:
    host = normalize_host(host)
    if not host:
        if hasattr(db, "_set_last_routing_error"):
            db._set_last_routing_error("Host is empty")
        return False

    try:
        process_values = db._as_list(payload)
        validate_ospf_processes(db, process_values)
        with closing(db._connect()) as conn:
            existing_ids = {
                row["ospf_id"]
                for row in conn.execute(
                    """
                    SELECT ospf_id
                    FROM t04_ospf_processes
                    WHERE host = ? AND sync_status != 'pending_delete';
                    """,
                    (host,),
                ).fetchall()
            }
            submitted_ids: set[int] = set()

            for index, process_value in enumerate(process_values, start=1):
                process = db._as_dict(process_value)
                if is_blank_ospf_process_submission(db, process):
                    continue
                ospf_id = db._int_or_none(process.get("ospf_id")) or 0
                process_id = db._int_or_none(process.get("process_id"))
                if process_id is None:
                    raise ValueError(
                        "OSPF process_id is required in "
                        + describe_process_submission(db, process, index)
                    )

                if ospf_id > 0 and ospf_id in existing_ids:
                    submitted_ids.add(ospf_id)
                    current = load_process_for_compare(conn, db, ospf_id)
                    if current is not None and normalize_process(db, current) == normalize_process(db, process):
                        continue

                    if (
                        current is not None
                        and normalize_process_core(current) == normalize_process_core(process)
                        and normalize_without_networks(db, current) == normalize_without_networks(db, process)
                    ):
                        sync_ospf_networks(conn, db, ospf_id, process)
                        continue

                    archive_ospf_process(conn, ospf_id)
                    saved_id = insert_ospf_process(conn, db, host, process)
                    if saved_id in existing_ids:
                        submitted_ids.add(saved_id)
                    continue

                saved_id = insert_ospf_process(conn, db, host, process)
                # Compatibility callers may identify a process only by its
                # process_id. If that row already exists, do not archive it as
                # "omitted" after the upsert.
                if saved_id in existing_ids:
                    submitted_ids.add(saved_id)

            for deleted_id in existing_ids - submitted_ids:
                archive_ospf_process(conn, deleted_id)

            conn.commit()
        if hasattr(db, "_set_last_routing_error"):
            db._set_last_routing_error("")
        return True
    except (sqlite3.Error, OverflowError, TypeError, ValueError) as exc:
        if hasattr(db, "_set_last_routing_error"):
            db._set_last_routing_error(str(exc))
        log_db_error("saveOspfRouting", exc)
        return False
