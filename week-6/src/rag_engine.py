"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Module: Retrieval-Augmented Generation (RAG) & Grounded AI Assistant Engine
Focus: Semantic retrieval, strict grounding, multi-document synthesis, and negative-case handling
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import config
import database
import processor

logger = logging.getLogger("rag_engine")

NEGATIVE_FALLBACK_ANSWER = (
    "The available documents do not contain enough information to answer this question."
)

_VECTORIZER_CACHE = None
_CHUNKS_CACHE: List[Dict[str, Any]] = []
_MATRIX_CACHE = None


def index_document_for_rag(
    document_id: int,
    text: str,
    page_texts: Optional[List[str]] = None,
    db_path: Optional[str] = None
) -> int:
    """
    Chunks document text and persists chunks into SQLite database for semantic retrieval.
    Returns the count of chunks created.
    """
    global _VECTORIZER_CACHE, _CHUNKS_CACHE, _MATRIX_CACHE
    # Invalidate search cache
    _VECTORIZER_CACHE = None
    _CHUNKS_CACHE = []
    _MATRIX_CACHE = None

    chunks = processor.chunk_document_text(
        text=text,
        document_id=document_id,
        chunk_size=config.RAG_CHUNK_SIZE,
        chunk_overlap=config.RAG_CHUNK_OVERLAP,
        page_texts=page_texts
    )
    if not chunks:
        return 0

    inserted_count = database.insert_rag_chunks(chunks, db_path=db_path)
    logger.info(f"Indexed {inserted_count} RAG chunks for document #{document_id}.")
    return inserted_count


def _load_and_vectorize_all_chunks(db_path: Optional[str] = None):
    """Loads all chunks and builds TF-IDF vector matrix with caching."""
    global _VECTORIZER_CACHE, _CHUNKS_CACHE, _MATRIX_CACHE

    all_chunks = database.get_all_rag_chunks(db_path=db_path)
    if not all_chunks:
        _CHUNKS_CACHE = []
        _VECTORIZER_CACHE = None
        _MATRIX_CACHE = None
        return [], None, None

    corpus = [c["chunk_text"] for c in all_chunks]
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 3),
        stop_words="english",
        sublinear_tf=True,
        max_features=10000
    )
    try:
        matrix = vectorizer.fit_transform(corpus)
    except Exception as e:
        logger.warning(f"TF-IDF vectorizer fit error: {e}")
        return all_chunks, None, None

    _CHUNKS_CACHE = all_chunks
    _VECTORIZER_CACHE = vectorizer
    _MATRIX_CACHE = matrix

    return all_chunks, vectorizer, matrix


def retrieve_relevant_chunks(
    query: str,
    top_k: Optional[int] = None,
    document_id: Optional[int] = None,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Performs semantic vector retrieval against indexed document chunks.
    Filters by document_id if specified.
    Returns ranked chunks with similarity scores.
    """
    k = top_k or config.RAG_TOP_K
    chunks, vectorizer, matrix = _load_and_vectorize_all_chunks(db_path=db_path)
    if not chunks or vectorizer is None or matrix is None:
        return []

    # Optional document filter mask
    if document_id is not None:
        filtered_indices = [i for i, c in enumerate(chunks) if c["document_id"] == document_id]
        if not filtered_indices:
            return []
        sub_chunks = [chunks[i] for i in filtered_indices]
        sub_matrix = matrix[filtered_indices]
    else:
        sub_chunks = chunks
        sub_matrix = matrix

    try:
        query_vec = vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, sub_matrix)[0]
    except Exception as e:
        logger.warning(f"Error computing vector similarity: {e}")
        return []

    ranked_indices = np.argsort(similarities)[::-1]
    results: List[Dict[str, Any]] = []

    for idx in ranked_indices:
        score = float(similarities[idx])
        if score > 0.001:  # Non-zero relevance
            chunk_info = dict(sub_chunks[idx])
            chunk_info["similarity_score"] = round(score, 4)
            results.append(chunk_info)
            if len(results) >= k:
                break

    return results


def _extract_grounded_answer_offline(query: str, retrieved_chunks: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Robust offline deterministic extractor that synthesizes answers directly
    from retrieved text and builds precise citations.
    """
    query_clean = query.strip().lower()
    query_words = set(re.findall(r"\b\w{3,}\b", query_clean))

    citations: List[Dict[str, Any]] = []
    answered_sentences: List[str] = []
    used_doc_ids = set()

    # Match relevant sentences
    for chunk in retrieved_chunks:
        text = chunk["chunk_text"]
        doc_id = chunk["document_id"]
        filename = chunk.get("original_filename", f"Doc #{doc_id}")
        page = chunk.get("page_number", 1)
        score = chunk["similarity_score"]

        # Split chunk into sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", text) if s.strip()]
        matched_in_chunk = []

        for sent in sentences:
            sent_words = set(re.findall(r"\b\w{3,}\b", sent.lower()))
            overlap = query_words.intersection(sent_words)
            if overlap:
                matched_in_chunk.append((sent, len(overlap)))

        # Sort sentences by keyword overlap in this chunk
        matched_in_chunk.sort(key=lambda x: x[1], reverse=True)
        if matched_in_chunk:
            top_sent = matched_in_chunk[0][0]
            if top_sent not in answered_sentences:
                answered_sentences.append(top_sent)
                if doc_id not in used_doc_ids:
                    citations.append({
                        "document_id": doc_id,
                        "filename": filename,
                        "page_number": page,
                        "chunk_index": chunk.get("chunk_index", 0),
                        "relevance_percentage": f"{int(round(score * 100))}%",
                        "excerpt": top_sent[:180] + ("..." if len(top_sent) > 180 else "")
                    })
                    used_doc_ids.add(doc_id)

    if not answered_sentences:
        return NEGATIVE_FALLBACK_ANSWER, []

    # Format synthesized answer
    if len(citations) > 1:
        # Multi-document cross-reference answer
        lines = ["Here is the information found across multiple documents:"]
        for c in citations:
            lines.append(f"- **{c['filename']}** (Page {c['page_number']}): {c['excerpt']}")
        formatted_answer = "\n".join(lines)
    else:
        # Single document grounded answer
        main_text = " ".join(answered_sentences[:3])
        formatted_answer = f"{main_text}"

    return formatted_answer, citations


def answer_document_query(
    query: str,
    document_id: Optional[int] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main RAG Question Answering Endpoint:
    - Retrieves top matching semantic chunks
    - Enforces negative constraint: If documents lack sufficient info, returns
      exact message: "The available documents do not contain enough information to answer this question."
    - Synthesizes grounded answer with citations to source documents & pages.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return {
            "query": query,
            "success": False,
            "answer": "Please provide a valid question.",
            "citations": [],
            "retrieved_chunks_count": 0,
            "is_grounded": False,
            "reason": "EMPTY_QUERY"
        }

    top_chunks = retrieve_relevant_chunks(
        query=cleaned_query,
        top_k=config.RAG_TOP_K,
        document_id=document_id,
        db_path=db_path
    )

    # Negative Check: No chunks found or maximum similarity is too low
    if not top_chunks or top_chunks[0]["similarity_score"] < config.RAG_MIN_SIMILARITY_SCORE:
        logger.info(f"Query '{cleaned_query}' had low semantic similarity. Falling back to negative answer.")
        return {
            "query": query,
            "success": True,
            "answer": NEGATIVE_FALLBACK_ANSWER,
            "citations": [],
            "retrieved_chunks_count": len(top_chunks),
            "max_similarity": top_chunks[0]["similarity_score"] if top_chunks else 0.0,
            "is_grounded": True,
            "has_sufficient_information": False
        }

    # Extract answer and citations
    answer_text, citations = _extract_grounded_answer_offline(cleaned_query, top_chunks)

    # Negative Check: If extractor could not find relevant facts
    if answer_text == NEGATIVE_FALLBACK_ANSWER or not citations:
        return {
            "query": query,
            "success": True,
            "answer": NEGATIVE_FALLBACK_ANSWER,
            "citations": [],
            "retrieved_chunks_count": len(top_chunks),
            "max_similarity": top_chunks[0]["similarity_score"],
            "is_grounded": True,
            "has_sufficient_information": False
        }

    return {
        "query": query,
        "success": True,
        "answer": answer_text,
        "citations": citations,
        "retrieved_chunks_count": len(top_chunks),
        "max_similarity": top_chunks[0]["similarity_score"],
        "is_grounded": True,
        "has_sufficient_information": True
    }
