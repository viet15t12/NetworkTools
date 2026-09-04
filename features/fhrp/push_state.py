"""Apply successful FHRP worker results to SQLite."""

from __future__ import annotations

from contextlib import closing
from typing import Any


def apply_fhrp_success(db: Any, task: dict[str, Any]) -> None:
    """Advance only the member represented by a successful device task."""
    config = task["config"]
    member_id = int(config["member_id"])
    fhrp_id = int(config["fhrp_id"])
    with closing(db._connect()) as conn:
        with conn:
            if task.get("action") == "remove":
                conn.execute(
                    "DELETE FROM t08_fhrp_members WHERE member_id = ?;",
                    (member_id,),
                )
                remaining = conn.execute(
                    "SELECT 1 FROM t08_fhrp_members WHERE fhrp_id = ? LIMIT 1;",
                    (fhrp_id,),
                ).fetchone()
                if remaining is None:
                    conn.execute(
                        "DELETE FROM t08_fhrp_groups WHERE fhrp_id = ?;",
                        (fhrp_id,),
                    )
                return
            conn.execute(
                """
                UPDATE t08_fhrp_members
                SET sync_status = 'synchronized', delete_restore_status = NULL
                WHERE member_id = ?;
                """,
                (member_id,),
            )
            conn.execute(
                """
                UPDATE t08_fhrp_tracks
                SET sync_status = 'synchronized', delete_restore_status = NULL
                WHERE member_id = ? AND sync_status = 'pending_apply';
                """,
                (member_id,),
            )
