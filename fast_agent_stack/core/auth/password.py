"""Password hashing via pwdlib + Argon2id (ADR-030, I18).

Requires: pip install fast-agent-stack[auth-jwt]
"""

try:
    from pwdlib import PasswordHash
    from pwdlib.hashers.argon2 import Argon2Hasher
except ImportError:
    raise ImportError(
        "pwdlib is required for password hashing. "
        "Install it with: pip install fast-agent-stack[auth-jwt]"
    )

# I18: OWASP 2024 minimum parameters for Argon2id
_hasher = PasswordHash(
    [
        Argon2Hasher(
            time_cost=3,
            memory_cost=65536,  # 64 MB
            parallelism=4,
        )
    ]
)


def hash_password(password: str) -> str:
    """Return an Argon2id hash of *password*."""
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> tuple[bool, str | None]:
    """Verify *password* against *hashed*.

    Returns ``(is_valid, new_hash)`` where ``new_hash`` is non-None when the
    stored hash needs re-hashing (parameter upgrade). Callers must persist
    ``new_hash`` on the user record when it is non-None (ADR-030 re-hash policy).
    """
    return _hasher.verify_and_update(password, hashed)
