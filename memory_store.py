import sqlite3
import json
import uuid
import os
from datetime import datetime
from config import DB_NAME


class RCAStore:
    def __init__(self):
        # Ensure directory exists (important for Azure /home path safety)
        db_directory = os.path.dirname(DB_NAME)
        if db_directory and not os.path.exists(db_directory):
            os.makedirs(db_directory, exist_ok=True)

        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                incident_type TEXT,
                status TEXT DEFAULT 'DRAFT',
                created_at TEXT,
                updated_at TEXT,
                heading TEXT,
                probable_root_cause TEXT,
                whiteboard_text TEXT,
                mir_text TEXT,
                rca_json TEXT,
                final_root_cause TEXT,
                corrective_actions TEXT,
                preventive_actions TEXT,
                finalized_at TEXT
            )
        """)
        self.conn.commit()

    def save_incident(
        self,
        incident_id: str,
        incident_type: str,
        rca_data: dict,
        whiteboard_text: str = "",
        mir_text: str = "",
        confirmed: bool = False
    ):
        rca_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        status = "CONFIRMED" if confirmed else "DRAFT"

        heading = rca_data.get("heading", "")
        probable_root_cause = rca_data.get("probable_root_cause", "")

        self.conn.execute("""
            INSERT INTO incidents (
                id,
                incident_id,
                incident_type,
                status,
                created_at,
                updated_at,
                heading,
                probable_root_cause,
                rca_json,
                whiteboard_text,
                mir_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rca_id,
            incident_id,
            incident_type,
            status,
            now,
            now,
            heading,
            probable_root_cause,
            json.dumps(rca_data),
            whiteboard_text,
            mir_text or ""
        ))

        self.conn.commit()
        return rca_id

    def update_with_mir(self, rca_id: str, rca_data: dict, mir_text: str):
        now = datetime.utcnow().isoformat()

        self.conn.execute("""
            UPDATE incidents
            SET rca_json = ?,
                mir_text = ?,
                heading = ?,
                probable_root_cause = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            json.dumps(rca_data),
            mir_text,
            rca_data.get("heading"),
            rca_data.get("probable_root_cause"),
            "FINAL",
            now,
            rca_id
        ))

        self.conn.commit()

    def finalize(self, rca_id: str, final_data: dict):
        now = datetime.utcnow().isoformat()

        self.conn.execute("""
            UPDATE incidents
            SET final_root_cause = ?,
                corrective_actions = ?,
                preventive_actions = ?,
                finalized_at = ?,
                status = 'ARCHIVED'
            WHERE id = ?
        """, (
            final_data.get("final_root_cause"),
            json.dumps(final_data.get("corrective_actions", [])),
            json.dumps(final_data.get("preventive_actions", [])),
            final_data.get("finalized_at", now),
            rca_id
        ))

        self.conn.commit()

    def update_rca(self, rca_id: str, rca_data: dict):
        now = datetime.utcnow().isoformat()

        self.conn.execute("""
            UPDATE incidents
            SET rca_json = ?, updated_at = ?
            WHERE id = ?
        """, (
            json.dumps(rca_data),
            now,
            rca_id
        ))

        self.conn.commit()

    def get(self, rca_id: str):
        cur = self.conn.execute(
            "SELECT * FROM incidents WHERE id = ?",
            (rca_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_by_incident_id(self, incident_id: str):
        cur = self.conn.execute("""
            SELECT * FROM incidents
            WHERE incident_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (incident_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_all(self):
        cur = self.conn.execute("""
            SELECT * FROM incidents
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def get_finalized(self):
        cur = self.conn.execute("""
            SELECT * FROM incidents
            WHERE status IN ('FINAL', 'ARCHIVED')
              AND final_root_cause IS NOT NULL
            ORDER BY finalized_at DESC
        """)
        rows = cur.fetchall()
        return [dict(row) for row in rows]