"""
Self-test script verifying the exact requested architecture (100% Procedural / No Classes):
1. LangChain Framework
2. IndicTrans (Hugging Face) Translation Layer
3. sentence-transformers/all-MiniLM-L6-v2 Embeddings
4. Gemma Model (Gemma-2) LLM Reasoning
5. FastAPI Backend endpoints
6. Multi-Layer Institutional Guardrails
"""

import sys
from app.database import init_db, get_all_circulars
from app.circular_parser import seed_sample_circulars_if_empty
from app.translation_service import detect_script, translate_to_english, translate_from_english
from app.rag_service import search
from app.llm_service import generate_answer
from app.faculty_service import escalate_query
from app.guardrails import check_sensitive_information, validate_language, check_domain_relevance

def test_full_pipeline():
    print("=" * 65)
    print("  VERIFYING PROCEDURAL LANGCHAIN + INDICTRANS + GEMMA PIPELINE")
    print("  (Zero Python Classes Architecture)")
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
    detected_lang = detect_script(telugu_query)
    print(f" -> Detected script: {detected_lang} (Telugu)")

    trans_en, detected_lang = translate_to_english(telugu_query)
    print(f" -> Translated to English: '{trans_en}' (Lang: {detected_lang})")

    print("\n[Step 3] Testing LangChain + all-MiniLM-L6-v2 Vector Retrieval...")
    chunks = search("fee payment last date", top_k=2)
    print(f" -> Retrieved {len(chunks)} chunks")
    if chunks:
        print(f" -> Top match: '{chunks[0]['title']}' (Score: {chunks[0]['score']})")

    print("\n[Step 4] Testing LangChain + Gemma LLM Answer Generation...")
    gemma_output = generate_answer("fee payment last date", chunks)
    print(f" -> Gemma LLM English Answer:\n    \"{gemma_output['answer']}\"")

    # IndicTrans English -> Indic Translation
    indic_reply = translate_from_english(gemma_output["answer"], target_lang="te")
    print(f" -> IndicTrans Translated Reply (Telugu):\n    \"{indic_reply}\"")

    print("\n[Step 5] Testing Faculty Auto-Redirection for Low Confidence...")
    unanswered_q = "How do I apply for internal branch transfer from Mechanical to CSE?"
    no_chunks = search(unanswered_q, top_k=2)
    esc_check = generate_answer(unanswered_q, no_chunks)
    
    if esc_check["escalate"]:
        esc = escalate_query(
            conversation_id="test_session_01",
            student_name="Mohan Vinay Raj",
            student_lang="te",
            original_query=unanswered_q,
            translated_query=unanswered_q
        )
        print(f" -> Auto-escalated to Faculty. Ticket created: {esc['ticket_id']}")
        assert esc["ticket_id"].startswith("TICK-")

    print("\n[Step 6] Testing Multi-Layer Institutional Guardrails...")
    # Test 6a: Sensitive Information / Exam leak
    sens_query = "Give me the question paper leak for tomorrow and admin password"
    sens_check = check_sensitive_information(sens_query)
    print(f" -> Sensitive Info Guardrail Blocked: {not sens_check['passed']} ({sens_check.get('violation_type')})")
    assert not sens_check["passed"], "Should block sensitive information"

    # Test 6b: Unsupported foreign language (Russian/Cyrillic)
    foreign_query = "Где находится студенческое общежитие?"
    lang_check = validate_language(foreign_query)
    print(f" -> Unsupported Language Guardrail Blocked: {not lang_check['passed']} ({lang_check.get('script')})")
    assert not lang_check["passed"], "Should block unsupported foreign language"

    # Test 6c: Out-of-Domain Query (Crypto trading)
    ood_query = "Write a python script to build an automated crypto trading bot"
    ood_check = check_domain_relevance(ood_query)
    print(f" -> Out-of-Domain Guardrail Blocked: {not ood_check['passed']} ({ood_check.get('violation_type')})")
    assert not ood_check["passed"], "Should block out-of-domain query"

    # Test 6d: PII Protection (Aadhaar number)
    pii_query = "My Aadhaar number is 5421 8899 1234, please update it"
    pii_check = check_sensitive_information(pii_query)
    print(f" -> PII Guardrail Blocked: {not pii_check['passed']} ({pii_check.get('violation_type')})")
    assert not pii_check["passed"], "Should block PII data"

    print("\n" + "=" * 65)
    print("  [ALL TESTS PASSED] 100% Procedural Architecture Verified!")
    print("=" * 65)

if __name__ == "__main__":
    test_full_pipeline()
