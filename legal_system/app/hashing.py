"""
Cryptographic SHA-256 Hashing & Evidence Integrity Engine.

Provides mathematically verifiable tamper detection, SHA-256 fingerprinting,
and chain-of-custody cryptographic validation for legal exhibits.
"""

import hashlib
import os
from pathlib import Path
from typing import Dict, Any


def compute_sha256(data: bytes) -> str:
    """Compute the hexadecimal SHA-256 hash of raw byte data."""
    hasher = hashlib.sha256()
    hasher.update(data)
    return hasher.hexdigest().lower()


def compute_file_sha256(filepath: str | Path) -> str:
    """Stream a file from disk in chunks and compute its SHA-256 hash."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Evidence file not found: {filepath}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def verify_file_integrity(filepath: str | Path, expected_hash: str) -> Dict[str, Any]:
    """
    Verify whether the on-disk evidence file matches the immutable expected SHA-256 hash.

    Returns:
        dict: {
            "is_valid": bool,
            "expected_hash": str,
            "current_hash": str,
            "matches": bool,
            "file_exists": bool,
            "status_badge": "VERIFIED_GREEN" | "TAMPERED_RED"
        }
    """
    path = Path(filepath)
    if not path.exists():
        return {
            "is_valid": False,
            "expected_hash": expected_hash.lower(),
            "current_hash": None,
            "matches": False,
            "file_exists": False,
            "status_badge": "MISSING_RED",
            "message": "Physical evidence file is missing from secure storage vault.",
        }

    current_hash = compute_file_sha256(path)
    is_match = (current_hash == expected_hash.lower())

    return {
        "is_valid": is_match,
        "expected_hash": expected_hash.lower(),
        "current_hash": current_hash,
        "matches": is_match,
        "file_exists": True,
        "status_badge": "VERIFIED_GREEN" if is_match else "TAMPERED_RED",
        "message": (
            "Cryptographic seal matches canonical record. Chain of custody intact."
            if is_match
            else "CRITICAL ALERT: File hash mismatch! Unauthorized modification detected."
        ),
    }


def simulate_file_tamper(filepath: str | Path) -> str:
    """
    Simulate intentional or unauthorized tampering by appending a byte sequence.
    Returns the new corrupt SHA-256 hash.
    """
    path = Path(filepath)
    with open(path, "ab") as f:
        f.write(b"\n[UNAUTHORIZED_MODIFICATION_DETECTED_BY_HASH_VALIDATOR]")
    return compute_file_sha256(path)


def restore_file_content(filepath: str | Path, canonical_bytes: bytes) -> str:
    """Restore file content to its canonical state, restoring valid hash."""
    path = Path(filepath)
    with open(path, "wb") as f:
        f.write(canonical_bytes)
    return compute_file_sha256(path)
