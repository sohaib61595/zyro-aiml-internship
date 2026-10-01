"""
ZYROO INTERNSHIP PROGRAM - WEEK 5
Module: Document Ingestion, OCR & Text Processing Engine
Focus: Workflow automation, validation, review and auditability

Capabilities:
- PyMuPDF native digital PDF parsing with page extraction.
- Preprocessed OCR fallback for scanned PDFs and image files (PNG, JPG, JPEG).
- Image preprocessing: Grayscale conversion, contrast adjustment, Otsu binarization, median filtering.
- Text cleaning and Unicode NFKC normalization, newline condensation, and unprintable character stripping.
- Defensive handling for corrupted files, truncated bytes, encrypted PDFs, and missing OCR binaries.
"""

import os
import io
import re
import shutil
import logging
import unicodedata
from typing import Tuple, Dict, Any, Optional
from PIL import Image, ImageEnhance, ImageFilter, UnidentifiedImageError
import numpy as np

logger = logging.getLogger("document_processor")

# ------------------------------------------------------------------------------
# 1. Dependency Discovery (PyMuPDF & Tesseract)
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
    """Checks whether pytesseract and the Tesseract binary are available."""
    if pytesseract is None:
        return False
    try:
        if not shutil.which("tesseract"):
            tesseract_candidates = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
            ]
            for cand in tesseract_candidates:
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
    - Contrast enhancement
    - Median filter for noise reduction
    - Otsu adaptive binarization
    """
    try:
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")
        
        # Grayscale
        gray = img.convert("L")
        
        # Contrast Enhancement
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)
        
        # Median filter to remove salt-and-pepper noise
        denoised = enhanced.filter(ImageFilter.MedianFilter(size=3))
        
        # Otsu thresholding via NumPy
        np_img = np.array(denoised)
        hist, bin_edges = np.histogram(np_img.ravel(), bins=256, range=(0, 256))
        total = np_img.size
        current_max, threshold = 0.0, 128
        sum_total = np.dot(np.arange(256), hist)
        sum_back, weight_back = 0.0, 0
        
        for i in range(256):
            weight_back += hist[i]
            if weight_back == 0:
                continue
            weight_fore = total - weight_back
            if weight_fore == 0:
                break
            sum_back += i * hist[i]
            mean_back = sum_back / weight_back
            mean_fore = (sum_total - sum_back) / weight_fore
            var_between = weight_back * weight_fore * ((mean_back - mean_fore) ** 2)
            if var_between > current_max:
                current_max = var_between
                threshold = i
                
        binarized_np = np.where(np_img > threshold, 255, 0).astype(np.uint8)
        return Image.fromarray(binarized_np)
    except Exception as e:
        logger.warning(f"Image preprocessing warning: {e}. Falling back to original image.")
        return img


def run_ocr_on_image(img: Image.Image, apply_preprocessing: bool = True) -> str:
    """Runs pytesseract OCR on a PIL Image object with optional preprocessing."""
    if not is_tesseract_available():
        return ""
    try:
        target_img = preprocess_image_for_ocr(img) if apply_preprocessing else img
        custom_config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_string(target_img, config=custom_config)
        return text or ""
    except Exception as e:
        logger.warning(f"OCR execution failed: {e}")
        return ""


# ------------------------------------------------------------------------------
# 3. Text Cleaning & Normalization
# ------------------------------------------------------------------------------
def clean_text(raw_text: str) -> str:
    """
    Cleans raw text extracted from native PDF parsers or OCR engines.
    - Unicode NFKC normalization
    - Standardizes line breaks (\r\n -> \n)
    - Replaces non-breaking spaces and zero-width artifacts
    - Normalizes quotes, dashes, and bullet symbols
    - Removes unprintable control characters
    - Condenses excessive blank lines
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""

    # NFKC normalizes ligatures (e.g. 'fi' -> 'f' + 'i')
    text = unicodedata.normalize("NFKC", raw_text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)

    # Quotes, dashes, bullets
    text = re.sub(r"[\u2018\u2019\u201A\u201B]", "'", text)
    text = re.sub(r"[\u201C\u201D\u201E\u201F]", '"', text)
    text = re.sub(r"[\u2013\u2014\u2015]", "-", text)
    text = re.sub(r"[•▪►■●★✦]", "-", text)

    # Control characters (except newline \n and tab \t)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    # Line-by-line whitespace normalization
    lines = text.split("\n")
    cleaned_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]
    joined = "\n".join(cleaned_lines)
    return re.sub(r"\n{3,}", "\n\n", joined).strip()


# ------------------------------------------------------------------------------
# 4. Unified Processing Entrypoint
# ------------------------------------------------------------------------------
def read_and_process_document(
    file_bytes: bytes,
    filename: str,
    apply_ocr_preprocessing: bool = True
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Reads, parses, extracts, and normalizes text from a document.
    
    Returns:
        (raw_text, cleaned_text, metadata)
    """
    metadata: Dict[str, Any] = {
        "filename": filename,
        "method": "UNKNOWN",
        "page_count": 0,
        "ocr_applied": False,
        "preprocessed": apply_ocr_preprocessing,
        "error": None
    }

    if not file_bytes:
        metadata["error"] = "Empty file bytes."
        return "", "", metadata

    ext = os.path.splitext(filename)[1].lower()
    raw_text = ""

    # Case A: PDF Document
    if ext == ".pdf":
        if fitz is None:
            metadata["error"] = "PyMuPDF (fitz) is not installed."
            return "", "", metadata

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            metadata["page_count"] = len(doc)
            
            # 1. Attempt digital text extraction
            pdf_text_parts = []
            for page in doc:
                txt = page.get_text()
                if txt and txt.strip():
                    pdf_text_parts.append(txt)
            raw_text = "\n".join(pdf_text_parts).strip()
            
            # 2. Check if scanned / image-only PDF (text is too sparse)
            if len(raw_text) < 40 and is_tesseract_available():
                logger.info(f"PDF '{filename}' appears scanned. Running OCR on rendered pages.")
                ocr_parts = []
                for page in doc:
                    pix = page.get_pixmap(dpi=150)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    page_ocr = run_ocr_on_image(img, apply_preprocessing=apply_ocr_preprocessing)
                    if page_ocr:
                        ocr_parts.append(page_ocr)
                if ocr_parts:
                    raw_text = "\n".join(ocr_parts).strip()
                    metadata["ocr_applied"] = True
                    metadata["method"] = "PDF_OCR_FALLBACK"
                else:
                    metadata["method"] = "NATIVE_PDF"
            else:
                metadata["method"] = "NATIVE_PDF"
            doc.close()

        except Exception as e:
            logger.error(f"Error parsing PDF '{filename}': {e}")
            metadata["error"] = f"Corrupted or invalid PDF: {str(e)}"
            return "", "", metadata

    # Case B: Image Files (PNG, JPG, JPEG)
    elif ext in (".png", ".jpg", ".jpeg"):
        metadata["page_count"] = 1
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.verify()  # Verify image integrity
            img = Image.open(io.BytesIO(file_bytes))  # Re-open after verify
            
            if is_tesseract_available():
                raw_text = run_ocr_on_image(img, apply_preprocessing=apply_ocr_preprocessing)
                metadata["method"] = "IMAGE_OCR"
                metadata["ocr_applied"] = True
            else:
                metadata["error"] = "Tesseract OCR engine is not available for image reading."
                metadata["method"] = "IMAGE_OCR_UNAVAILABLE"
        except UnidentifiedImageError:
            metadata["error"] = "Unidentified or corrupted image format."
            return "", "", metadata
        except Exception as e:
            metadata["error"] = f"Failed to process image: {str(e)}"
            return "", "", metadata

    else:
        metadata["error"] = f"Unsupported file extension '{ext}'."
        return "", "", metadata

    cleaned_text = clean_text(raw_text)
    metadata["raw_char_count"] = len(raw_text)
    metadata["cleaned_char_count"] = len(cleaned_text)
    metadata["has_text"] = bool(cleaned_text.strip())

    return raw_text, cleaned_text, metadata
