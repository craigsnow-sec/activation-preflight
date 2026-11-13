# These built-in tools read command arguments, read JSON records, and return an exit code.
import argparse
import json
import sys


# Keep file reading in one place so every executor ID receives the same checks.
def read_executor(path):
    # Reading with 'r' lets us inspect the fixture without changing its contents.
    with open(path, "r", encoding="utf-8") as source:
        record = json.load(source)
    # A JSON object is a record of named values; other JSON shapes cannot be permits.
    if not isinstance(record, dict):
        raise ValueError("Expected a JSON object")
    executor = record.get("executor_id")
    # Reject absent, non-text, and blank IDs rather than accidentally accepting them.
    if not isinstance(executor, str) or not executor.strip():
        raise ValueError("Expected a non-empty executor ID")
    return executor


# Put the workflow in a function so importing this file cannot start a check.
def main():
    # Arguments are named command inputs; require all three to avoid hidden defaults.
    parser = argparse.ArgumentParser(description="Check executor identity only; never execute.")
    parser.add_argument("--action", required=True)
    parser.add_argument("--permit", required=True)
    parser.add_argument("--at", required=True, help="Evaluation timestamp; echoed, not validated")
    args = parser.parse_args()
    # Begin with rejection so unreadable or invalid records cannot produce PASS.
    status, reason = "REJECT", "INVALID_INPUT"
    try:
        action_executor = read_executor(args.action)
        permit_executor = read_executor(args.permit)
        # Compare the exact strings; do not silently repair an identity mismatch.
        if action_executor == permit_executor:
            status, reason = "PASS", "EXECUTOR_MATCH"
        else:
            reason = "EXECUTOR_MISMATCH"
    except (OSError, ValueError):
        # File errors, invalid JSON, invalid text encoding, and invalid IDs retain rejection.
        pass
    # Print one machine-readable result; the timestamp is evidence, not an expiry check.
    print(json.dumps({"status": status, "reason": reason, "evaluated_at": args.at}))
    return 0 if status == "PASS" else 1


# This guard runs the CLI only when this file is launched directly.
if __name__ == "__main__":
    sys.exit(main())
