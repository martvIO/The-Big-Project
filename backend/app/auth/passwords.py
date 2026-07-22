from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()

# Precomputed hash of a random value. Verifying a supplied password against THIS
# when the email is unknown makes the unknown-email path do the same argon2 work
# as a real verify — no timing side-channel distinguishing "no such user" from
# "wrong password".
_DUMMY_HASH = _hasher.hash("no-such-account-timing-equalizer")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    return True


def verify_password_dummy(password: str) -> bool:
    verify_password(password, _DUMMY_HASH)
    return False
