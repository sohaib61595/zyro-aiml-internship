"""
ZYROO INTERNSHIP PROGRAM - WEEK 3
Module: Text Cleaning and Normalization Engine
Step 2: Clean the Extracted Text

Features:
- Removes non-printable, unicode artifacts, zero-width chars, and non-breaking spaces.
- Normalizes quotation marks, em-dashes, bullets, and accents.
- Collapses irregular spaces and excessive blank lines while preserving document structure.
- Handles empty or very short extracted text safely with diagnostic feedback.
- Produces normalized tokens for ML classification without destroying raw case for entity regex.
"""

import re
import unicodedata
from typing import Dict, Any, Tuple


def clean_extracted_text(raw_text: str, keep_newlines: bool = True) -> str:
    """
    Cleans raw text extracted from PDFs or OCR engines.
    
    Args:
        raw_text: Messy text string directly from PDF parser or OCR engine.
        keep_newlines: If True, preserves line breaks (max 2 consecutive).
                       If False, collapses everything into a single line.
                       
    Returns:
        Cleaned, normalized text string.
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""

    # 1. Normalize Unicode (NFKC handles ligatures like 'fi', 'fl', and compatibility forms)
    text = unicodedata.normalize("NFKC", raw_text)

    # 2. Standardize Line Endings (\r\n or \r -> \n)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Replace non-breaking spaces and zero-width artifacts
    text = text.replace("\xa0", " ")
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)

    # 4. Normalize quotes, apostrophes, dashes, and bullets
    text = re.sub(r"[\u2018\u2019\u201A\u201B]", "'", text)
    text = re.sub(r"[\u201C\u201D\u201E\u201F]", '"', text)
    text = re.sub(r"[\u2013\u2014\u2015]", "-", text)
    text = re.sub(r"[•▪►■●★✦]", "-", text)

    # 5. Remove unprintable control characters (except newline \n and tab \t)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    # 6. Process line-by-line: trim whitespace from each line and collapse internal spaces
    lines = text.split("\n")
    processed_lines = []
    for line in lines:
        # Replace tabs and multiple spaces with a single space
        line = re.sub(r"[ \t]+", " ", line).strip()
        processed_lines.append(line)

    if keep_newlines:
        # Rejoin and collapse 3 or more consecutive blank lines down to 2
        joined = "\n".join(processed_lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", joined).strip()
    else:
        # Join into single space-separated string
        cleaned = " ".join(line for line in processed_lines if line).strip()

    return cleaned


def normalize_for_classification(text: str) -> str:
    """
    Produces a lowercased, noise-filtered representation of cleaned text
    specifically optimized for TF-IDF feature extraction.
    """
    if not text:
        return ""
    
    # Lowercase
    norm = text.lower()
    # Replace email addresses and URLs with generic tokens or spaces
    norm = re.sub(r"[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+", " ", norm)
    norm = re.sub(r"https?://\S+|www\.\S+", " ", norm)
    # Replace punctuation and special symbols with spaces, preserving letters and numbers
    norm = re.sub(r"[^a-z0-9\s]", " ", norm)
    # Collapse multiple spaces
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm


def validate_text_quality(text: str, min_chars: int = 25) -> Dict[str, Any]:
    """
    Evaluates whether the extracted text is sufficient for reliable downstream processing.
    
    Returns:
        dict: {
            "is_valid": bool,
            "char_count": int,
            "word_count": int,
            "line_count": int,
            "status": "VALID" | "EMPTY" | "VERY_SHORT",
            "warning": str or None
        }
    """
    stripped = text.strip() if text else ""
    char_count = len(stripped)
    word_count = len(stripped.split())
    line_count = len([line for line in stripped.splitlines() if line.strip()])

    if char_count == 0:
        return {
            "is_valid": False,
            "char_count": 0,
            "word_count": 0,
            "line_count": 0,
            "status": "EMPTY",
            "warning": "No text could be extracted from this document. It may be a blank page or unreadable scan."
        }
    elif char_count < min_chars:
        return {
            "is_valid": False,
            "char_count": char_count,
            "word_count": word_count,
            "line_count": line_count,
            "status": "VERY_SHORT",
            "warning": f"Extracted text is very short ({char_count} chars). Scanned OCR preprocessing is recommended."
        }
    else:
        return {
            "is_valid": True,
            "char_count": char_count,
            "word_count": word_count,
            "line_count": line_count,
            "status": "VALID",
            "warning": None
        }


def get_cleaning_summary(raw: str, cleaned: str) -> Dict[str, Any]:
    """Provides comparative metrics between raw and cleaned text."""
    raw_chars = len(raw) if raw else 0
    clean_chars = len(cleaned) if cleaned else 0
    saved_chars = raw_chars - clean_chars
    reduction_pct = round((saved_chars / raw_chars * 100), 1) if raw_chars > 0 else 0.0

    return {
        "raw_characters": raw_chars,
        "cleaned_characters": clean_chars,
        "characters_removed": saved_chars,
        "reduction_percentage": f"{reduction_pct}%",
        "raw_lines": len(raw.splitlines()) if raw else 0,
        "cleaned_lines": len(cleaned.splitlines()) if cleaned else 0
    }
