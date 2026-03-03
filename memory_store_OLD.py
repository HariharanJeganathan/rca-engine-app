import sqlite3
import json
import uuid
from datetime import datetime
from config import DB_NAME

class RCAStore:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                incident_type TEXT,
                status TEXT DEFAULT 'DRAFT',
                created_at TEXT,
                updated_at TEXT,
                whiteboard_text TEXT,
                mir_text TEXT,
                heading TEXT,
                probable_root_cause TEXT,
                rca_json TEXT,
                final_root_cause TEXT,
                corrective_actions TEXT,
                preventive_actions TEXT,
                is_change BOOLEAN DEFAULT 0,
                change_id TEXT,
                systems_affected TEXT,
                teams_involved TEXT
            )
        """)
        self.conn.commit()
    
    def save_incident(self, incident_id: str, incident_type: str, 
                      whiteboard_text: str, mir_text: str, rca_data: dict) -> str:
        rca_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        classification = rca_data.get("incident_classification", {})
        details = rca_data.get("incident_details", {})
        
        self.conn.execute("""
            INSERT INTO incidents (
                id, incident_id, incident_type, status, created_at, updated_at,
                whiteboard_text, mir_text, heading, probable_root_cause, rca_json,
                is_change, change_id, systems_affected, teams_involved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rca_id,
            incident_id,
            incident_type,
            'DRAFT',
            now,
            now,
            whiteboard_text,
            mir_text,
            rca_data.get("heading", ""),
            rca_data.get("probable_root_cause", ""),
            json.dumps(rca_data),
            classification.get("is_change", False),
            classification.get("change_id", ""),
            json.dumps(details.get("systems_affected", [])),
            json.dumps(details.get("teams_involved", []))
        ))
        
        self.conn.commit()
        return rca_id
    
    def update_rca(self, rca_id: str, rca_data: dict):
        now = datetime.utcnow().isoformat()
        
        self.conn.execute("""
            UPDATE incidents 
            SET heading=?, probable_root_cause=?, rca_json=?, updated_at=?
            WHERE id=?
        """, (
            rca_data.get("heading", ""),
            rca_data.get("probable_root_cause", ""),
            json.dumps(rca_data),
            now,
            rca_id
        ))
        
        self.conn.commit()
    
    def finalize(self, rca_id: str, final_data: dict):
        now = datetime.utcnow().isoformat()
        
        corrective = final_data.get("corrective_actions", [])
        preventive = final_data.get("preventive_actions", [])
        
        if isinstance(corrective, list):
            corrective = json.dumps(corrective)
        if isinstance(preventive, list):
            preventive = json.dumps(preventive)
        
        self.conn.execute("""
            UPDATE incidents 
            SET status='FINALIZED',
                final_root_cause=?,
                corrective_actions=?,
                preventive_actions=?,
                updated_at=?
            WHERE id=?
        """, (
            final_data.get("final_root_cause", ""),
            corrective,
            preventive,
            now,
            rca_id
        ))
        
        self.conn.commit()
    
    def get(self, rca_id: str):
        cur = self.conn.execute("SELECT * FROM incidents WHERE id=?", (rca_id,))
        return cur.fetchone()
    
    def list_all(self, limit: int = 100):
        cur = self.conn.execute(
            "SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?", 
            (limit,)
        )
        return cur.fetchall()
    
    def get_finalized(self, limit: int = None):
        query = "SELECT * FROM incidents WHERE status='FINALIZED' ORDER BY updated_at DESC"
        params = ()
        
        if limit:
            query += " LIMIT ?"
            params = (limit,)
        
        cur = self.conn.execute(query, params)
        return cur.fetchall()