# check_leakage.py — does the model memorize trajectories or learn physics?
import sys, pandas as pd, numpy as np
from sklearn.metrics import f1_score, accuracy_score
import lightgbm as lgb

sys.path.insert(0, "services/ai")
from preprocessing import load_data, FEATURES

df = load_data("services/ai/dtx_ai_master_dataset.csv")
X, y = df[FEATURES], df["fault_label"]

# Approach 1 — standard stratified split (what the notebook does)
from sklearn.model_selection import train_test_split
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
m1 = lgb.LGBMClassifier(n_estimators=200, max_depth=5, learning_rate=0.1,
                         class_weight="balanced", verbose=-1, random_state=42)
m1.fit(Xtr, ytr)
print(f"Stratified random split: F1={f1_score(yte, m1.predict(Xte), average='macro'):.4f}")

# Approach 2 — temporal/block split (no trajectory mixing across train/test)
# If rows are grouped by class in blocks, this prevents within-class trajectory leak.
n = len(df)
split_idx = int(n * 0.8)
Xtr, Xte = X.iloc[:split_idx], X.iloc[split_idx:]
ytr, yte = y.iloc[:split_idx], y.iloc[split_idx:]
m2 = lgb.LGBMClassifier(n_estimators=200, max_depth=5, learning_rate=0.1,
                         class_weight="balanced", verbose=-1, random_state=42)
m2.fit(Xtr, ytr)
print(f"Temporal block split    : F1={f1_score(yte, m2.predict(Xte), average='macro'):.4f}")

# Approach 3 — shuffle labels and run stratified. F1 should drop to ~1/6 = 0.17.
# If it's significantly higher, the model is learning row-order noise.
y_shuffled = pd.Series(np.random.RandomState(0).permutation(y.values), index=y.index)
Xtr, Xte, ytr, yte = train_test_split(X, y_shuffled, test_size=0.2, stratify=y_shuffled, random_state=42)
m3 = lgb.LGBMClassifier(n_estimators=200, max_depth=5, learning_rate=0.1,
                         class_weight="balanced", verbose=-1, random_state=42)
m3.fit(Xtr, ytr)
print(f"Shuffled labels (sanity): F1={f1_score(yte, m3.predict(Xte), average='macro'):.4f}")