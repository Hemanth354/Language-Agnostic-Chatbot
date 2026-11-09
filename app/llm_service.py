import os
import re
import json
import logging
from typing import List, Dict, Any, Optional

from app.config import GROQ_API_KEY, HUGGINGFACEHUB_API_TOKEN, LLM_MODEL_NAME

logger = logging.getLogger("llm_service")

# Keywords for detecting offensive, filthy, or abusive content (Slide 4 Guardrail)
TOXIC_KEYWORDS = {
    "abuse", "idiot", "stupid", "fuck", "bitch", "bastard", "asshole",
    "chutiya", "madarchod", "bhenchod", "gandu", "kamina", "donga", "lanja"
}

class LangChainGemmaService:
    """
    LLM reasoning service utilizing the LangChain framework with Google Gemma-2 models:
    - Primary: LangChain ChatGroq with 'gemma2-9b-it'
    - Secondary: LangChain HuggingFaceEndpoint / HuggingFacePipeline ('google/gemma-2-9b-it')
    - Fallback: LangChain ChatGoogleGenerativeAI or local heuristic extraction
    """
    def __init__(self):
        self.llm = None
        self._init_langchain_gemma()

    def _init_langchain_gemma(self):
        """Initializes Gemma model through LangChain."""
        # 1. Try LangChain ChatGroq (gemma2-9b-it)
        if GROQ_API_KEY:
            try:
                from langchain_groq import ChatGroq
                self.llm = ChatGroq(
                    api_key=GROQ_API_KEY,
                    model_name=LLM_MODEL_NAME, # gemma2-9b-it
                    temperature=0.2,
                    max_tokens=300
                )
                logger.info(f"LangChain ChatGroq initialized with model: {LLM_MODEL_NAME}")
                return
            except Exception as e:
                logger.warning(f"Could not initialize LangChain ChatGroq ({e}).")

        # 2. Try LangChain Hugging Face Endpoint for Gemma
        if HUGGINGFACEHUB_API_TOKEN:
            try:
                from langchain_community.llms import HuggingFaceEndpoint
                self.llm = HuggingFaceEndpoint(
                    repo_id=f"google/{LLM_MODEL_NAME}",
                    huggingfacehub_api_token=HUGGINGFACEHUB_API_TOKEN,
                    temperature=0.2,
                    max_new_tokens=300
                )
                logger.info(f"LangChain HuggingFaceEndpoint initialized with Gemma: google/{LLM_MODEL_NAME}")
                return
            except Exception as e:
                logger.warning(f"Could not initialize LangChain HuggingFace Gemma: {e}")

        logger.info("No external Groq or HuggingFace key provided. Utilizing built-in contextual extractor.")

    def check_content_safety(self, text: str) -> Dict[str, Any]:
        """Detects abusive or filthy queries using sentiment analysis (Slide 4)."""
        lowered = text.lower()
        words = set(re.findall(r"\w+", lowered))
        found_toxic = words.intersection(TOXIC_KEYWORDS)
        if found_toxic:
            return {
                "is_toxic": True,
                "reason": "Inappropriate content detected.",
                "warning_message": "Campus Bot Advisory: Please maintain academic decorum. Abusive or inappropriate queries are flagged and logged."
            }
        return {"is_toxic": False}

    def generate_answer(self, query: str, context_chunks: List[Dict[str, Any]], 
                        history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes LangChain chain with Gemma-2 to generate a concise, grounded response.
        """
        # Safety & Moderation check
        safety = self.check_content_safety(query)
        if safety["is_toxic"]:
            return {
                "answer": safety["warning_message"],
                "confidence": 0.0,
                "escalate": False,
                "source_circulars": []
            }

        # Check if context was found
        if not context_chunks or (context_chunks and context_chunks[0].get("score", 0) < 0.28):
            return {
                "answer": "This information is not explicitly mentioned in the recent college circulars. Your query has been automatically forwarded to the faculty/academic section for assistance.",
                "confidence": 0.2,
                "escalate": True,
                "source_circulars": []
            }

        # Format context & sources
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

        # Execute with LangChain Gemma LLM if available
        if self.llm:
            try:
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_core.output_parsers import StrOutputParser

                system_prompt = (
                    "You are the official Language Agnostic Campus AI Chatbot for Rajiv Gandhi University of Knowledge Technologies (RGUKT).\n"
                    "Your role is to assist students with queries regarding circulars, fee payments, exam schedules, scholarships, and hostel guidelines.\n"
                    "Instructions:\n"
                    "1. Answer concisely and accurately in 1 to 3 sentences based ONLY on the provided college circular context.\n"
                    "2. If the context contains specific dates (e.g. 30/09/2025), amounts, or deadlines, state them clearly.\n"
                    "3. If the context does not contain enough information, state that it will be redirected to faculty.\n"
                    "4. Maintain a polite, professional academic tone."
                )

                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", "{history}\n\nCollege Circular Context:\n{context}\n\nStudent Question:\n{question}\n\nAnswer:")
                ])

                chain = prompt | self.llm | StrOutputParser()
                answer = chain.invoke({
                    "history": history_text,
                    "context": formatted_context,
                    "question": query
                })

                return {
                    "answer": answer.strip(),
                    "confidence": context_chunks[0].get("score", 0.9),
                    "escalate": False,
                    "source_circulars": sources
                }
            except Exception as e:
                logger.warning(f"LangChain Gemma execution exception: {e}. Falling back to contextual extractor.")

        # Fallback Contextual Extractor (Runs offline / without API key)
        top_text = context_chunks[0].get("text", "")
        extracted_answer = self._extract_best_answer(query, top_text, context_chunks[0].get("title", ""))
        return {
            "answer": extracted_answer,
            "confidence": context_chunks[0].get("score", 0.8),
            "escalate": False,
            "source_circulars": sources
        }

    def _extract_best_answer(self, query: str, context: str, title: str) -> str:
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

# Singleton instance
llm_service = LangChainGemmaService()
