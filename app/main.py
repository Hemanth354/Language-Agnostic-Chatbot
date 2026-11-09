import os
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, Form, UploadFile, File, Query, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import (
    BASE_DIR, SUPPORTED_LANGUAGES, SPEECH_LANG_CODES,
    CIRCULAR_DIR
)
from app.database import (
    init_db, get_db, save_conversation, save_message,
    get_conversation_history, get_all_circulars, delete_circular
)
from app.translation_service import translation_service
from app.rag_service import rag_service
from app.llm_service import llm_service
from app.circular_parser import (
    seed_sample_circulars_if_empty, ingest_circular, extract_text_from_file
)
from app.faculty_service import faculty_service
from app.channels.whatsapp import verify_webhook as verify_wa, send_whatsapp_message
from app.channels.telegram import send_telegram_message

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

# Initialize app
app = FastAPI(
    title="Language Agnostic Campus Chatbot",
    description="SIH 2025 - Team TechTitans RGUKTN (SIH25104)",
    version="2.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and Templates
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Pydantic Schemas
class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    preferred_lang: Optional[str] = "auto"
    user_name: Optional[str] = "Student"
    channel: Optional[str] = "web"

class FacultyReplyRequest(BaseModel):
    ticket_id: str
    reply: str
    assigned_faculty: Optional[str] = "Faculty In-Charge"

# Startup event
@app.on_event("startup")
async def startup_event():
    init_db()
    seed_sample_circulars_if_empty()
    logger.info("Application started. Sample circulars and DB ready.")

# ================= PAGE ROUTES =================

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Main Student Chatbot UI with voice assistant & language selector."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "languages": SUPPORTED_LANGUAGES,
        "speech_codes": SPEECH_LANG_CODES
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Student Volunteer & Admin Circular Management Portal."""
    circulars = get_all_circulars()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "circulars": circulars
    })

@app.get("/faculty", response_class=HTMLResponse)
async def faculty_page(request: Request):
    """Faculty Escalation & Ticket Resolution Dashboard."""
    tickets = faculty_service.list_all_tickets()
    return templates.TemplateResponse("faculty.html", {
        "request": request,
        "tickets": tickets
    })

@app.get("/simulator", response_class=HTMLResponse)
async def simulator_page(request: Request):
    """WhatsApp & Telegram multi-channel interactive mobile simulator."""
    return templates.TemplateResponse("simulator.html", {
        "request": request,
        "languages": SUPPORTED_LANGUAGES
    })

# ================= API ROUTES =================

@app.get("/api/languages")
async def get_languages():
    return {
        "languages": SUPPORTED_LANGUAGES,
        "speech_codes": SPEECH_LANG_CODES
    }

@app.post("/api/chat")
async def process_chat(req: ChatRequest):
    """
    Core Pipeline:
    1. Language Detection & IndicTrans Translation to English
    2. LangChain-style History Retrieval
    3. MiniLM Embeddings & ChromaDB Semantic Search
    4. Gemma-2 LLM Reasoning & Toxicity/Sentiment Guardrail
    5. Automatic Faculty Redirection if confidence is low
    6. Translation back to Student's Native Language
    7. Persistent Logging to SQLite
    """
    raw_query = req.query.strip()
    if not raw_query:
        return JSONResponse({"error": "Empty query"}, status_code=400)

    conv_id = req.conversation_id or str(uuid.uuid4())
    user_name = req.user_name or "Student"
    pref_lang = req.preferred_lang or "auto"

    save_conversation(conv_id, user_name, pref_lang, req.channel or "web")

    # Step 1: IndicTrans translation layer to English
    translated_query, detected_lang = translation_service.translate_to_english(
        raw_query, user_selected_lang=pref_lang
    )
    lang_name = SUPPORTED_LANGUAGES.get(detected_lang, detected_lang)

    # Step 2: Conversational history
    history = get_conversation_history(conv_id, limit=5)

    # Step 3: Semantic circular search via MiniLM & ChromaDB
    relevant_chunks = rag_service.search(translated_query, top_k=3)

    # Step 4: Gemma2 LLM Answer generation + Moderation check
    llm_result = llm_service.generate_answer(translated_query, relevant_chunks, history)
    english_answer = llm_result["answer"]
    confidence = llm_result["confidence"]
    should_escalate = llm_result["escalate"]
    sources = llm_result.get("source_circulars", [])

    # Step 5: Auto-redirect to faculty if low confidence or unknown circular
    ticket_id = None
    if should_escalate or confidence < 0.35:
        escalation = faculty_service.escalate_query(
            conversation_id=conv_id,
            student_name=user_name,
            student_lang=detected_lang,
            original_query=raw_query,
            translated_query=translated_query,
            department="Academic / Examinations Section"
        )
        ticket_id = escalation["ticket_id"]
        english_answer += f" (Logged as Ticket #{ticket_id} for faculty review)."

    # Step 6: Translate back to student's native language
    translated_response = translation_service.translate_from_english(
        english_answer, target_lang=detected_lang
    )

    # Step 7: Store in SQL database
    save_message(
        conversation_id=conv_id,
        sender="bot",
        user_query=raw_query,
        detected_lang=detected_lang,
        translated_query=translated_query,
        response_text=english_answer,
        translated_response=translated_response,
        response_lang=detected_lang,
        confidence_score=confidence,
        is_escalated=should_escalate or (ticket_id is not None),
        ticket_id=ticket_id,
        metadata={"sources": sources}
    )

    return {
        "conversation_id": conv_id,
        "original_query": raw_query,
        "detected_lang": detected_lang,
        "language_name": lang_name,
        "translated_query": translated_query,
        "english_response": english_answer,
        "response": translated_response,
        "confidence": confidence,
        "is_escalated": bool(ticket_id),
        "ticket_id": ticket_id,
        "sources": sources,
        "speech_code": SPEECH_LANG_CODES.get(detected_lang, "en-IN")
    }

@app.get("/api/history/{conversation_id}")
async def get_history(conversation_id: str):
    messages = get_conversation_history(conversation_id)
    return {"conversation_id": conversation_id, "messages": messages}

# ================= CIRCULARS (VOLUNTEER PORTAL) =================

@app.get("/api/circulars")
async def list_circulars():
    return {"circulars": get_all_circulars()}

@app.post("/api/circulars/upload")
async def upload_circular(
    title: str = Form(...),
    circular_no: Optional[str] = Form(""),
    category: Optional[str] = Form("General"),
    issue_date: Optional[str] = Form(""),
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    extracted_text = content or ""
    filename = ""

    if file and file.filename:
        filename = file.filename
        dest_path = CIRCULAR_DIR / filename
        with open(dest_path, "wb") as f:
            f.write(await file.read())
        
        file_text = extract_text_from_file(dest_path)
        if file_text:
            extracted_text = (extracted_text + "\n\n" + file_text).strip() if extracted_text else file_text

    if not extracted_text:
        return JSONResponse({"error": "No content provided in file or text form."}, status_code=400)

    circ_id = ingest_circular(
        title=title,
        content=extracted_text,
        circular_no=circular_no or "RGUKTN-NOTICE",
        category=category or "General",
        issue_date=issue_date or "",
        file_name=filename,
        uploaded_by="Student Volunteer"
    )

    return {"message": "Circular successfully uploaded and indexed into ChromaDB/Vector store.", "id": circ_id}

@app.delete("/api/circulars/{circular_id}")
async def remove_circular(circular_id: int):
    delete_circular(circular_id)
    return {"message": f"Circular #{circular_id} deleted."}

# ================= FACULTY ESCALATION API =================

@app.get("/api/faculty/tickets")
async def get_tickets(status: Optional[str] = Query(None)):
    tickets = faculty_service.list_all_tickets(status)
    return {"tickets": tickets}

@app.get("/api/ticket/{ticket_id}")
async def check_ticket_status(ticket_id: str):
    """Lookup ticket status and response for students."""
    conn = get_db()
    cursor = conn.execute("SELECT * FROM faculty_tickets WHERE ticket_id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    if not ticket:
        return JSONResponse({"error": "Ticket not found"}, status_code=404)
    return {"ticket": dict(ticket)}

@app.post("/api/faculty/reply")
async def reply_ticket(data: FacultyReplyRequest):
    res = faculty_service.respond_to_ticket(
        ticket_id=data.ticket_id,
        faculty_reply=data.reply,
        assigned_faculty=data.assigned_faculty or "Faculty In-Charge"
    )
    return res

# ================= CHANNEL INTEGRATIONS (WHATSAPP & TELEGRAM) =================

@app.get("/api/whatsapp/webhook")
async def whatsapp_verify(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge")
):
    challenge = verify_wa(hub_mode, hub_token, hub_challenge)
    if challenge is not None:
        return Response(content=str(challenge), media_type="text/plain")
    return Response(content="Verification failed", status_code=status.HTTP_403_FORBIDDEN)

@app.post("/api/whatsapp/webhook")
async def whatsapp_incoming(request: Request):
    data = await request.json()
    try:
        entry = data.get("entry", [])[0]
        change = entry.get("changes", [])[0]["value"]
        messages = change.get("messages", [])
        if messages:
            msg = messages[0]
            from_num = msg.get("from")
            body = msg.get("text", {}).get("body", "")

            # Process through chatbot
            chat_req = ChatRequest(query=body, conversation_id=f"wa_{from_num}", channel="whatsapp")
            bot_resp = await process_chat(chat_req)

            # Reply to student on WhatsApp
            reply_text = bot_resp["response"]
            send_whatsapp_message(from_num, reply_text)
    except Exception as e:
        logger.error(f"WhatsApp webhook processing error: {e}")
    return {"status": "ok"}

@app.post("/api/telegram/webhook")
async def telegram_incoming(request: Request):
    data = await request.json()
    try:
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")

        if chat_id and text:
            chat_req = ChatRequest(query=text, conversation_id=f"tg_{chat_id}", channel="telegram")
            bot_resp = await process_chat(chat_req)

            # Reply to student on Telegram
            reply_text = f"*{bot_resp['response']}*\n\n_(Language: {bot_resp['language_name']})_"
            send_telegram_message(chat_id, reply_text)
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
    return {"status": "ok"}

