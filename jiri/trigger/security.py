import hashlib
import hmac
import secrets


def verify_github_signature(body: bytes, secret: str, signature_header: str | None) -> bool:
    """Validate GitHub ``X-Hub-Signature-256`` (``sha256=...``)."""
    if not secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    digest = signature_header.removeprefix("sha256=")
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    expected = mac.hexdigest()
    return hmac.compare_digest(expected, digest)


def verify_jiri_secret(secret: str, header_value: str | None) -> bool:
    """Optional shared secret for agent-to-agent calls (``X-Jiri-Secret``)."""
    if not secret:
        return True
    if not header_value:
        return False
    return secrets.compare_digest(secret, header_value)
