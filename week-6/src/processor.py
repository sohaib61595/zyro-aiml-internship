"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Module: Document Ingestion, OCR & Semantic Chunking Engine
Focus: Enterprise integration, security, optimization, and deployment readiness
"""

import os
import io
import re
import shutil
import logging
import unicodedata
from typing import Tuple, Dict, Any, List, Optional
from PIL import Image, ImageEnhance, ImageFilter, UnidentifiedImageError
import numpy as np

import config

logger = logging.getLogger("document_processor")

# ------------------------------------------------------------------------------
# 1. Dependency Discovery
# ------------------------------------------------------------------------------
try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    import pytesseract
    tesseract_candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    if not shutil.which("tesseract"):
        for cand in tesseract_candidates:
            if os.path.exists(cand):
                pytesseract.pytesseract.tesseract_cmd = cand
                break
except ImportError:
    pytesseract = None


def is_tesseract_available() -> bool:
    """Checks whether pytesseract and the Tesseract binary are executable."""
    if pytesseract is None:
        return False
    try:
        if not shutil.which("tesseract"):
            for cand in [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
            ]:
                if os.path.exists(cand):
                    pytesseract.pytesseract.tesseract_cmd = cand
                    break
        version = pytesseract.get_tesseract_version()
        return bool(version)
    except Exception:
        return False


# ------------------------------------------------------------------------------
# 2. Image Preprocessing & OCR
# ------------------------------------------------------------------------------

def preprocess_image_for_ocr(img: Image.Image) -> Image.Image:
    """
    Applies computer vision filters to optimize OCR accuracy:
    - Grayscale conversion
    - Contrast enhancement (2.0x)
    - Median filter for noise reduction
    - Otsu adaptive binarization
    """
    try:
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")
        
        gray = img.convert("L")
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)
        denoised = enhanced.filter(ImageFilter.MedianFilter(size=3))
        
        # Otsu thresholding via NumPy
        np_img = np.array(denoised)
        pixel_counts, bin_edges = np.histogram(np_img, bins=256, range=(0, 256))
        total_pixels = np_img.size
        current_max, threshold = 0.0, 128
        weight_bg, sum_bg = 0, 0
        total_sum = np.dot(np.arange(256), pixel_counts)

        for i in range(256):
            weight_bg += pixel_counts[i]
            if weight_bg == 0:
                continue
            weight_fg = total_pixels - weight_bg
            if weight_fg == 0:
                break
            sum_bg += i * pixel_counts[i]
            mean_bg = sum_bg / weight_bg
            mean_fg = (total_sum - sum_bg) / weight_fg
            var_between = weight_bg * weight_fg * ((mean_bg - mean_fg) ** 2)
            if var_between > current_max:
                current_max = var_between
                threshold = i

        binary = (np_img > threshold) * 255
        return Image.fromarray(binary.astype(np.uint8))
    except Exception as e:
        logger.warning(f"Error in OCR image preprocessing, returning fallback: {e}")
        return img


def run_ocr_on_image(img: Image.Image, apply_preprocessing: bool = True) -> str:
    """Runs pytesseract OCR with defensive fallback."""
    if not is_tesseract_available():
        logger.info("Tesseract binary not installed/available; OCR extraction skipped.")
        return ""
    try:
        proc_img = preprocess_image_for_ocr(img) if apply_preprocessing else img
        custom_config = r"--oem 3 --psm 6"
        extracted = pytesseract.image_to_string(proc_img, config=custom_config)
        return extracted.strip()
    except Exception as e:
        logger.warning(f"OCR invocation error: {e}")
        return ""


# ------------------------------------------------------------------------------
# 3. Text Normalization & Cleaning
# ------------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Cleans raw text:
    - Normalizes Unicode NFKC
    - Strips unprintable control characters
    - Condenses multiple horizontal spaces
    - Standardizes line breaks
    """
    if not text:
        return ""

    normalized = unicodedata.normalize("NFKC", text)
    filtered = "".join(
        ch for ch in normalized
        if unicodedata.category(ch)[0] != "C" or ch in ("\n", "\r", "\t")
    )
    # Condense horizontal spaces
    condensed = re.sub(r"[ \t]+", " ", filtered)
    # Condense excessive newlines (keep max 2 for paragraph separation)
    condensed = re.sub(r"\n{3,}", "\n\n", condensed)
    return condensed.strip()


# ------------------------------------------------------------------------------
# 4. Multi-Page Extraction & Pipeline Ingestion
# ------------------------------------------------------------------------------

def read_and_process_document(
    file_bytes: bytes,
    filename: str,
    apply_ocr_preprocessing: bool = True
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Universal ingestion handler for PDFs and Images:
    Returns (raw_text: str, cleaned_text: str, metadata: Dict[str, Any])
    """
    filename_lower = filename.lower()
    raw_text = ""
    pages_extracted = 0
    ocr_applied = False
    error_message: Optional[str] = None
    page_texts: List[str] = []

    try:
        if filename_lower.endswith(".pdf"):
            if fitz is None:
                raise ImportError("PyMuPDF (fitz) is not installed.")

            try:
                pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
            except Exception as e:
                return "", "", {
                    "pages": 0,
                    "ocr_applied": False,
                    "error": f"Corrupted or invalid PDF structure: {str(e)}",
                    "tesseract_available": is_tesseract_available(),
                    "page_texts": []
                }

            pages_extracted = len(pdf_doc)
            for page_idx in range(pages_extracted):
                page = pdf_doc[page_idx]
                p_text = page.get_text("text")
                page_texts.append(p_text)
                raw_text += p_text + "\n"

            # Scanned PDF Fallback: if digital text is empty or too sparse
            if len(clean_text(raw_text)) < config.MIN_TEXT_LENGTH_FOR_EXTRACTION:
                logger.info(f"Digital text sparse ({len(clean_text(raw_text))} chars). Triggering OCR on PDF pages...")
                ocr_text = ""
                ocr_page_texts = []
                for page_idx in range(pages_extracted):
                    page = pdf_doc[page_idx]
                    pix = page.get_pixmap(dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    p_ocr = run_ocr_on_image(img, apply_preprocessing=apply_ocr_preprocessing)
                    ocr_page_texts.append(p_ocr)
                    ocr_text += p_ocr + "\n"

                if len(clean_text(ocr_text)) > len(clean_text(raw_text)):
                    raw_text = ocr_text
                    page_texts = ocr_page_texts
                    ocr_applied = True
            pdf_doc.close()

        elif any(filename_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]):
            try:
                img = Image.open(io.BytesIO(file_bytes))
                raw_text = run_ocr_on_image(img, apply_preprocessing=apply_ocr_preprocessing)
                pages_extracted = 1
                ocr_applied = True
                page_texts.append(raw_text)
            except UnidentifiedImageError:
                return "", "", {
                    "pages": 0,
                    "ocr_applied": False,
                    "error": "Corrupted image file: Unable to identify image header.",
                    "tesseract_available": is_tesseract_available(),
                    "page_texts": []
                }
        else:
            return "", "", {
                "pages": 0,
                "ocr_applied": False,
                "error": f"Unsupported file type '{os.path.splitext(filename)[1]}'.",
                "tesseract_available": is_tesseract_available(),
                "page_texts": []
            }

    except Exception as e:
        logger.error(f"Unexpected document extraction failure on '{filename}': {e}")
        error_message = f"Processing Error: {str(e)}"

    cleaned = clean_text(raw_text)
    metadata = {
        "pages": pages_extracted,
        "ocr_applied": ocr_applied,
        "error": error_message,
        "raw_length": len(raw_text),
        "clean_length": len(cleaned),
        "tesseract_available": is_tesseract_available(),
        "page_texts": page_texts
    }
    return raw_text, cleaned, metadata


# ------------------------------------------------------------------------------
# 5. Semantic Chunking for RAG
# ------------------------------------------------------------------------------

def chunk_document_text(
    text: str,
    document_id: int,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    page_texts: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Splits document text into semantically coherent overlapping chunks.
    Preserves page boundaries and sentence structure.
    
    Returns list of dicts:
    [
        {
            "document_id": int,
            "chunk_index": int,
            "page_number": int,
            "chunk_text": str,
            "token_count": int
        },
        ...
    ]
    """
    size = chunk_size or config.RAG_CHUNK_SIZE
    overlap = chunk_overlap or config.RAG_CHUNK_OVERLAP

    chunks: List[Dict[str, Any]] = []
    chunk_counter = 0

    # If page texts are supplied, chunk per page for exact page attribution
    if page_texts and len(page_texts) > 0:
        for page_idx, p_text in enumerate(page_texts, 1):
            cleaned_p = clean_text(p_text)
            if not cleaned_p:
                continue

            # Split by paragraphs or sentences
            paragraphs = cleaned_p.split("\n\n")
            current_chunk = ""

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                if len(current_chunk) + len(para) + 1 <= size:
                    current_chunk = f"{current_chunk}\n{para}".strip()
                else:
                    if current_chunk:
                        chunks.append({
                            "document_id": document_id,
                            "chunk_index": chunk_counter,
                            "page_number": page_idx,
                            "chunk_text": current_chunk,
                            "token_count": len(current_chunk.split())
                        })
                        chunk_counter += 1
                    # Start new chunk with overlap if possible
                    if len(current_chunk) > overlap:
                        current_chunk = current_chunk[-overlap:] + " " + para
                    else:
                        current_chunk = para

            if current_chunk:
                chunks.append({
                    "document_id": document_id,
                    "chunk_index": chunk_counter,
                    "page_number": page_idx,
                    "chunk_text": current_chunk,
                    "token_count": len(current_chunk.split())
                })
                chunk_counter += 1
    else:
        # Fallback single-stream sliding window
        cleaned = clean_text(text)
        if not cleaned:
            return []

        step = max(size - overlap, 50)
        for i in range(0, len(cleaned), step):
            window = cleaned[i:i + size].strip()
            if window:
                chunks.append({
                    "document_id": document_id,
                    "chunk_index": chunk_counter,
                    "page_number": 1,
                    "chunk_text": window,
                    "token_count": len(window.split())
                })
                chunk_counter += 1

    return chunks
