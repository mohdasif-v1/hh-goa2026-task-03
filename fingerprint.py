import hashlib
import json

def canonicalize(content: dict) -> str:
    """Canonicalization rule: keys sorted alphabetically, no extraneous whitespace, UTF-8 encoded string output.
    Per TRD Section 3.4 & 4.4.
    """
    return json.dumps(content, sort_keys=True, separators=(",", ":"))

def fingerprint(content: dict) -> str:
    """Computes SHA-256 hex string of canonicalized JSON representation."""
    canonical_str = canonicalize(content)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
