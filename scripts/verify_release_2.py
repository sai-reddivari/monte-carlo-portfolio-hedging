"""Compatibility command for frozen-bundle verification; never overwrites historical reports."""
from verify_frozen_bundle import verify
if __name__ == '__main__':
    raise SystemExit(0 if verify()['passed'] else 1)
