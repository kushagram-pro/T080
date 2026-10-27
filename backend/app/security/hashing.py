import bcrypt

# NFR-006: passwords are never stored in plaintext.
# bcrypt is used directly; passlib 1.7.4 is unmaintained and breaks on bcrypt >= 4.1.

BCRYPT_MAX_BYTES = 72  # bcrypt ignores/rejects anything beyond this; schemas must enforce it


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")
    if len(pw) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes")
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Over-length password or malformed hash: treat as a failed match
        return False


# Used when the email is unknown so login takes the same time either way.
# FR-003: a failed login must not reveal whether the email or password was wrong.
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


def verify_against_dummy(password: str) -> bool:
    verify_password(password, _DUMMY_HASH)
    return False
