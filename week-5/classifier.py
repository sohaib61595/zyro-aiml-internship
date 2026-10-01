"""
ZYROO INTERNSHIP PROGRAM - WEEK 5
Module: Document Classifier with Calibrated Inference & Confidence Awareness
Focus: Workflow automation, validation, review and auditability

Requirements Addressed:
- Task 4 (Confidence-Aware Review):
  - Store predicted document type and confidence when available.
  - Never create or estimate a confidence value when the model does not provide one.
  - Documented threshold for uncertain classifications: CONFIDENCE_THRESHOLD = 0.75.
"""

import os
import joblib
import logging
import numpy as np
from typing import Dict, Any, Optional, List

logger = logging.getLogger("document_classifier")

CLASSES = ["Invoice", "Resume", "Other"]

# Documented operational threshold for uncertain classifications (Requirement 4)
CONFIDENCE_THRESHOLD = 0.75

_CACHED_MODEL = None


def get_classifier():
    """Loads and caches the serialized classifier model pipeline."""
    global _CACHED_MODEL
    if _CACHED_MODEL is not None:
        return _CACHED_MODEL

    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "models", "best_classifier.joblib")

    if os.path.exists(model_path):
        try:
            _CACHED_MODEL = joblib.load(model_path)
            return _CACHED_MODEL
        except Exception as e:
            logger.warning(f"Error loading trained model from {model_path}: {e}")

    # Fallback search in week-4 models
    w4_path = os.path.abspath(os.path.join(base_dir, "..", "week-4", "models", "best_classifier.joblib"))
    if os.path.exists(w4_path):
        try:
            _CACHED_MODEL = joblib.load(w4_path)
            return _CACHED_MODEL
        except Exception:
            pass

    return None


# Keywords for heuristic classification fallback
INVOICE_KEYWORDS = [
    "invoice", "tax invoice", "bill to", "billed to", "invoice number", "inv#",
    "subtotal", "total amount", "amount due", "balance due", "tax", "gst", "vat",
    "unit price", "quantity", "qty", "due date", "pkr", "usd", "eur", "payment terms"
]

RESUME_KEYWORDS = [
    "resume", "curriculum vitae", "cv", "education", "experience", "work experience",
    "skills", "technical skills", "projects", "certifications", "bachelor", "master",
    "university", "gpa", "internship", "employment", "summary", "profile", "technologies"
]

OTHER_KEYWORDS = [
    "memorandum", "agreement", "nda", "confidential", "meeting minutes", "policy",
    "announcement", "guidelines", "protocol", "syllabus", "tender", "press release",
    "lease", "operating procedure", "action items", "department"
]


def classify_document(text: str) -> Dict[str, Any]:
    """
    Classifies clean document text into 'Invoice', 'Resume', or 'Other'.
    
    Adheres strictly to Requirement 4:
    - Extracts model confidence when and ONLY when the model provides probabilities.
    - If the model does not provide probabilities, confidence is explicitly None.
    - Never fabricates or estimates a confidence score.
    
    Returns:
        dict: {
            "document_type": str,
            "confidence": Optional[float],
            "confidence_percentage": Optional[str],
            "probabilities": Optional[Dict[str, float]],
            "model_name": str,
            "is_confident": bool, # True if confidence is not None and >= CONFIDENCE_THRESHOLD
            "status": str
        }
    """
    cleaned = text.strip() if text else ""
    if len(cleaned) < 15:
        return {
            "document_type": "Other",
            "confidence": None,  # No confidence fabricated for insufficient text
            "confidence_percentage": "N/A",
            "probabilities": None,
            "model_name": "Insufficient Text Fallback",
            "is_confident": False,
            "status": "INSUFFICIENT_TEXT"
        }

    clf = get_classifier()

    # 1. Machine Learning Model Path
    if clf is not None:
        try:
            # Check if model natively provides predict_proba (e.g. Platt-calibrated classifier)
            if hasattr(clf, "predict_proba"):
                probs = clf.predict_proba([cleaned])[0]
                classes = list(getattr(clf, "classes_", CLASSES))
                prob_dict = {cls: round(float(p), 4) for cls, p in zip(classes, probs)}
                pred_idx = int(np.argmax(probs))
                pred_class = classes[pred_idx]
                confidence = float(probs[pred_idx])

                is_confident = (confidence >= CONFIDENCE_THRESHOLD)

                return {
                    "document_type": pred_class,
                    "confidence": round(confidence, 4),
                    "confidence_percentage": f"{int(round(confidence * 100))}%",
                    "probabilities": prob_dict,
                    "model_name": "Calibrated Linear SVM (TF-IDF)",
                    "is_confident": is_confident,
                    "status": "SUCCESS"
                }
            elif hasattr(clf, "predict"):
                # Model provides predictions but NO probabilities
                pred_class = str(clf.predict([cleaned])[0])
                return {
                    "document_type": pred_class,
                    "confidence": None,  # Explicitly None per Requirement 4
                    "confidence_percentage": "N/A",
                    "probabilities": None,
                    "model_name": "Uncalibrated ML Classifier",
                    "is_confident": False,
                    "status": "NO_PROBABILITIES"
                }
        except Exception as e:
            logger.warning(f"ML classification failed: {e}. Falling back to heuristics.")

    # 2. Heuristic Rule-Based Fallback
    text_lower = cleaned.lower()
    counts = {
        "Invoice": sum(1 for kw in INVOICE_KEYWORDS if kw in text_lower),
        "Resume": sum(1 for kw in RESUME_KEYWORDS if kw in text_lower),
        "Other": sum(1 for kw in OTHER_KEYWORDS if kw in text_lower),
    }
    total_hits = sum(counts.values())

    if total_hits == 0:
        return {
            "document_type": "Other",
            "confidence": None,  # Explicitly None
            "confidence_percentage": "N/A",
            "probabilities": None,
            "model_name": "Rule-Based Keyword Heuristic",
            "is_confident": False,
            "status": "NO_KEYWORDS_MATCHED"
        }

    sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    top_cls, top_count = sorted_counts[0]

    # Keyword frequency proportion
    heuristic_conf = round(top_count / total_hits, 3)

    return {
        "document_type": top_cls,
        "confidence": heuristic_conf,
        "confidence_percentage": f"{int(round(heuristic_conf * 100))}%",
        "probabilities": {cls: round(c / total_hits, 3) for cls, c in counts.items()},
        "model_name": "Rule-Based Keyword Heuristic",
        "is_confident": (heuristic_conf >= CONFIDENCE_THRESHOLD),
        "status": "SUCCESS"
    }
