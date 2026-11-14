import os
import math
import re
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path

from app.config import CHROMA_DIR, EMBEDDING_MODEL_NAME
from app.database import get_all_chunks, save_chunks

logger = logging.getLogger("rag_service")

# Module-level handles (No class definition)
_embeddings = None
_vectorstore = None
_retriever = None

def init_langchain_components():
    """Initializes LangChain HuggingFaceEmbeddings and Chroma vector store procedurally."""
    global _embeddings, _vectorstore, _retriever

    # 1. Initialize LangChain HuggingFaceEmbeddings (all-MiniLM-L6-v2)
    try:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings

        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
        logger.info(f"LangChain HuggingFaceEmbeddings initialized: {EMBEDDING_MODEL_NAME}")
    except Exception as e:
        logger.warning(f"Could not load LangChain HuggingFaceEmbeddings ({e}). Using resilient fallback vectorizer.")
        _embeddings = None

    # 2. Initialize LangChain Chroma Vector Store
    try:
        try:
            from langchain_chroma import Chroma
        except ImportError:
            from langchain_community.vectorstores import Chroma

        if _embeddings:
            _vectorstore = Chroma(
                collection_name="campus_circulars",
                embedding_function=_embeddings,
                persist_directory=str(CHROMA_DIR)
            )
            _retriever = _vectorstore.as_retriever(search_kwargs={"k": 3})
            logger.info("LangChain Chroma vectorstore initialized successfully.")
    except Exception as e:
        logger.warning(f"ChromaDB initialization error: {e}. Falling back to SQLite vector search.")
        _vectorstore = None

# Initialize on import
init_langchain_components()

def fallback_embed(text: str, dim: int = 128) -> List[float]:
    """Procedural hash-based vectorizer for zero-dependency / offline mode."""
    vec = [0.0] * dim
    tokens = re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())
    if not tokens:
        return vec
    for token in tokens:
        h = hash(token) % dim
        vec[h] += 1.0
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Generates embeddings using LangChain all-MiniLM-L6-v2 embeddings."""
    global _embeddings
    if _embeddings and texts:
        try:
            return _embeddings.embed_documents(texts)
        except Exception as e:
            logger.error(f"LangChain embed error: {e}")

    return [fallback_embed(t) for t in texts]

def index_circular_chunks(circular_id: int, chunks: List[str], metadata: Dict[str, Any]):
    """Indexes documents into LangChain Chroma vectorstore and SQLite."""
    global _vectorstore
    if not chunks:
        return

    # 1. Add to LangChain Chroma Vector Store
    if _vectorstore:
        try:
            from langchain_core.documents import Document
            docs = [
                Document(
                    page_content=chunk,
                    metadata={
                        "circular_id": circular_id,
                        "title": metadata.get("title", ""),
                        "category": metadata.get("category", ""),
                        "circular_no": metadata.get("circular_no", ""),
                        "issue_date": metadata.get("issue_date", "")
                    }
                )
                for chunk in chunks
            ]
            _vectorstore.add_documents(docs)
            logger.info(f"[LangChain Chroma] Successfully added {len(docs)} documents.")
        except Exception as e:
            logger.warning(f"LangChain Chroma add_documents failed: {e}")

    # 2. Also store embeddings into SQLite for persistent backup
    embeddings = embed_texts(chunks)
    chunk_records = [{"text": chunk, "embedding": emb} for chunk, emb in zip(chunks, embeddings)]
    save_chunks(circular_id, chunk_records)

def search(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Retrieves top relevant circular chunks using LangChain similarity_search_with_relevance_scores.
    """
    global _vectorstore
    query = query.strip()
    if not query:
        return []

    # 1. Use LangChain Chroma Retriever if available
    if _vectorstore:
        try:
            results = _vectorstore.similarity_search_with_relevance_scores(query, k=top_k)
            matches = []
            for doc, score in results:
                matches.append({
                    "text": doc.page_content,
                    "title": doc.metadata.get("title", "Circular"),
                    "circular_no": doc.metadata.get("circular_no", ""),
                    "category": doc.metadata.get("category", ""),
                    "issue_date": doc.metadata.get("issue_date", ""),
                    "score": round(float(score), 3)
                })
            if matches:
                return matches
        except Exception as e:
            logger.debug(f"LangChain Chroma search error: {e}. Falling back to SQLite.")

    # 2. Fallback SQLite search with Cosine Similarity + BM25 keyword boosting
    all_chunks = get_all_chunks()
    if not all_chunks:
        return []

    q_vec = embed_texts([query])[0]
    q_tokens = set(re.findall(r"\b[a-zA-Z0-9]+\b", query.lower()))

    scored_chunks = []
    for ch in all_chunks:
        emb = ch.get("embedding", [])
        cos_sim = 0.0
        if emb and len(emb) == len(q_vec):
            dot = sum(a * b for a, b in zip(q_vec, emb))
            norm_a = math.sqrt(sum(a * a for a in q_vec))
            norm_b = math.sqrt(sum(b * b for b in emb))
            if norm_a > 0 and norm_b > 0:
                cos_sim = dot / (norm_a * norm_b)

        text_tokens = set(re.findall(r"\b[a-zA-Z0-9]+\b", ch["chunk_text"].lower()))
        overlap = len(q_tokens.intersection(text_tokens))
        kw_score = (overlap / len(q_tokens)) if q_tokens else 0.0

        final_score = round(0.6 * cos_sim + 0.4 * kw_score, 3)
        scored_chunks.append({
            "text": ch["chunk_text"],
            "title": ch.get("title", "Circular"),
            "circular_no": ch.get("circular_no", ""),
            "category": ch.get("category", ""),
            "issue_date": ch.get("issue_date", ""),
            "score": final_score
        })

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    return scored_chunks[:top_k]
