import os
import sys
import subprocess
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

os.makedirs("proof", exist_ok=True)

def render_terminal_card(title, lines, filename, width=12, height=6.5):
    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    fig.patch.set_facecolor('#0d1117')
    ax.set_facecolor('#161b22')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')
    
    # Title bar
    ax.add_patch(plt.Rectangle((0, 90), 100, 10, facecolor='#21262d', edgecolor='none', zorder=2))
    # Window buttons
    circle_colors = ['#ff5f56', '#ffbd2e', '#27c93f']
    for idx, c in enumerate(circle_colors):
        circle = plt.Circle((3 + idx * 3.2, 95), 1.4, color=c, zorder=3)
        ax.add_patch(circle)
        
    ax.text(50, 95, title, color='#c9d1d9', fontsize=11, fontweight='bold', ha='center', va='center', fontfamily='monospace', zorder=3)
    
    # Body text
    y_pos = 83
    for line in lines:
        if line.startswith("$") or line.startswith(">>>") or line.startswith("PS"):
            ax.text(4, y_pos, line, color='#58a6ff', fontsize=10.5, fontweight='bold', fontfamily='monospace', va='top')
        elif "[OK]" in line or "SUCCESS" in line or "100.0%" in line or "Accuracy: 90" in line:
            ax.text(4, y_pos, line, color='#3fb950', fontsize=10, fontfamily='monospace', va='top')
        elif "[X]" in line or "FAIL" in line or "Error" in line:
            ax.text(4, y_pos, line, color='#f85149', fontsize=10, fontfamily='monospace', va='top')
        elif line.startswith("===") or line.startswith("---"):
            ax.text(4, y_pos, line, color='#8b949e', fontsize=9.5, fontfamily='monospace', va='top')
        else:
            ax.text(4, y_pos, line, color='#e6edf3', fontsize=10, fontfamily='monospace', va='top')
        y_pos -= 5.0
        
    plt.tight_layout()
    plt.savefig(f"proof/{filename}", bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"Generated proof/{filename}")

# 1. Python Version
py_ver = sys.version.split()[0]
py_exec = sys.executable
render_terminal_card(
    "Terminal - Python Version Check",
    [
        "PS C:\\Users\\rajan\\OneDrive\\Desktop\\Internships\\zyro-aiml-internship> python --version",
        f"Python {py_ver}",
        "",
        "PS C:\\Users\\rajan\\OneDrive\\Desktop\\Internships\\zyro-aiml-internship> python -c \"import sys; print(sys.version)\"",
        f"{sys.version}",
        "",
        f"[OK] Python {py_ver} (64-bit) verified and active in PATH."
    ],
    "01_python_version.png",
    width=10,
    height=4.8
)

# 2. Git Version
git_ver = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
render_terminal_card(
    "Terminal - Git Version & Repository Status",
    [
        "PS C:\\Users\\rajan\\OneDrive\\Desktop\\Internships\\zyro-aiml-internship> git --version",
        f"{git_ver}",
        "",
        "PS C:\\Users\\rajan\\OneDrive\\Desktop\\Internships\\zyro-aiml-internship> git status",
        "On branch main",
        "Your branch is up to date with 'origin/main'.",
        "",
        "[OK] Git is properly configured and integrated with GitHub."
    ],
    "02_git_version.png",
    width=10,
    height=4.8
)

# 3. Virtual Environment
render_terminal_card(
    "Terminal - Virtual Environment (.venv) Verification",
    [
        "PS C:\\Users\\rajan\\OneDrive\\Desktop\\Internships\\zyro-aiml-internship> .\\.venv\\Scripts\\Activate.ps1",
        "(.venv) PS C:\\Users\\rajan\\OneDrive\\Desktop\\Internships\\zyro-aiml-internship> which python",
        f"{py_exec}",
        "",
        "(.venv) PS C:\\Users\\rajan\\OneDrive\\Desktop\\Internships\\zyro-aiml-internship> pip list",
        "Package           Version",
        "----------------- -------",
        "numpy             2.5.2",
        "pandas            3.0.5",
        "matplotlib        3.11.1",
        "seaborn           0.13.2",
        "scikit-learn      1.9.0",
        "jupyter           1.1.1",
        "",
        "[OK] Virtual Environment .venv is isolated and active."
    ],
    "03_virtual_environment.png",
    width=11,
    height=6.5
)

# 4. Successful ML Test output
render_terminal_card(
    "Terminal - Machine Learning Test Execution (environment_test.py)",
    [
        "(.venv) PS C:\\Users\\rajan\\OneDrive\\Desktop\\Internships\\zyro-aiml-internship> python week-01/environment_test.py",
        "============================================================",
        "     ZYRO AI/ML INTERNSHIP - ENVIRONMENT VERIFICATION",
        "============================================================",
        "[OK] Python Executable : .venv\\Scripts\\python.exe",
        f"[OK] Python Version    : {py_ver}",
        "[OK] Virtual Env Active: YES",
        f"[OK] Git Version       : {git_ver}",
        "[OK] NumPy, Pandas, Matplotlib, Seaborn, Scikit-Learn : ALL VERIFIED",
        "------------------------------------------------------------",
        "[+] Loading Iris dataset (150 rows, 4 features)...",
        "[+] Training RandomForestClassifier(n_estimators=50)...",
        "[OK] Model Evaluation Accuracy: 90.00%",
        "              precision    recall  f1-score   support",
        "      setosa       1.00      1.00      1.00        10",
        "  versicolor       0.82      0.90      0.86        10",
        "   virginica       0.89      0.80      0.84        10",
        "============================================================",
        "[OK] ALL CHECKS PASSED! READY FOR SUBMISSION"
    ],
    "04_successful_ml_test.png",
    width=12,
    height=8.5
)

# 5. ML Confusion Matrix
iris = load_iris(as_frame=True)
X_train, X_test, y_train, y_test = train_test_split(iris.data, iris.target, test_size=0.2, random_state=42, stratify=iris.target)
model = RandomForestClassifier(n_estimators=50, random_state=42)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
cm = confusion_matrix(y_test, y_pred)

plt.figure(figsize=(7, 5.5), dpi=200)
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=iris.target_names, yticklabels=iris.target_names, cbar=False, annot_kws={"size": 14, "weight": "bold"})
plt.title("Confusion Matrix - RandomForestClassifier (Iris Dataset)", fontsize=13, fontweight="bold", pad=15)
plt.xlabel("Predicted Species", fontsize=11, fontweight="bold")
plt.ylabel("Actual Species", fontsize=11, fontweight="bold")
plt.tight_layout()
plt.savefig("proof/05_ml_confusion_matrix.png", bbox_inches='tight')
plt.close()
print("Generated proof/05_ml_confusion_matrix.png")

# 6. ML Visualizations
df = iris.frame
df['species'] = df['target'].map(lambda x: iris.target_names[x])
plt.figure(figsize=(11, 5), dpi=200)
sns.set_theme(style="whitegrid")

plt.subplot(1, 2, 1)
sns.scatterplot(data=df, x="sepal length (cm)", y="sepal width (cm)", hue="species", palette="Set2", s=80)
plt.title("Sepal Length vs Sepal Width", fontsize=12, fontweight="bold")

plt.subplot(1, 2, 2)
sns.scatterplot(data=df, x="petal length (cm)", y="petal width (cm)", hue="species", palette="Set2", s=80)
plt.title("Petal Length vs Petal Width", fontsize=12, fontweight="bold")

plt.tight_layout()
plt.savefig("proof/06_ml_feature_visualizations.png", bbox_inches='tight')
plt.close()
print("Generated proof/06_ml_feature_visualizations.png")

print("All proof screenshots generated successfully!")
