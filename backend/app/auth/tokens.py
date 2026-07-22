import hashlib
import secrets

TOKEN_BYTES = 32  # 256 bits


def generate_session_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    # Session tokens are high-entropy random values, so a fast one-way hash is
    # the right tool — only hashes are stored, and a DB leak can't recover tokens.
    return hashlib.sha256(token.encode()).hexdigest()
