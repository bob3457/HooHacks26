"""
train_models.py — Run once to train XGBoost models and save artifacts.

Usage (from project root):
    python backend/train_models.py
"""

import sys
import os

# Make src importable when running from project root or backend/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from src.ingestion.pipeline import run_ingestion
from src.features.engineer import build_features, save_feature_store
from src.models.forecaster import train

print("=== AgriSignal Model Training ===\n")

print("1/3 — Loading data...")
data = run_ingestion(start="1997-01", end="2024-12")
print(f"     NG spot:  {data['ng_spot'].dropna().shape[0]} months")
print(f"     Urea:     {data['urea'].dropna().shape[0]} months")
print(f"     DAP:      {data['dap'].dropna().shape[0]} months")
print(f"     Storage:  {data['storage_mmcf'].dropna().shape[0]} months")

print("\n2/3 — Building feature store...")
fs = build_features(data)
path = save_feature_store(fs)
print(f"     Feature store: {fs.shape[0]} rows x {fs.shape[1]} cols -> {path}")

print("\n3/3 — Training XGBoost models (t1, t2, t3)...")
metadata = train(fs)

print("\n=== Training complete ===")
print(f"  Residual std  t1: ${metadata['residual_std_t1']:.1f}/mt")
print(f"  Residual std  t2: ${metadata['residual_std_t2']:.1f}/mt")
print(f"  Residual std  t3: ${metadata['residual_std_t3']:.1f}/mt")
if "test_rmse_t2" in metadata:
    print(f"  Test RMSE     t2: ${metadata['test_rmse_t2']:.1f}/mt")
    print(f"  Test dir-acc  t2: {metadata.get('test_dir_acc_t2', 0)*100:.0f}%")
