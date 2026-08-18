def get_decimals(step):
    step_str = f"{step:.10f}".rstrip("0")
    return len(step_str.split(".")[1]) if "." in step_str else 0

for step in [0.01, 0.1, 1.0, 0.05, 0.5, 0.25]:
    print(f"step={step} -> decimals={get_decimals(step)}")
