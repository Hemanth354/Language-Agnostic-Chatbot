import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.config import DB_PATH

logger = logging.getLogger("database")

def get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db()
    with conn:
        # Conversations table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                user_name TEXT,
                preferred_lang TEXT DEFAULT 'auto',
                channel TEXT DEFAULT 'web',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Messages table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                sender TEXT NOT NULL, -- 'user', 'bot', 'faculty'
                user_query TEXT,
                detected_lang TEXT,
                translated_query TEXT,
                response_text TEXT,
                translated_response TEXT,
                response_lang TEXT,
                confidence_score REAL DEFAULT 1.0,
                is_escalated BOOLEAN DEFAULT 0,
                ticket_id TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)

        # Circulars table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS circulars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                circular_no TEXT,
                title TEXT NOT NULL,
                category TEXT DEFAULT 'General',
                issue_date TEXT,
                content TEXT NOT NULL,
                summary TEXT,
                file_name TEXT,
                uploaded_by TEXT DEFAULT 'Volunteer',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Circular Chunks for Vector/RAG retrieval
        conn.execute("""
            CREATE TABLE IF NOT EXISTS circular_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                circular_id INTEGER NOT NULL,
                chunk_index INTEGER,
                chunk_text TEXT NOT NULL,
                embedding_json TEXT,
                FOREIGN KEY (circular_id) REFERENCES circulars(id) ON DELETE CASCADE
            )
        """)

        # Faculty Redirect / Escalation Tickets
        conn.execute("""
            CREATE TABLE IF NOT EXISTS faculty_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT UNIQUE NOT NULL,
                conversation_id TEXT,
                student_name TEXT,
                student_contact TEXT,
                student_lang TEXT,
                original_query TEXT NOT NULL,
                translated_query TEXT NOT NULL,
                department TEXT DEFAULT 'Academic Section',
                priority TEXT DEFAULT 'Medium',
                status TEXT DEFAULT 'Open', -- 'Open', 'In Progress', 'Resolved'
                assigned_faculty TEXT,
                faculty_reply TEXT,
                translated_reply TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)

        # System Activity Logs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    conn.close()
    logger.info("Database initialized successfully.")

# Database helper functions

def save_conversation(conversation_id: str, user_name: str = "Student", preferred_lang: str = "auto", channel: str = "web"):
    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO conversations (id, user_name, preferred_lang, channel, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET 
                updated_at = CURRENT_TIMESTAMP,
                preferred_lang = excluded.preferred_lang
        """, (conversation_id, user_name, preferred_lang, channel))
    conn.close()

def save_message(conversation_id: str, sender: str, user_query: str, detected_lang: str,
                 translated_query: str, response_text: str, translated_response: str,
                 response_lang: str, confidence_score: float = 1.0, is_escalated: bool = False,
                 ticket_id: Optional[str] = None, metadata: Optional[Dict] = None) -> int:
    conn = get_db()
    meta_json = json.dumps(metadata) if metadata else "{}"
    with conn:
        cursor = conn.execute("""
            INSERT INTO messages (
                conversation_id, sender, user_query, detected_lang,
                translated_query, response_text, translated_response,
                response_lang, confidence_score, is_escalated, ticket_id, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conversation_id, sender, user_query, detected_lang,
            translated_query, response_text, translated_response,
            response_lang, confidence_score, 1 if is_escalated else 0, ticket_id, meta_json
        ))
        msg_id = cursor.lastrowid
    conn.close()
    return msg_id

def get_conversation_history(conversation_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.execute("""
        SELECT * FROM messages 
        WHERE conversation_id = ? 
        ORDER BY created_at ASC 
        LIMIT ?
    """, (conversation_id, limit))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def create_circular(title: str, content: str, circular_no: str = "", category: str = "General", 
                    issue_date: str = "", summary: str = "", file_name: str = "", 
                    uploaded_by: str = "Volunteer") -> int:
    conn = get_db()
    with conn:
        cursor = conn.execute("""
            INSERT INTO circulars (title, content, circular_no, category, issue_date, summary, file_name, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, content, circular_no, category, issue_date, summary, file_name, uploaded_by))
        circ_id = cursor.lastrowid
    conn.close()
    return circ_id

def get_all_circulars() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.execute("""
        SELECT c.*, COUNT(ch.id) as chunk_count 
        FROM circulars c
        LEFT JOIN circular_chunks ch ON c.id = ch.circular_id
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def delete_circular(circular_id: int):
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM circular_chunks WHERE circular_id = ?", (circular_id,))
        conn.execute("DELETE FROM circulars WHERE id = ?", (circular_id,))
    conn.close()

def save_chunks(circular_id: int, chunks: List[Dict[str, Any]]):
    conn = get_db()
    with conn:
        for idx, chunk in enumerate(chunks):
            embedding_json = json.dumps(chunk.get("embedding", []))
            conn.execute("""
                INSERT INTO circular_chunks (circular_id, chunk_index, chunk_text, embedding_json)
                VALUES (?, ?, ?, ?)
            """, (circular_id, idx, chunk["text"], embedding_json))
    conn.close()

def get_all_chunks() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.execute("""
        SELECT ch.id, ch.circular_id, ch.chunk_index, ch.chunk_text, ch.embedding_json,
               c.title, c.circular_no, c.category, c.issue_date
        FROM circular_chunks ch
        JOIN circulars c ON ch.circular_id = c.id
    """)
    rows = []
    for r in cursor.fetchall():
        row_dict = dict(r)
        if row_dict.get("embedding_json"):
            try:
                row_dict["embedding"] = json.loads(row_dict["embedding_json"])
            except Exception:
                row_dict["embedding"] = []
        rows.append(row_dict)
    conn.close()
    return rows

def create_faculty_ticket(conversation_id: str, student_name: str, student_lang: str,
                          original_query: str, translated_query: str, 
                          department: str = "Academic Section", priority: str = "Medium",
                          student_contact: str = "") -> str:
    import uuid
    ticket_id = f"TICK-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:5].upper()}"
    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO faculty_tickets (
                ticket_id, conversation_id, student_name, student_contact, student_lang,
                original_query, translated_query, department, priority, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open')
        """, (
            ticket_id, conversation_id, student_name, student_contact, student_lang,
            original_query, translated_query, department, priority
        ))
    conn.close()
    return ticket_id

def get_faculty_tickets(status: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db()
    if status:
        cursor = conn.execute("SELECT * FROM faculty_tickets WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        cursor = conn.execute("SELECT * FROM faculty_tickets ORDER BY created_at DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def resolve_faculty_ticket(ticket_id: str, faculty_reply: str, translated_reply: str, assigned_faculty: str = "Faculty In-Charge"):
    conn = get_db()
    with conn:
        conn.execute("""
            UPDATE faculty_tickets 
            SET faculty_reply = ?, 
                translated_reply = ?, 
                assigned_faculty = ?, 
                status = 'Resolved',
                resolved_at = CURRENT_TIMESTAMP
            WHERE ticket_id = ?
        """, (faculty_reply, translated_reply, assigned_faculty, ticket_id))
    conn.close()

def log_event(event_type: str, details: str):
    conn = get_db()
    with conn:
        conn.execute("INSERT INTO audit_logs (event_type, details) VALUES (?, ?)", (event_type, details))
    conn.close()

