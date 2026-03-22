import subprocess
import json
import numpy as np
import os

RUNS = 50
META_PATH = "data/models/model_metadata.json"

# Lists to hold the results of all 50 runs
t1_accs, t2_accs, t3_accs = [], [], []
t1_rmse, t2_rmse, t3_rmse = [], [], []

print(f"🚀 Starting {RUNS} training loops...")

for i in range(RUNS):
    print(f"Run {i+1}/{RUNS}...", end=" ", flush=True)
    
    # Run the training script silently
    subprocess.run(["python", "backend/train_models.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Open the generated metadata file to grab the exact scores
    if os.path.exists(META_PATH):
        with open(META_PATH, "r") as f:
            meta = json.load(f)
            t1_accs.append(meta.get("test_clf_acc_t1", 0))
            t2_accs.append(meta.get("test_clf_acc_t2", 0))
            t3_accs.append(meta.get("test_clf_acc_t3", 0))
            
            t1_rmse.append(meta.get("test_rmse_t1", 0))
            t2_rmse.append(meta.get("test_rmse_t2", 0))
            t3_rmse.append(meta.get("test_rmse_t3", 0))
        print("✅ Done")
    else:
        print("❌ Failed (metadata not found)")

print("\n" + "="*40)
print(f"📊 AVERAGES OVER {RUNS} RUNS")
print("="*40)
print(f"t1 (30-Day) | Acc: {np.mean(t1_accs)*100:.1f}%  |  RMSE: ${np.mean(t1_rmse):.1f}")
print(f"t2 (60-Day) | Acc: {np.mean(t2_accs)*100:.1f}%  |  RMSE: ${np.mean(t2_rmse):.1f}")
print(f"t3 (90-Day) | Acc: {np.mean(t3_accs)*100:.1f}%  |  RMSE: ${np.mean(t3_rmse):.1f}")
print("="*40)