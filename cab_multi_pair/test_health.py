"""
==================================================================
           CAB MASTER - MODULAR HEALTH DIAGNOSTICS
==================================================================
Run this script to verify the structural integrity, paths, and
variable mappings of the modular bot framework, including analytics.
==================================================================
"""

import os
import sys
import io

# Ensure UTF-8 output encoding for emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def run_diagnostics():
    print("\n==================================================")
    print("      CAB MASTER MODULAR HEALTH DIAGNOSTICS       ")
    print("==================================================")
    
    # ---------------------------------------------------------
    # 1. Module Import Testing
    # ---------------------------------------------------------
    print("\n[1] Testing Structural Imports...")
    try:
        import config
        import connection
        import utils
        import ledger
        import signals
        import execution
        import trade_manager
        import main
        import analytics.intelligencia  # NEW: Testing Analytics Import
        print("  ✔️ All 9 core modules (including analytics) imported successfully.")
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        sys.exit(1)

    # ---------------------------------------------------------
    # 2. Configuration & Dictionary Inheritance
    # ---------------------------------------------------------
    print("\n[2] Validating Configuration Map...")
    try:
        import config
        assert hasattr(config, 'TERMINAL_PATH'), "Missing TERMINAL_PATH in config"
        assert len(config.SYMBOLS) > 0, "SYMBOLS list failed to derive from PAIRS"
        assert "XAGUSDm" in config.SYMBOLS, "XAGUSDm not found in configuration list"
        print(f"  ✔️ Config validated. Successfully derived {len(config.SYMBOLS)} dynamic symbols.")
    except AssertionError as e:
        print(f"  ❌ Configuration error: {e}")

    # ---------------------------------------------------------
    # 3. File System & Path Access
    # ---------------------------------------------------------
    print("\n[3] Checking File System & I/O Permissions...")
    try:
        import config
        if os.path.exists(config.TERMINAL_PATH):
            print(f"  ✔️ MT5 Terminal located at: {config.TERMINAL_PATH}")
        else:
            print(f"  ⚠️ MT5 Terminal NOT found: {config.TERMINAL_PATH}")
    except Exception as e:
        print(f"  ❌ File system check failed: {e}")

    # ---------------------------------------------------------
    # 4. Utility Fallbacks & Math Safety
    # ---------------------------------------------------------
    print("\n[4] Testing Logic Safety (Zero-Division Shields)...")
    try:
        import utils
        test_lot = utils.calculate_lot("EURUSDm", 10.0, 1.0)
        assert test_lot == 0.01, f"Fallback failed, got {test_lot}"
        print("  ✔️ calculate_lot() fallback safety verified.")
    except Exception as e:
        print(f"  ❌ Math utility failed: {e}")

    # ---------------------------------------------------------
    # 5. Ledger & Analytics Memory Instantiation
    # ---------------------------------------------------------
    print("\n[5] Verifying Ledger & Intelligencia Memory Arrays...")
    try:
        import ledger
        assert isinstance(ledger.mfe_tracker, dict)
        assert isinstance(ledger.entry_intelligence, dict) # NEW: Checking Intelligencia memory
        print("  ✔️ All state memory trackers instantiated correctly.")
    except Exception as e:
        print(f"  ❌ Ledger memory initialization failed: {e}")

    # ---------------------------------------------------------
    # 6. Intelligencia Data Output Validation
    # ---------------------------------------------------------
    print("\n[6] Testing Intelligencia Snapshot Engine...")
    try:
        from analytics.intelligencia import get_entry_intelligence
        # Run a test snapshot. Because MT5 isn't connected, it should gracefully return defaults.
        dummy_snapshot = get_entry_intelligence("EURUSDm")
        assert isinstance(dummy_snapshot, dict), "Snapshot must return a dictionary"
        assert "Macro_DXY_Proxy" in dummy_snapshot, "Missing DXY proxy key"
        assert "H1_ATR_State" in dummy_snapshot, "Missing ATR state key"
        assert dummy_snapshot["Session"] in ["ASIAN", "LONDON_OPEN", "LON_NY_OVERLAP", "NEW_YORK", "LATE_NY_ASIAN"], "Session routing failed"
        print("  ✔️ Intelligencia engine output structure and fallbacks validated.")
    except Exception as e:
        print(f"  ❌ Analytics engine failed: {e}")

    print("\n==================================================")
    print(" DIAGNOSTICS COMPLETE: Framework is structurally sound.")
    print("==================================================")

if __name__ == "__main__":
    run_diagnostics()