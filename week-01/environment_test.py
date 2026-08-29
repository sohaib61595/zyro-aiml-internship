"""
Zyro AI/ML Internship - Week 1: Environment & Tooling Verification Test
------------------------------------------------------------------------
This script verifies that:
1. Python version and virtual environment are correctly configured.
2. Core AI/ML libraries (NumPy, Pandas, Matplotlib, Seaborn, Scikit-Learn) are imported.
3. A basic Machine Learning model (Random Forest Classifier on the Iris dataset) trains and predicts successfully.
"""

import sys
import subprocess
import os

# Set standard output encoding for cross-platform compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def print_separator(title=""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)

def verify_system():
    print_separator("1. SYSTEM & ENVIRONMENT VERIFICATION")
    print(f"[OK] Python Executable : {sys.executable}")
    print(f"[OK] Python Version    : {sys.version.split()[0]}")
    
    # Check virtual environment
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        print(f"[OK] Virtual Env Active: YES ({sys.prefix})")
    else:
        print(f"[!]  Virtual Env Active: NO (Running in base/global environment)")
        
    # Check Git version
    try:
        git_res = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
        print(f"[OK] Git Version       : {git_res.stdout.strip()}")
    except Exception as e:
        print(f"[X]  Git Check Failed  : {e}")

def verify_libraries():
    print_separator("2. AI/ML LIBRARIES VERIFICATION")
    
    packages = [
        ("numpy", "NumPy"),
        ("pandas", "Pandas"),
        ("matplotlib", "Matplotlib"),
        ("seaborn", "Seaborn"),
        ("sklearn", "Scikit-Learn"),
        ("jupyter", "Jupyter"),
    ]
    
    all_ok = True
    for module_name, display_name in packages:
        try:
            mod = __import__(module_name)
            version = getattr(mod, "__version__", "Installed")
            print(f"[OK] {display_name:<15} : Version {version}")
        except ImportError as e:
            print(f"[X]  {display_name:<15} : NOT INSTALLED ({e})")
            all_ok = False
            
    return all_ok

def run_ml_pipeline():
    print_separator("3. MACHINE LEARNING PIPELINE TEST (Iris Dataset)")
    
    import numpy as np
    import pandas as pd
    from sklearn.datasets import load_iris
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, classification_report
    
    print("[+] Loading Iris dataset...")
    iris = load_iris(as_frame=True)
    df = iris.frame
    print(f"[OK] Dataset loaded successfully: {df.shape[0]} rows, {df.shape[1]} columns")
    print(f"[OK] Target classes: {list(iris.target_names)}")
    
    X = iris.data
    y = iris.target
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"[OK] Train-test split complete: {len(X_train)} train samples, {len(X_test)} test samples")
    
    print("[+] Training RandomForestClassifier model...")
    model = RandomForestClassifier(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)
    print("[OK] Model training completed.")
    
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"[OK] Model Evaluation Accuracy: {acc * 100:.2f}%")
    
    # Feature importance
    feature_imp = pd.Series(model.feature_importances_, index=iris.feature_names).sort_values(ascending=False)
    print("\n[+] Top Feature Importances:")
    for feat, imp in feature_imp.items():
        print(f"    - {feat:<25}: {imp:.4f}")
        
    print("\n[+] Classification Report:")
    print(classification_report(y_test, y_pred, target_names=iris.target_names))

def main():
    print("=" * 60)
    print("     ZYRO AI/ML INTERNSHIP - ENVIRONMENT VERIFICATION")
    print("=" * 60)
    
    verify_system()
    libs_ok = verify_libraries()
    
    if libs_ok:
        run_ml_pipeline()
        print_separator("VERIFICATION SUMMARY")
        print("ALL CHECKS PASSED SUCCESSFULLY! Environment is ready for AI/ML development.")
        print("=" * 60)
    else:
        print_separator("VERIFICATION FAILED")
        print("Some required libraries are missing. Please run:")
        print("pip install -r requirements.txt")
        print("=" * 60)

if __name__ == "__main__":
    main()
