"""
ZYROO INTERNSHIP PROGRAM - WEEK 3
Module: Improved OCR Handling & Preprocessing Engine
Step 3: Improve OCR Handling for Scanned and Image Documents

Techniques:
1. Grayscale Conversion (Removes color artifacts and background tint)
2. DPI Upscaling / Resizing (Sharpens character contours for small scans)
3. Contrast Enhancement (Separates text from low-contrast paper)
4. Adaptive/Otsu Binarization (Converts to clean black-and-white binary image)
5. Noise Reduction (Median filter to eliminate salt-and-pepper scanner noise)
6. Dual-Engine Extraction (PyMuPDF Native Text -> High-Res Page Render -> Preprocessed OCR)
"""

import os
import io
import shutil
import numpy as np
from typing import Tuple, Dict, Any, Optional
from PIL import Image, ImageEnhance, ImageFilter

# Optional PyMuPDF (fitz)
try:
    import fitz
except ImportError:
    fitz = None

# Optional OCR (pytesseract)
try:
    import pytesseract
    # Auto-detect Tesseract executable on Windows or PATH
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
    """
    Applies image preprocessing pipeline tailored for scanned documents and receipts.
    
    Returns:
        (preprocessed_image, applied_steps_dict)
    """
    applied = {}
    proc = image.copy()

    # 1. RGBA / Palette to RGB
    if proc.mode in ("RGBA", "P"):
        proc = proc.convert("RGB")

    # 2. Resizing / Upscaling (low-resolution scans benefit significantly from 1.5x - 2.0x scale)
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

    # 5. Noise Reduction (Median filter eliminates salt-and-pepper scanning artifacts)
    if denoise:
        proc = proc.filter(ImageFilter.MedianFilter(size=3))
        applied["median_denoise"] = "3x3 kernel"

    # 6. Otsu Binarization / Thresholding
    if binarize and proc.mode == "L":
        arr = np.array(proc)
        thresh_val = calculate_otsu_threshold(arr)
        # Apply threshold (pixels above thresh become 255 white, below become 0 black)
        bin_arr = np.where(arr > thresh_val, 255, 0).astype(np.uint8)
        proc = Image.fromarray(bin_arr)
        applied["otsu_binarization"] = f"Threshold={thresh_val}"

    return proc, applied


def extract_text_from_image(
    image: Image.Image,
    apply_preprocessing: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """Runs OCR on an image with optional preprocessing."""
    if not is_tesseract_available():
        return "[Notice: Tesseract-OCR engine is not installed. Scanned text extraction unavailable.]", {
            "method": "OCR Unavailable",
            "ocr_used": False
        }

    applied_steps = {}
    if apply_preprocessing:
        proc_img, applied_steps = preprocess_image_for_ocr(image)
    else:
        proc_img = image

    try:
        # psm 6 = Assume a single uniform block of text; psm 3 = Fully automatic page segmentation
        ocr_text = pytesseract.image_to_string(proc_img, config="--psm 3").strip()
        return ocr_text, {
            "method": "Tesseract OCR (Preprocessed)" if apply_preprocessing else "Tesseract OCR (Raw)",
            "ocr_used": True,
            "preprocessing": applied_steps,
            "char_count": len(ocr_text),
            "word_count": len(ocr_text.split())
        }
    except Exception as e:
        return f"[OCR Error: {e}]", {"method": "OCR Error", "error": str(e), "ocr_used": True}


def extract_document_text(
    file_bytes: bytes,
    filename: str,
    apply_ocr_preprocessing: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """
    Main extraction interface.
    Handles digital PDFs (PyMuPDF), scanned PDFs (PyMuPDF Render + OCR),
    and image files (.png, .jpg, .jpeg) with full preprocessing.
    """
    ext = os.path.splitext(filename)[1].lower()

    # --- PDF Processing ---
    if ext == ".pdf":
        if fitz is not None:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            num_pages = len(doc)
            page_texts = [doc[p].get_text("text").strip() for p in range(num_pages) if doc[p].get_text("text").strip()]
            combined_text = "\n\n".join(page_texts).strip()

            # If document contains healthy selectable text, return native output
            if len(combined_text) >= 40:
                return combined_text, {
                    "method": "PyMuPDF (Native Digital Text)",
                    "pages": num_pages,
                    "ocr_used": False,
                    "char_count": len(combined_text),
                    "word_count": len(combined_text.split())
                }

            # Scanned PDF: Render pages as images (200 DPI) and run preprocessed OCR
            if is_tesseract_available():
                ocr_results = []
                last_proc = {}
                for p in range(num_pages):
                    pix = doc[p].get_pixmap(dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    text_p, meta_p = extract_text_from_image(img, apply_preprocessing=apply_ocr_preprocessing)
                    if text_p and not text_p.startswith("["):
                        ocr_results.append(text_p)
                        last_proc = meta_p.get("preprocessing", {})

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

            return "[Notice: PDF contains no selectable text and OCR could not recover legible text.]", {
                "method": "Extraction Incomplete",
                "pages": num_pages,
                "ocr_used": is_tesseract_available(),
                "char_count": 0,
                "word_count": 0
            }

    # --- Image Processing ---
    elif ext in [".png", ".jpg", ".jpeg"]:
        img = Image.open(io.BytesIO(file_bytes))
        return extract_text_from_image(img, apply_preprocessing=apply_ocr_preprocessing)

    else:
        raise ValueError(f"Unsupported file format '{ext}'. Supported: .pdf, .png, .jpg, .jpeg")
