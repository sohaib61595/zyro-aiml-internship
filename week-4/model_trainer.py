"""
ZYROO INTERNSHIP PROGRAM - WEEK 4
Module: Document Classification & Calibrated Inference Engine
Pipeline Step: Classify documents into 'Invoice', 'Resume', or 'Other' with confidence scores.

Features:
- Loads the trained Calibrated Linear Support Vector Machine (TF-IDF 1-2 ngrams) pipeline.
- Fast inference with cached pipeline in memory.
- Provides calibrated prediction probabilities (Platt Scaling).
- Falls back gracefully to Rule-based classifier if needed.
"""

import os
import json
import joblib
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import numpy as np
from typing import Dict, Any, List, Tuple
from text_cleaner import clean_extracted_text

CLASSES = ["Invoice", "Resume", "Other"]

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


class RuleBasedClassifier:
    """Keyword-based heuristic classifier used as a transparent baseline and fallback."""
    def __init__(self):
        self.classes_ = np.array(CLASSES)

    def fit(self, X, y=None):
        return self

    def predict_one(self, text: str) -> Tuple[str, float, Dict[str, int]]:
        text_lower = text.lower()
        counts = {
            "Invoice": sum(1 for kw in INVOICE_KEYWORDS if kw in text_lower),
            "Resume": sum(1 for kw in RESUME_KEYWORDS if kw in text_lower),
            "Other": sum(1 for kw in OTHER_KEYWORDS if kw in text_lower),
        }
        total = sum(counts.values())
        if total == 0:
            return "Other", 0.33, counts

        sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        top_cls, top_count = sorted_counts[0]
        confidence = round(top_count / total, 3)
        return top_cls, confidence, counts

    def predict(self, texts: List[str]) -> List[str]:
        return [self.predict_one(t)[0] for t in texts]


_CACHED_PIPELINE = None


def get_classifier():
    """Loads and caches the serialized best classifier pipeline."""
    global _CACHED_PIPELINE
    if _CACHED_PIPELINE is not None:
        return _CACHED_PIPELINE

    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "models", "best_classifier.joblib")

    if os.path.exists(model_path):
        try:
            _CACHED_PIPELINE = joblib.load(model_path)
            return _CACHED_PIPELINE
        except Exception:
            pass

    # Fallback to week-3 model if not found in week-4
    w3_model = os.path.abspath(os.path.join(base_dir, "..", "week-3", "models", "best_classifier.joblib"))
    if os.path.exists(w3_model):
        try:
            _CACHED_PIPELINE = joblib.load(w3_model)
            return _CACHED_PIPELINE
        except Exception:
            pass

    return None


def classify_document(text: str) -> Dict[str, Any]:
    """
    Classifies clean document text and provides calibrated confidence score.
    
    Returns:
        dict: {
            "document_type": str,
            "confidence": float,
            "confidence_percentage": str,
            "probabilities": Dict[str, float],
            "model_name": str,
            "status": str
        }
    """
    cleaned = clean_extracted_text(text)
    if not cleaned or len(cleaned.strip()) < 15:
        return {
            "document_type": "Other",
            "confidence": 0.33,
            "confidence_percentage": "33%",
            "probabilities": {"Invoice": 0.33, "Resume": 0.33, "Other": 0.34},
            "model_name": "Fallback Baseline",
            "status": "INSUFFICIENT_TEXT"
        }

    clf = get_classifier()
    if clf is not None:
        try:
            probs = clf.predict_proba([cleaned])[0]
            classes = list(clf.classes_)
            prob_dict = {cls: round(float(p), 4) for cls, p in zip(classes, probs)}
            pred_idx = np.argmax(probs)
            pred_class = classes[pred_idx]
            confidence = float(probs[pred_idx])

            return {
                "document_type": pred_class,
                "confidence": round(confidence, 3),
                "confidence_percentage": f"{int(round(confidence * 100))}%",
                "probabilities": prob_dict,
                "model_name": "Calibrated Linear SVM (TF-IDF)",
                "status": "SUCCESS"
            }
        except Exception:
            pass

    # Rule-based fallback if ML pipeline unavailable
    rule_base = RuleBasedClassifier()
    pred_class, confidence, counts = rule_base.predict_one(cleaned)
    return {
        "document_type": pred_class,
        "confidence": confidence,
        "confidence_percentage": f"{int(round(confidence * 100))}%",
        "probabilities": {cls: round(c / max(1, sum(counts.values())), 2) for cls, c in counts.items()},
        "model_name": "Rule-Based Keyword Heuristic",
        "status": "SUCCESS"
    }
