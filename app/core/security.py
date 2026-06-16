from datetime import UTC, datetime, timedelta
import hashlib
import secrets

from app.core.config import get_settings


def hash_password(password: str) -> str:
    iterations = 600000
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, digest = password_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    computed_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations_text),
    ).hex()

    return secrets.compare_digest(computed_digest, digest)


def create_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    settings = get_settings()
    return hashlib.sha256(f"{settings.session_secret_key}:{token}".encode("utf-8")).hexdigest()


def get_session_expiration() -> datetime:
    settings = get_settings()
    return datetime.now(UTC) + timedelta(days=settings.session_expire_days)
