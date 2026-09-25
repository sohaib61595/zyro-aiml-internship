"""
ZYROO INTERNSHIP PROGRAM - WEEK 4
Module: OCR & Document Ingestion Engine with Defensive Error Handling
Tasks: Task 8 (Safer Error Handling: unreadable PDFs/images, OCR failure resilience)

Capabilities:
- PyMuPDF native digital text extraction with page tracking.
- Preprocessed OCR for scanned PDFs & camera images (contrast enhancement, Otsu binarization, median denoising).
- Defensive error catching: Gracefully handles corrupted files, truncated images, missing OCR binaries, and encrypted PDFs.
- Never crashes the application; returns structured status, user-friendly warnings, and diagnostic metadata.
"""

import os
import io
import shutil
import logging
import numpy as np
from typing import Tuple, Dict, Any, Optional
from PIL import Image, ImageEnhance, ImageFilter, UnidentifiedImageError

logger = logging.getLogger("ocr_engine")

# PyMuPDF (pymupdf / fitz) import with fallback
try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

# pytesseract import with Windows candidate path discovery
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
    """Checks whether pytesseract and Tesseract engine binary are operational."""
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
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def calculate_otsu_threshold(gray_np: np.ndarray) -> int:
    """Computes optimal Otsu binarization threshold for grayscale image."""
    hist, _ = np.histogram(gray_np.ravel(), bins=256, range=(0, 256))
    total = gray_np.size
    current_max = 0.0
    threshold = 127
    sum_total = np.dot(np.arange(256), hist)
    sum_background = 0.0
    weight_background = 0

    for t in range(256):
        weight_background += hist[t]
        if weight_background == 0:
            continue
        weight_foreground = total - weight_background
        if weight_foreground == 0:
            break

        sum_background += t * hist[t]
        mean_background = sum_background / weight_background
        mean_foreground = (sum_total - sum_background) / weight_foreground

        variance_between = (
            weight_background * weight_foreground * ((mean_background - mean_foreground) ** 2)
        )
        if variance_between > current_max:
            current_max = variance_between
            threshold = t

    return int(threshold)


def preprocess_image_for_ocr(
    image: Image.Image,
    to_grayscale: bool = True,
    scale_factor: float = 1.5,
    contrast_boost: float = 1.8,
    binarize: bool = True,
    denoise: bool = True
) -> Tuple[Image.Image, Dict[str, Any]]:
    """Applies computer vision preprocessing tailored for scanned documents."""
    applied = {}
    proc = image.copy()

    # 1. Ensure RGB mode
    if proc.mode in ("RGBA", "P"):
        proc = proc.convert("RGB")

    # 2. Resizing / Upscaling
    if scale_factor > 1.0 and (proc.width < 1600 or proc.height < 1600):
        new_w = int(proc.width * scale_factor)
        new_h = int(proc.height * scale_factor)
        proc = proc.resize((new_w, new_h), Image.Resampling.LANCZOS)
        applied["scaling"] = f"{scale_factor}x ({new_w}x{new_h}px)"

    # 3. Grayscale Conversion
    if to_grayscale:
        proc = proc.convert("L")
        applied["grayscale"] = True

    # 4. Contrast Enhancement
    if contrast_boost > 1.0:
        enhancer = ImageEnhance.Contrast(proc)
        proc = enhancer.enhance(contrast_boost)
        applied["contrast_boost"] = f"{contrast_boost}x"

    # 5. Denoising
    if denoise:
        proc = proc.filter(ImageFilter.MedianFilter(size=3))
        applied["median_denoise"] = "3x3 kernel"

    # 6. Otsu Binarization
    if binarize and proc.mode == "L":
        arr = np.array(proc)
        thresh_val = calculate_otsu_threshold(arr)
        bin_arr = np.where(arr > thresh_val, 255, 0).astype(np.uint8)
        proc = Image.fromarray(bin_arr)
        applied["otsu_binarization"] = f"Threshold={thresh_val}"

    return proc, applied


def extract_text_from_image(
    image: Image.Image,
    apply_preprocessing: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """Runs OCR on an image safely without crashing."""
    if not is_tesseract_available():
        return "", {
            "method": "OCR Unavailable",
            "ocr_used": False,
            "error": "Tesseract-OCR engine is not installed or not in PATH."
        }

    applied_steps = {}
    if apply_preprocessing:
        proc_img, applied_steps = preprocess_image_for_ocr(image)
    else:
        proc_img = image

    try:
        ocr_text = pytesseract.image_to_string(proc_img, config="--psm 3").strip()
        return ocr_text, {
            "method": "Tesseract OCR (Preprocessed)" if apply_preprocessing else "Tesseract OCR (Raw)",
            "ocr_used": True,
            "preprocessing": applied_steps,
            "char_count": len(ocr_text),
            "word_count": len(ocr_text.split())
        }
    except Exception as e:
        logger.error(f"Tesseract OCR execution error: {e}")
        return "", {
            "method": "OCR Error",
            "error": f"OCR processing failed: {str(e)}",
            "ocr_used": True
        }


def extract_document_text(
    file_bytes: bytes,
    filename: str,
    apply_ocr_preprocessing: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """
    Unified extraction entry point with Task 8 defensive error handling.
    
    Guarantees:
    - Never raises raw exceptions on corrupt files, invalid image formats, or OCR crashes.
    - Returns (text_string, metadata_dict).
    - If extraction fails, returns empty text and sets 'error' in metadata.
    """
    ext = os.path.splitext(filename)[1].lower()

    # --- 1. PDF Processing ---
    if ext == ".pdf":
        if fitz is None:
            return "", {
                "method": "Extraction Failed",
                "error": "PyMuPDF library is not installed.",
                "ocr_used": False
            }

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            logger.warning(f"Corrupted or invalid PDF file '{filename}': {e}")
            return "", {
                "method": "PDF Open Error",
                "error": f"Unreadable PDF document: The file appears to be corrupted or invalid.",
                "ocr_used": False
            }

        try:
            num_pages = len(doc)
            if num_pages == 0:
                return "", {
                    "method": "Empty PDF",
                    "error": "The PDF document contains 0 pages.",
                    "pages": 0,
                    "ocr_used": False
                }

            page_texts = []
            for p in range(num_pages):
                try:
                    txt = doc[p].get_text("text").strip()
                    if txt:
                        page_texts.append(txt)
                except Exception as pe:
                    logger.warning(f"Error reading page {p} of '{filename}': {pe}")

            combined_text = "\n\n".join(page_texts).strip()

            # Healthy native digital text found
            if len(combined_text) >= 40:
                return combined_text, {
                    "method": "PyMuPDF (Native Digital Text)",
                    "pages": num_pages,
                    "ocr_used": False,
                    "char_count": len(combined_text),
                    "word_count": len(combined_text.split())
                }

            # Scanned PDF fallback: Render pages and run OCR
            if is_tesseract_available():
                ocr_results = []
                last_proc = {}
                for p in range(num_pages):
                    try:
                        pix = doc[p].get_pixmap(dpi=200)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        text_p, meta_p = extract_text_from_image(img, apply_preprocessing=apply_ocr_preprocessing)
                        if text_p:
                            ocr_results.append(text_p)
                            last_proc = meta_p.get("preprocessing", {})
                    except Exception as re_err:
                        logger.warning(f"OCR render failed on page {p}: {re_err}")

                scanned_text = "\n\n".join(ocr_results).strip()
                if scanned_text:
                    return scanned_text, {
                        "method": "PyMuPDF Scanned Render + Tesseract OCR",
                        "pages": num_pages,
                        "ocr_used": True,
                        "preprocessing": last_proc,
                        "char_count": len(scanned_text),
                        "word_count": len(scanned_text.split())
                    }

            return combined_text, {
                "method": "Native PDF Text (Low Content)",
                "pages": num_pages,
                "ocr_used": is_tesseract_available(),
                "char_count": len(combined_text),
                "word_count": len(combined_text.split()),
                "warning": "PDF contains very low text density and OCR could not recover additional text."
            }
        except Exception as e:
            logger.error(f"Unexpected error parsing PDF '{filename}': {e}")
            return "", {
                "method": "PDF Extraction Error",
                "error": "Failed to extract text from PDF document.",
                "ocr_used": False
            }

    # --- 2. Image Processing ---
    elif ext in [".png", ".jpg", ".jpeg"]:
        try:
            img = Image.open(io.BytesIO(file_bytes))
            # Verify image integrity
            img.verify()
            # Reopen because verify() closes the stream
            img = Image.open(io.BytesIO(file_bytes))
        except (UnidentifiedImageError, OSError) as ie:
            logger.warning(f"Invalid image format for '{filename}': {ie}")
            return "", {
                "method": "Image Decode Error",
                "error": "Corrupted or unsupported image file.",
                "ocr_used": False
            }

        return extract_text_from_image(img, apply_preprocessing=apply_ocr_preprocessing)

    # --- 3. Unsupported Type ---
    else:
        return "", {
            "method": "Unsupported Format",
            "error": f"Unsupported format '{ext}'. Only .pdf, .png, .jpg, and .jpeg are supported.",
            "ocr_used": False
        }
