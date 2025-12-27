"""
Quick test to verify validate_and_log_setup_status function works correctly.
Run this to see debug output and validation behavior.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.workers.setup_worker import validate_and_log_setup_status

def test_validation():
    print("=" * 60)
    print("Testing setup_status validation")
    print("=" * 60)
    
    # Test cases
    test_cases = [
        ("done", "success_case"),
        ("active", "in_progress_case"),
        ("pending", "pending_case"),
        ("failed", "error_case"),
        ("completed", "legacy_completed"),  # Should coerce to "done"
        ("in_progress", "legacy_in_progress"),  # Should coerce to "active"
        ("invalid_status", "unknown_value"),  # Should coerce based on context
        ("DONE", "uppercase_test"),  # Should normalize to lowercase
    ]
    
    for status, context in test_cases:
        print(f"\n{'─' * 60}")
        result = validate_and_log_setup_status(status, context)
        print(f"✓ Result: {repr(result)}")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_validation()
