"""License validation — encrypted license.key file."""

import base64
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def _get_fernet(secret: str) -> Fernet:
    key = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def generate_license(secret: str, client_name: str, expiry: date) -> str:
    """Produce a license token string. Call this on your dev machine only."""
    payload = json.dumps({
        "client": client_name,
        "expiry": expiry.isoformat(),
    }).encode()
    return _get_fernet(secret).encrypt(payload).decode()


def check_license(secret: str, license_path: Path) -> None:
    """Validate license on startup. Calls sys.exit if invalid or expired."""
    if not license_path.exists():
        print("=" * 55)
        print("  LICENSE ERROR: license.key not found.")
        print(f"  Expected at: {license_path}")
        print("  Contact your vendor to obtain a license file.")
        print("=" * 55)
        sys.exit(1)

    try:
        token = license_path.read_bytes().strip()
        payload = json.loads(_get_fernet(secret).decrypt(token))
    except (InvalidToken, Exception):
        print("=" * 55)
        print("  LICENSE ERROR: license.key is invalid or tampered.")
        print("  Contact your vendor for a valid license file.")
        print("=" * 55)
        sys.exit(1)

    expiry = date.fromisoformat(payload["expiry"])
    client = payload.get("client", "Unknown")

    if date.today() > expiry:
        print("=" * 55)
        print(f"  LICENSE EXPIRED")
        print(f"  Client : {client}")
        print(f"  Expired: {expiry.strftime('%d %b %Y')}")
        print("  Contact your vendor to renew your license.")
        print("=" * 55)
        sys.exit(1)

    days_left = (expiry - date.today()).days
    print(f"License OK | Client: {client} | Expires: {expiry.strftime('%d %b %Y')} ({days_left} days left)")
