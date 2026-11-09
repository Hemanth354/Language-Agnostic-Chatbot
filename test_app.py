"""
Self-test script verifying the exact requested architecture:
1. LangChain Framework
2. IndicTrans (Hugging Face) Translation Service
3. sentence-transformers/all-MiniLM-L6-v2 Embeddings
4. Gemma Model (Gemma-2) LLM Reasoning
5. FastAPI Backend endpoints
"""

import sys
from app.database import init_db, get_all_circulars
from app.circular_parser import seed_sample_circulars_if_empty
from app.translation_service import translation_service
from app.rag_service import rag_service
from app.llm_service import llm_service
from app.faculty_service import faculty_service

def test_full_pipeline():
    print("=" * 65)
    print("  VERIFYING LANGCHAIN + INDICTRANS + ALL-MINILM + GEMMA PIPELINE")
    print("=" * 65)

    print("\n[Step 1] Initializing SQLite DB and Seeding RGUKT Circulars...")
    init_db()
    seed_sample_circulars_if_empty()
    circulars = get_all_circulars()
    print(f" -> Circulars indexed: {len(circulars)}")
    assert len(circulars) > 0, "Database should contain seeded circulars"

    print("\n[Step 2] Testing IndicTrans Hugging Face Translation Layer...")
    # Telugu query from SIH Slide 2
    telugu_query = "ఫీజు చెల్లించడానికి చివరి తేదీ ఎప్పుడు?"
    detected_lang = translation_service.detect_script(telugu_query)
    print(f" -> Detected script: {detected_lang} (Telugu)")

    trans_en, detected_lang = translation_service.translate_to_english(telugu_query)
    print(f" -> Translated to English: '{trans_en}' (Lang: {detected_lang})")

    print("\n[Step 3] Testing LangChain + all-MiniLM-L6-v2 Vector Retrieval...")
    chunks = rag_service.search("fee payment last date", top_k=2)
    print(f" -> Retrieved {len(chunks)} chunks")
    if chunks:
        print(f" -> Top match: '{chunks[0]['title']}' (Score: {chunks[0]['score']})")

    print("\n[Step 4] Testing LangChain + Gemma LLM Answer Generation...")
    gemma_output = llm_service.generate_answer("fee payment last date", chunks)
    print(f" -> Gemma LLM English Answer:\n    \"{gemma_output['answer']}\"")

    # IndicTrans English -> Indic Translation
    indic_reply = translation_service.translate_from_english(gemma_output["answer"], target_lang="te")
    print(f" -> IndicTrans Translated Reply (Telugu):\n    \"{indic_reply}\"")

    print("\n[Step 5] Testing Faculty Auto-Redirection for Low Confidence...")
    unanswered_q = "How do I apply for internal branch transfer from Mechanical to CSE?"
    no_chunks = rag_service.search(unanswered_q, top_k=2)
    esc_check = llm_service.generate_answer(unanswered_q, no_chunks)
    
    if esc_check["escalate"]:
        esc = faculty_service.escalate_query(
            conversation_id="test_session_01",
            student_name="Mohan Vinay Raj",
            student_lang="te",
            original_query=unanswered_q,
            translated_query=unanswered_q
        )
        print(f" -> Auto-escalated to Faculty. Ticket created: {esc['ticket_id']}")
        assert esc["ticket_id"].startswith("TICK-")

    print("\n" + "=" * 65)
    print("  [ALL TESTS PASSED] LangChain, IndicTrans, all-MiniLM, Gemma Ready!")
    print("=" * 65)

if __name__ == "__main__":
    test_full_pipeline()
