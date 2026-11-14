import logging
from typing import Dict, Any, List
from app.database import create_faculty_ticket, get_faculty_tickets, resolve_faculty_ticket, get_db
from app.translation_service import translate_from_english

logger = logging.getLogger("faculty_service")

def escalate_query(conversation_id: str, student_name: str, student_lang: str,
                    original_query: str, translated_query: str, 
                    department: str = "Academic Section",
                    student_contact: str = "") -> Dict[str, Any]:
    """Procedurally creates a ticket for faculty intervention when chatbot confidence is low."""
    ticket_id = create_faculty_ticket(
        conversation_id=conversation_id,
        student_name=student_name,
        student_lang=student_lang,
        original_query=original_query,
        translated_query=translated_query,
        department=department,
        student_contact=student_contact
    )
    logger.info(f"Escalated query to faculty. Ticket ID: {ticket_id}")
    return {
        "ticket_id": ticket_id,
        "department": department,
        "status": "Open",
        "message": f"Your query has been logged under Ticket ID #{ticket_id}. Faculty members from {department} will review and respond shortly."
    }

def respond_to_ticket(ticket_id: str, faculty_reply: str, assigned_faculty: str = "Faculty In-Charge") -> Dict[str, Any]:
    """Faculty resolves ticket with an answer, automatically translated to student's native language."""
    conn = get_db()
    cursor = conn.execute("SELECT * FROM faculty_tickets WHERE ticket_id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()

    if not ticket:
        return {"error": "Ticket not found"}

    ticket_dict = dict(ticket)
    student_lang = ticket_dict.get("student_lang", "en")

    # Translate reply back to student's native tongue
    translated_reply = translate_from_english(faculty_reply, student_lang)

    resolve_faculty_ticket(ticket_id, faculty_reply, translated_reply, assigned_faculty)

    return {
        "ticket_id": ticket_id,
        "faculty_reply": faculty_reply,
        "translated_reply": translated_reply,
        "student_lang": student_lang,
        "status": "Resolved"
    }

def list_all_tickets(status: str = None) -> List[Dict[str, Any]]:
    """Lists all tickets from database."""
    return get_faculty_tickets(status)
