# Language Agnostic Chatbot 🎓
**Smart India Hackathon 2025 | Problem Statement ID: SIH25104**  
**Theme:** Smart Education | **Category:** Software  
**Team ID:** 55812 | **Team Name:** TEAM TECHTITANS_RGUKTN (RGUKT Nuzvid)

---

## 📌 Technology Stack Overview (As Specified)

This project is built using the exact architecture specified in the technical approach:

1. **Orchestration Framework:** **LangChain** (`langchain`, `langchain-core`, `langchain-community`, `langchain-groq`, `langchain-chroma`)
   - History-aware conversation chains (`ChatPromptTemplate`, message memory, vector retriever chaining).
2. **Language Translation:** **IndicTrans Hugging Face Model** (`ai4bharat/indictrans2-indic-en-1B` & `ai4bharat/indictrans2-en-indic-1B`)
   - Translates between 22 Scheduled Indian languages and English with script unification.
3. **Embeddings:** **`sentence-transformers/all-MiniLM-L6-v2`**
   - Embedded via LangChain's `HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")`.
4. **Vector Database:** **ChromaDB**
   - Integrated via LangChain `Chroma` vector store for chunk storage and semantic similarity search.
5. **LLM:** **Google Gemma Model** (`gemma2-9b-it`)
   - Grounded RAG reasoning and summarization using LangChain `ChatGroq` / `HuggingFaceEndpoint`.
   - Sentiment and toxicity guardrails for abusive/filthy query rejection.
6. **Backend:** **FastAPI** (`fastapi`, `uvicorn`)
   - Asynchronous REST endpoints, circular ingestion, faculty escalation tickets, and multi-channel webhooks (WhatsApp & Telegram).
7. **Frontend & Voice:** Modern HTML5, CSS3, JavaScript (ES6) with **Web Speech API** (Speech-to-Text & Text-to-Speech).

---

## 📂 Project Architecture

```
agnostic_chatbot/
├── app/
│   ├── config.py                 # 22 Indian language codes, credentials, and settings
│   ├── database.py               # SQLite schema (conversations, circulars, faculty tickets)
│   ├── translation_service.py    # IndicTrans (Hugging Face) translation layer
│   ├── rag_service.py            # LangChain + all-MiniLM-L6-v2 + ChromaDB
│   ├── llm_service.py            # LangChain + Gemma-2 LLM reasoning & moderation
│   ├── circular_parser.py        # PDF/Text parser & pre-seeded RGUKT official circulars
│   ├── faculty_service.py        # Human-in-the-loop auto-redirection & faculty replies
│   ├── channels/
│   │   ├── whatsapp.py           # WhatsApp Business Cloud API & Webhook handler
│   │   └── telegram.py           # Telegram Bot API & Webhook handler
│   └── main.py                   # FastAPI REST APIs and UI route controller
├── static/
│   ├── css/style.css             # Modern responsive campus UI with glassmorphism
│   └── js/
│       ├── app.js                # Chat interface, Speech-to-Text & Text-to-Speech
│       └── admin.js              # Circular upload & index controller
├── templates/
│   ├── index.html                # Main Student Helpline UI (Voice + Text + FAQs)
│   ├── admin.html                # Volunteer & Admin Circulars Knowledge Base Portal
│   ├── faculty.html              # Faculty Escalation & Query Resolution Dashboard
│   └── simulator.html            # WhatsApp & Telegram Multi-channel Live Simulator
├── data/
│   └── circulars/                # Sample college circulars (Fee, Calendar, Hostel, Scholarship)
├── run.py                        # Single-command launcher
├── test_app.py                   # Automated pipeline verification script
├── requirements.txt              # Project dependencies
├── .env.example                  # Environment configuration template
└── README.md                     # Documentation & SIH presentation alignment
```

---

## 🚀 Quickstart & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables (Optional)
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
Key configuration settings:
- `GROQ_API_KEY`: For fast cloud inference with `gemma2-9b-it`.
- `HUGGINGFACEHUB_API_TOKEN`: For Hugging Face IndicTrans models (`ai4bharat/indictrans2-indic-en-1B`).
- *Note: The system also includes an offline heuristic extractor and fallback translator that operates without requiring any external API keys.*

### 3. Run Verification Pipeline
```bash
python test_app.py
```

### 4. Start the FastAPI Server
```bash
python run.py
```
Or via batch script:
```bash
start.bat
```

---

## 🌐 Application Endpoints

- 🎓 **Student Chatbot UI:** [http://localhost:8000/](http://localhost:8000/)
- 📤 **Volunteer Circulars Portal:** [http://localhost:8000/admin](http://localhost:8000/admin)
- 👨‍🏫 **Faculty Escalation Desk:** [http://localhost:8000/faculty](http://localhost:8000/faculty)
- 📱 **WhatsApp & Telegram Simulator:** [http://localhost:8000/simulator](http://localhost:8000/simulator)
- 📑 **FastAPI Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Verified Test Scenarios (From Presentation)

1. **Telugu Query (Fee Payment Last Date):**
   - Input: `ఫీజు చెల్లించడానికి చివరి తేదీ ఎప్పుడు?`
   - IndicTrans Translation: `When is the last date to pay the fee?`
   - LangChain all-MiniLM-L6-v2 Retrieval: Matched `RGUKTN/ACAD/2025/EXAM-04`
   - Gemma Answer: `The last date to pay the semester examination fee is 30/09/2025.`
   - IndicTrans Output in Telugu: `గడువు తేదీ 30/09/2025.`
   - Voice Output: Speaks the response aloud in Telugu.

2. **Hinglish Query (Academic Timetable):**
   - Input: `Time table kab tak aega?`
   - Answer: `Mid-terms and End-terms time table will be published 2 weeks prior on the campus student portal notice board.`

3. **Faculty Escalation (Unanswered / Complex Query):**
   - Input: `Can I change my branch from ECE to CSE in 2nd year?`
   - Result: Low confidence in circulars -> **Auto-redirected to Faculty** under Ticket ID `#TICK-YYYYMMDD-XXXX`.
   - Faculty answers on [http://localhost:8000/faculty](http://localhost:8000/faculty) in English; the response is automatically translated back to the student's native language.

4. **Sentiment & Abuse Guardrail (Slide 4):**
   - Detects offensive/filthy queries and rejects them with a polite academic warning.
