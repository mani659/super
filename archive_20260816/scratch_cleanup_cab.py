import os
import shutil

cab_dir = os.path.abspath("cab")
print(f"Cleaning up {cab_dir}...")

files_to_remove = [
    "strategy.py",
    "strategy_2.py",
    "test.py",
    "test_2.py",
    "config_2.py",
    "logger_config_2.py",
    "main_2.py",
    "metrics_2.py",
    "test_health_2.py",
]

for fname in files_to_remove:
    fpath = os.path.join(cab_dir, fname)
    if os.path.exists(fpath):
        os.remove(fpath)
        print(f"  Removed file: {fname}")

# Remove old/ directory if present
old_dir = os.path.join(cab_dir, "old")
if os.path.exists(old_dir):
    shutil.rmtree(old_dir)
    print(f"  Removed legacy directory: old/")

# Clean __pycache__
for root, dirs, files in os.walk(cab_dir):
    for d in dirs:
        if d == "__pycache__":
            p = os.path.join(root, d)
            try:
                shutil.rmtree(p)
                print(f"  Removed pycache: {os.path.relpath(p, cab_dir)}")
            except Exception:
                pass

print("\nFinal active file tree in cab/:")
for root, dirs, files in os.walk(cab_dir):
    rel_root = os.path.relpath(root, cab_dir)
    level = rel_root.count(os.sep)
    indent = "  " * level
    if rel_root == ".":
        print("cab/")
    else:
        print(f"{indent}{os.path.basename(root)}/")
    subindent = "  " * (level + 1)
    for f in sorted(files):
        print(f"{subindent}{f}")
