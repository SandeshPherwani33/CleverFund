"""
Visualizations for model training, SMOTE results, and prediction metrics
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Setup
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static" / "charts"
STATIC_DIR.mkdir(exist_ok=True)


def plot_class_distribution(y_before, y_after, title="Class Distribution Before and After SMOTE"):
    """
    Create visualization comparing class distribution before and after SMOTE
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Before SMOTE
    unique, counts = np.unique(y_before, return_counts=True)
    colors = ['#e74c3c', '#2ecc71']  # Red for failure, Green for success
    labels = ['Failure (0)', 'Success (1)']
    
    axes[0].bar(labels, counts, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
    axes[0].set_title('Before SMOTE (Imbalanced)', fontsize=14, fontweight='bold')
    axes[0].set_ylabel('Number of Samples', fontsize=12)
    for i, v in enumerate(counts):
        axes[0].text(i, v + 10, str(v), ha='center', fontweight='bold')
    axes[0].grid(axis='y', alpha=0.3)
    
    # After SMOTE
    unique_after, counts_after = np.unique(y_after, return_counts=True)
    axes[1].bar(labels, counts_after, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
    axes[1].set_title('After SMOTE (Balanced)', fontsize=14, fontweight='bold')
    axes[1].set_ylabel('Number of Samples', fontsize=12)
    for i, v in enumerate(counts_after):
        axes[1].text(i, v + 10, str(v), ha='center', fontweight='bold')
    axes[1].grid(axis='y', alpha=0.3)
    
    plt.suptitle(title, fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    
    # Save
    save_path = STATIC_DIR / "smote_comparison.png"
    plt.savefig(save_path, dpi=100, bbox_inches='tight')
    print(f"Chart saved: {save_path}")
    plt.close()
    
    return str(save_path)


def plot_feature_importance(feature_names, importances, title="Feature Importance"):
    """
    Create feature importance bar plot
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Sort by importance
    indices = np.argsort(importances)[::-1]
    sorted_names = [feature_names[i] for i in indices]
    sorted_importances = [importances[i] for i in indices]
    
    # Create bar plot
    colors = plt.cm.viridis(np.linspace(0, 1, len(sorted_names)))
    bars = ax.barh(sorted_names, sorted_importances, color=colors, edgecolor='black', linewidth=1.5)
    
    ax.set_xlabel('Importance Score', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)
    
    # Add value labels
    for i, v in enumerate(sorted_importances):
        ax.text(v + 0.01, i, f'{v:.4f}', va='center', fontweight='bold')
    
    plt.tight_layout()
    
    # Save
    save_path = STATIC_DIR / "feature_importance.png"
    plt.savefig(save_path, dpi=100, bbox_inches='tight')
    print(f"Chart saved: {save_path}")
    plt.close()
    
    return str(save_path)


def plot_confusion_matrix(y_true, y_pred, title="Confusion Matrix"):
    """
    Create confusion matrix heatmap
    """
    from sklearn.metrics import confusion_matrix
    
    cm = confusion_matrix(y_true, y_pred)
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Create heatmap
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=['Failure', 'Success'],
                yticklabels=['Failure', 'Success'],
                cbar_kws={'label': 'Count'},
                linewidths=2, linecolor='black', ax=ax)
    
    ax.set_ylabel('True Label', fontsize=12, fontweight='bold')
    ax.set_xlabel('Predicted Label', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    # Save
    save_path = STATIC_DIR / "confusion_matrix.png"
    plt.savefig(save_path, dpi=100, bbox_inches='tight')
    print(f"Chart saved: {save_path}")
    plt.close()
    
    return str(save_path)


def plot_prediction_distribution(predictions, probabilities, title="Prediction Distribution"):
    """
    Create distribution plot of prediction probabilities
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Histogram
    axes[0].hist(probabilities, bins=30, color='#3498db', alpha=0.7, edgecolor='black')
    axes[0].axvline(0.5, color='red', linestyle='--', linewidth=2, label='Decision Boundary (50%)')
    axes[0].set_xlabel('Probability', fontsize=12, fontweight='bold')
    axes[0].set_ylabel('Frequency', fontsize=12, fontweight='bold')
    axes[0].set_title('Prediction Probability Distribution', fontsize=12, fontweight='bold')
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    
    # Pie chart
    unique_pred, counts = np.unique(predictions, return_counts=True)
    labels = ['Failure', 'Success']
    colors = ['#e74c3c', '#2ecc71']
    explode = (0.05, 0.05)
    
    axes[1].pie(counts, labels=labels, colors=colors, autopct='%1.1f%%',
                startangle=90, explode=explode, textprops={'fontsize': 12, 'fontweight': 'bold'})
    axes[1].set_title('Prediction Distribution', fontsize=12, fontweight='bold')
    
    plt.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    
    # Save
    save_path = STATIC_DIR / "prediction_distribution.png"
    plt.savefig(save_path, dpi=100, bbox_inches='tight')
    print(f"Chart saved: {save_path}")
    plt.close()
    
    return str(save_path)


def generate_training_report(metrics):
    """
    Generate JSON report from training metrics
    """
    report = {
        'title': 'Model Training Report',
        'timestamp': pd.Timestamp.now().isoformat(),
        'model_type': 'RandomForest with SMOTE',
        'metrics': {
            'test_accuracy': metrics.get('test_accuracy', 0),
            'roc_auc': metrics.get('roc_auc', 0),
            'total_samples': len(metrics.get('y_test', [])),
            'test_samples': len(metrics.get('y_test', []))
        },
        'smote_info': {
            'algorithm': 'SMOTE (Synthetic Minority Over-sampling Technique)',
            'purpose': 'Handle class imbalance in training data',
            'applied_to': 'Training set only',
            'test_set': 'Original distribution (not modified)'
        }
    }
    
    # Save report
    report_path = BASE_DIR / "data" / "training_report.json"
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"Report saved: {report_path}")
    return report


if __name__ == "__main__":
    # Example usage
    print("Visualization module loaded successfully")
    print(f"Charts will be saved to: {STATIC_DIR}")
