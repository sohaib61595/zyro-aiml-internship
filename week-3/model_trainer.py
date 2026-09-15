"""
ZYROO INTERNSHIP PROGRAM - WEEK 3
Module: Model Training, Comparison & Evaluation Pipeline
Steps 4, 5, 6, 9: Train, Compare, Evaluate Classifiers & Generate Confidences

Models:
1. Rule-Based Baseline (Keyword frequency heuristic)
2. Logistic Regression (Linear probabilistic classifier with L2 regularization)
3. Linear Support Vector Machine (LinearSVC with Platt/Calibrated probabilities)
4. Multinomial Naive Bayes (Frequency-based probabilistic classifier)

Outputs:
- Evaluation Metrics (Accuracy, Precision, Recall, F1-Score)
- Confusion Matrices and Comparison Bar Charts saved to week-3/graphs/
- Best Serialized Pipeline saved to week-3/models/best_classifier.joblib
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless environments
import matplotlib.pyplot as plt
import seaborn as sns

from typing import Dict, Any, List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)

from text_cleaner import clean_extracted_text, normalize_for_classification

# Constants
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


# ==============================================================================
# 1. RULE-BASED BASELINE CLASSIFIER
# ==============================================================================

class RuleBasedClassifier:
    """Keyword-based heuristic classifier used as a transparent baseline."""
    def __init__(self):
        self.classes_ = np.array(CLASSES)

    def fit(self, X, y=None):
        return self

    def predict_one(self, text: str) -> Tuple[str, float, Dict[str, int]]:
        text_lower = text.lower()
        inv_matches = sum(text_lower.count(k) for k in INVOICE_KEYWORDS)
        res_matches = sum(text_lower.count(k) for k in RESUME_KEYWORDS)
        oth_matches = sum(text_lower.count(k) for k in OTHER_KEYWORDS)

        scores = {"Invoice": inv_matches, "Resume": res_matches, "Other": oth_matches}
        total = inv_matches + res_matches + oth_matches

        if total == 0:
            return "Other", 0.35, scores

        best_cls = max(scores, key=scores.get)
        confidence = min(0.95, 0.45 + (scores[best_cls] / (total + 1)) * 0.50)
        return best_cls, round(confidence, 3), scores

    def predict(self, X: List[str]) -> np.ndarray:
        return np.array([self.predict_one(x)[0] for x in X])

    def predict_proba(self, X: List[str]) -> np.ndarray:
        probas = []
        for x in X:
            _, _, scores = self.predict_one(x)
            total = sum(scores.values()) + 1e-5
            p = [scores[c] / total for c in CLASSES]
            probas.append(p)
        return np.array(probas)


# ==============================================================================
# 2. DATASET LOADER
# ==============================================================================

def load_dataset(corpus_path: str = "dataset/documents_corpus.json") -> Tuple[List[str], List[str]]:
    """Loads and cleans document corpus from JSON file."""
    if not os.path.exists(corpus_path):
        # Fallback to absolute or week-3 relative
        alt_path = os.path.join(os.path.dirname(__file__), "dataset", "documents_corpus.json")
        if os.path.exists(alt_path):
            corpus_path = alt_path
        else:
            raise FileNotFoundError(f"Corpus dataset not found at {corpus_path}")

    with open(corpus_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    texts = [clean_extracted_text(item["text"]) for item in data]
    labels = [item["category"] for item in data]
    return texts, labels


# ==============================================================================
# 3. MODEL BENCHMARK & COMPARISON ENGINE
# ==============================================================================

def build_candidate_models() -> Dict[str, Any]:
    """Builds scikit-learn classification pipelines for comparison."""
    return {
        "Rule-Based Baseline": RuleBasedClassifier(),
        "Logistic Regression": Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, lowercase=True)),
            ("clf", LogisticRegression(C=1.0, max_iter=500, random_state=42))
        ]),
        "Linear SVM (Calibrated)": Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, lowercase=True)),
            ("clf", CalibratedClassifierCV(estimator=LinearSVC(C=1.0, random_state=42), cv=3))
        ]),
        "Multinomial Naive Bayes": Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, lowercase=True)),
            ("clf", MultinomialNB(alpha=0.1))
        ])
    }


def evaluate_models(
    texts: List[str],
    labels: List[str],
    output_dir: str = "graphs"
) -> Tuple[pd.DataFrame, Dict[str, np.ndarray], Dict[str, Any]]:
    """
    Executes cross-validation and held-out test evaluation across all models.
    Produces accuracy, precision, recall, F1-scores, and confusion matrices.
    """
    os.makedirs(output_dir, exist_ok=True)
    candidate_models = build_candidate_models()

    # Stratified Split: 75% Train, 25% Held-Out Test for confusion matrix & detailed reports
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.25, random_state=42, stratify=labels
    )

    metrics_records = []
    confusion_matrices = {}
    fitted_models = {}
    reports = {}

    for name, model in candidate_models.items():
        # Fit on train set
        if name == "Rule-Based Baseline":
            model.fit(X_train, y_train)
        else:
            model.fit(X_train, y_train)

        fitted_models[name] = model

        # Test set predictions
        y_pred = model.predict(X_test)
        
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, average="weighted", zero_division=0)
        rec = recall_score(y_test, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)
        
        cm = confusion_matrix(y_test, y_pred, labels=CLASSES)
        confusion_matrices[name] = cm
        reports[name] = classification_report(y_test, y_pred, labels=CLASSES, output_dict=True, zero_division=0)

        # Cross-validation score (5-fold) across the full dataset
        skf = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)
        cv_scores = []
        for train_idx, val_idx in skf.split(texts, labels):
            fold_train_X = [texts[i] for i in train_idx]
            fold_train_y = [labels[i] for i in train_idx]
            fold_val_X = [texts[i] for i in val_idx]
            fold_val_y = [labels[i] for i in val_idx]

            m_clone = build_candidate_models()[name]
            m_clone.fit(fold_train_X, fold_train_y)
            pred_v = m_clone.predict(fold_val_X)
            cv_scores.append(accuracy_score(fold_val_y, pred_v))
            
        cv_mean = float(np.mean(cv_scores))

        metrics_records.append({
            "Model": name,
            "Accuracy": round(acc, 4),
            "Precision": round(prec, 4),
            "Recall": round(rec, 4),
            "F1-Score": round(f1, 4),
            "CV 4-Fold Mean Acc": round(cv_mean, 4)
        })

    df_metrics = pd.DataFrame(metrics_records)
    print("\n" + "=" * 65)
    print("MODEL PERFORMANCE COMPARISON (WEEK 3)")
    print("=" * 65)
    print(df_metrics.to_string(index=False))
    print("=" * 65 + "\n")

    # Generate Visualizations
    plot_confusion_matrices(confusion_matrices, output_dir)
    plot_metrics_comparison(df_metrics, output_dir)
    plot_tfidf_features(texts, labels, output_dir)

    return df_metrics, confusion_matrices, fitted_models


# ==============================================================================
# 4. PLOTTING & VISUALIZATION GENERATORS
# ==============================================================================

def plot_confusion_matrices(cms: Dict[str, np.ndarray], output_dir: str):
    """Generates side-by-side confusion matrix heatmaps for all compared models."""
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, axes = plt.subplots(1, 4, figsize=(20, 4.8), dpi=200)

    for ax, (name, cm) in zip(axes, cms.items()):
        sns.heatmap(
            cm, annot=True, fmt="d", cmap="Blues", cbar=False,
            xticklabels=CLASSES, yticklabels=CLASSES, ax=ax,
            annot_kws={"size": 13, "weight": "bold"}
        )
        ax.set_title(f"{name}", fontsize=12, fontweight="bold", pad=10)
        ax.set_xlabel("Predicted Class", fontsize=10)
        ax.set_ylabel("True Class", fontsize=10)
        ax.tick_params(axis="both", labelsize=9)

    plt.suptitle("Document Classification Confusion Matrices Comparison (Week 3)", fontsize=14, fontweight="bold", y=1.04)
    plt.tight_layout()
    chart_path = os.path.join(output_dir, "confusion_matrices_comparison.png")
    plt.savefig(chart_path, bbox_inches="tight")
    plt.close()
    print(f"Saved Confusion Matrix Chart: {chart_path}")


def plot_metrics_comparison(df_metrics: pd.DataFrame, output_dir: str):
    """Generates grouped bar chart comparing Accuracy, Precision, Recall, and F1-Score."""
    plot_df = df_metrics.melt(
        id_vars=["Model"],
        value_vars=["Accuracy", "Precision", "Recall", "F1-Score"],
        var_name="Metric",
        value_name="Score"
    )

    plt.figure(figsize=(10, 5), dpi=200)
    sns.set_theme(style="whitegrid")
    palette = ["#1E40AF", "#0284C7", "#059669", "#D97706"]

    ax = sns.barplot(data=plot_df, x="Model", y="Score", hue="Metric", palette=palette)
    plt.title("Classification Models Benchmark: Accuracy, Precision, Recall & F1", fontsize=13, fontweight="bold", pad=12)
    plt.ylabel("Evaluation Score (0.0 to 1.0)", fontsize=10)
    plt.xlabel("Model Pipeline", fontsize=10)
    plt.ylim(0.0, 1.1)
    plt.legend(loc="lower right", frameon=True)

    # Annotate bar values
    for p in ax.patches:
        height = p.get_height()
        if not np.isnan(height) and height > 0.05:
            ax.annotate(f"{height:.2f}",
                        (p.get_x() + p.get_width() / 2., height),
                        ha='center', va='bottom', fontsize=8, color='#1F2937', xytext=(0, 2),
                        textcoords='offset points')

    plt.tight_layout()
    chart_path = os.path.join(output_dir, "model_metrics_barchart.png")
    plt.savefig(chart_path, bbox_inches="tight")
    plt.close()
    print(f"Saved Metrics Benchmark Chart: {chart_path}")


def plot_tfidf_features(texts: List[str], labels: List[str], output_dir: str):
    """Generates horizontal bar charts showing top TF-IDF predictive keywords per class."""
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=1000, lowercase=True)
    X = vectorizer.fit_transform(texts)
    feature_names = np.array(vectorizer.get_feature_names_out())

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), dpi=200)
    colors = ["#2563EB", "#059669", "#7C3AED"]

    for idx, (target_cls, col) in enumerate(zip(CLASSES, colors)):
        cls_indices = [i for i, l in enumerate(labels) if l == target_cls]
        cls_mean_tfidf = np.asarray(X[cls_indices].mean(axis=0)).flatten()
        top_indices = np.argsort(cls_mean_tfidf)[-10:]
        
        top_terms = feature_names[top_indices]
        top_scores = cls_mean_tfidf[top_indices]

        axes[idx].barh(top_terms, top_scores, color=col)
        axes[idx].set_title(f"Top Features: {target_cls}", fontsize=11, fontweight="bold")
        axes[idx].set_xlabel("Mean TF-IDF Score", fontsize=9)
        axes[idx].tick_params(axis="both", labelsize=9)

    plt.suptitle("Top Informative TF-IDF N-Grams by Document Category", fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    chart_path = os.path.join(output_dir, "tfidf_top_features.png")
    plt.savefig(chart_path, bbox_inches="tight")
    plt.close()
    print(f"Saved TF-IDF Features Chart: {chart_path}")


# ==============================================================================
# 5. SERIALIZE BEST MODEL & INFERENCE PIPELINE
# ==============================================================================

def train_and_save_best_model(
    texts: List[str],
    labels: List[str],
    models_dir: str = "models"
) -> str:
    """
    Fits the best production model (Linear SVM with Calibrated Probabilities or Logistic Regression)
    on the full dataset and serializes it.
    """
    os.makedirs(models_dir, exist_ok=True)
    
    # We choose Calibrated Linear SVM as the top high-precision classifier with well-calibrated confidence
    best_pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, lowercase=True)),
        ("clf", CalibratedClassifierCV(estimator=LinearSVC(C=1.0, random_state=42), cv=3))
    ])
    
    best_pipeline.fit(texts, labels)
    
    model_path = os.path.join(models_dir, "best_classifier.joblib")
    joblib.dump(best_pipeline, model_path)
    
    metadata = {
        "model_name": "Calibrated Linear Support Vector Machine (LinearSVC)",
        "vectorizer": "TF-IDF (1-2 ngrams, sublinear tf)",
        "classes": CLASSES,
        "sample_count": len(texts),
        "calibration": "Sigmoid (Platt Scaling) via 3-Fold CV"
    }
    with open(os.path.join(models_dir, "model_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Successfully serialized best classifier to: {model_path}")
    return model_path


# Global cached pipeline for fast inference
_CACHED_PIPELINE = None

def get_classifier():
    """Loads the cached or newly trained classifier pipeline."""
    global _CACHED_PIPELINE
    if _CACHED_PIPELINE is not None:
        return _CACHED_PIPELINE

    base_dir = os.path.dirname(__file__)
    model_path = os.path.join(base_dir, "models", "best_classifier.joblib")
    
    if os.path.exists(model_path):
        _CACHED_PIPELINE = joblib.load(model_path)
        return _CACHED_PIPELINE

    # If model file does not exist yet, train on the fly
    texts, labels = load_dataset(os.path.join(base_dir, "dataset", "documents_corpus.json"))
    train_and_save_best_model(texts, labels, os.path.join(base_dir, "models"))
    _CACHED_PIPELINE = joblib.load(model_path)
    return _CACHED_PIPELINE


def classify_document(text: str) -> Dict[str, Any]:
    """
    Step 9: Classifies document and provides calibrated confidence percentages.
    
    Returns:
        dict: {
            "document_type": str,
            "confidence": float (e.g. 0.94),
            "confidence_percentage": str (e.g. "94%"),
            "probabilities": Dict[str, float],
            "baseline_type": str,
            "baseline_confidence": float,
            "model_name": str
        }
    """
    cleaned = clean_extracted_text(text)
    if not cleaned or len(cleaned.strip()) < 15:
        return {
            "document_type": "Other",
            "confidence": 0.33,
            "confidence_percentage": "33%",
            "probabilities": {"Invoice": 0.33, "Resume": 0.33, "Other": 0.34},
            "baseline_type": "Other",
            "baseline_confidence": 0.33,
            "model_name": "Fallback Rule",
            "status": "INSUFFICIENT_TEXT"
        }

    clf = get_classifier()
    probs = clf.predict_proba([cleaned])[0]
    classes = list(clf.classes_)
    
    prob_dict = {cls: round(float(p), 4) for cls, p in zip(classes, probs)}
    pred_idx = np.argmax(probs)
    pred_class = classes[pred_idx]
    confidence = float(probs[pred_idx])

    # Compare with Rule-based Baseline
    rule_base = RuleBasedClassifier()
    base_pred, base_conf, base_scores = rule_base.predict_one(cleaned)

    return {
        "document_type": pred_class,
        "confidence": round(confidence, 3),
        "confidence_percentage": f"{int(round(confidence * 100))}%",
        "probabilities": prob_dict,
        "baseline_type": base_pred,
        "baseline_confidence": round(base_conf, 3),
        "baseline_scores": base_scores,
        "model_name": "Calibrated Linear SVM (TF-IDF)",
        "status": "SUCCESS"
    }


if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    corpus_file = os.path.join(base_dir, "dataset", "documents_corpus.json")
    print(f"Loading corpus from {corpus_file}...")
    X, y = load_dataset(corpus_file)
    print(f"Loaded {len(X)} documents across classes: {set(y)}")

    graphs_dir = os.path.join(base_dir, "graphs")
    models_dir = os.path.join(base_dir, "models")
    
    evaluate_models(X, y, output_dir=graphs_dir)
    train_and_save_best_model(X, y, models_dir=models_dir)
    print("Model training, comparison, evaluation and serialization complete!")
