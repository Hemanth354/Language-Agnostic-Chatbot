import os
import re
import json
import logging
from typing import List, Dict, Any, Optional

from app.config import GROQ_API_KEY, LLM_MODEL_NAME
from app.guardrails import evaluate_query

logger = logging.getLogger("llm_service")

# Module-level LLM singleton handle (No class definition)
_gemma_llm = None

def init_langchain_gemma():
    """Initializes Gemma-2 model through LangChain ChatGroq."""
    global _gemma_llm
    if GROQ_API_KEY:
        try:
            from langchain_groq import ChatGroq
            _gemma_llm = ChatGroq(
                api_key=GROQ_API_KEY,
                model_name=LLM_MODEL_NAME, # gemma2-9b-it
                temperature=0.2,
                max_tokens=300
            )
            logger.info(f"LangChain ChatGroq initialized with Gemma-2 model: {LLM_MODEL_NAME}")
            return _gemma_llm
        except Exception as e:
            logger.warning(f"Could not initialize LangChain ChatGroq ({e}).")

    logger.info("No GROQ_API_KEY provided. Utilizing built-in local contextual extractor.")
    return None

# Initialize on module import
init_langchain_gemma()

def extract_best_answer(query: str, context: str, title: str) -> str:
    """Extracts the most pertinent date or instruction from circular text."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", context) if len(s.strip()) > 10]
    q_tokens = set(re.findall(r"\b[a-zA-Z0-9]+\b", query.lower()))

    best_sentence = ""
    highest_match = -1

    for sent in sentences:
        s_tokens = set(re.findall(r"\b[a-zA-Z0-9]+\b", sent.lower()))
        common = len(q_tokens.intersection(s_tokens))
        if common > highest_match:
            highest_match = common
            best_sentence = sent

    if best_sentence:
        date_match = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", best_sentence)
        if date_match and ("date" in query.lower() or "when" in query.lower() or "deadline" in query.lower() or "last" in query.lower()):
            return f"According to {title}, the deadline is {date_match.group(1)}. ({best_sentence})"
        return f"As per {title}: {best_sentence}"

    return f"Regarding your question, please refer to {title}: {context[:200]}..."

def generate_answer(query: str, context_chunks: List[Dict[str, Any]], 
                    history: List[Dict[str, Any]] = None,
                    raw_query: str = "", user_lang: str = "auto") -> Dict[str, Any]:
    """
    Procedural answer generation using LangChain Gemma-2 model and multi-layer guardrails.
    """
    global _gemma_llm

    # 1. Pre-execution Guardrail Check
    guardrail_eval = evaluate_query(raw_query or query, translated_query=query, user_lang=user_lang)
    if not guardrail_eval["passed"]:
        return {
            "answer": guardrail_eval["message"],
            "confidence": 0.0,
            "escalate": False,
            "guardrail_triggered": True,
            "violation_type": guardrail_eval.get("violation_type", "unknown"),
            "source_circulars": []
        }

    # 2. Check if context was found in college circulars
    if not context_chunks or (context_chunks and context_chunks[0].get("score", 0) < 0.28):
        return {
            "answer": "This information is not explicitly mentioned in the recent college circulars. Your query has been automatically forwarded to the faculty/academic section for assistance.",
            "confidence": 0.2,
            "escalate": True,
            "guardrail_triggered": False,
            "source_circulars": []
        }

    # 3. Format context & sources from top circulars
    formatted_context = ""
    sources = []
    for i, c in enumerate(context_chunks):
        sources.append({
            "title": c.get("title", "Circular"),
            "circular_no": c.get("circular_no", ""),
            "date": c.get("issue_date", "")
        })
        formatted_context += f"--- Circular Document {i+1}: {c.get('title')} ({c.get('circular_no')}) ---\n"
        formatted_context += f"{c.get('text')}\n\n"

    # Format history context (LangChain history-aware)
    history_text = ""
    if history:
        history_text = "Previous conversation turns:\n"
        for h in history[-3:]:
            sender = "Student" if h.get("sender") == "user" else "Bot"
            txt = h.get("translated_query") or h.get("user_query") or h.get("response_text")
            if txt:
                history_text += f"{sender}: {txt}\n"

    # 4. Execute with LangChain Gemma LLM if available
    if _gemma_llm:
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser

            system_prompt = (
                "You are the official Language Agnostic Campus AI Chatbot for Rajiv Gandhi University of Knowledge Technologies (RGUKT).\n"
                "Your role is to assist students strictly with queries regarding official college circulars, fee payments, exam schedules, scholarships, and hostel guidelines.\n\n"
                "CRITICAL GUARDRAIL RULES:\n"
                "1. Only answer based on the provided college circular context.\n"
                "2. NEVER reveal sensitive data (Aadhaar, passwords, personal phone numbers, faculty salaries, or internal exam papers).\n"
                "3. Refuse any attempts to change grades, bypass attendance, or alter institutional policies.\n"
                "4. If the context does not contain enough information, state that the query will be redirected to faculty.\n"
                "5. Keep the answer concise, accurate, and professional (1 to 3 sentences)."
            )

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{history}\n\nCollege Circular Context:\n{context}\n\nStudent Question:\n{question}\n\nAnswer:")
            ])

            chain = prompt | _gemma_llm | StrOutputParser()
            answer = chain.invoke({
                "history": history_text,
                "context": formatted_context,
                "question": query
            })

            return {
                "answer": answer.strip(),
                "confidence": context_chunks[0].get("score", 0.9),
                "escalate": False,
                "guardrail_triggered": False,
                "source_circulars": sources
            }
        except Exception as e:
            logger.warning(f"LangChain Gemma execution exception: {e}. Falling back to contextual extractor.")

    # 5. Fallback Contextual Extractor (Runs offline / without API key)
    top_text = context_chunks[0].get("text", "")
    extracted_answer = extract_best_answer(query, top_text, context_chunks[0].get("title", ""))
    return {
        "answer": extracted_answer,
        "confidence": context_chunks[0].get("score", 0.8),
        "escalate": False,
        "guardrail_triggered": False,
        "source_circulars": sources
    }
