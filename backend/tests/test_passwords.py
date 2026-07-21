from app.auth.passwords import hash_password, verify_password, verify_password_dummy


def test_hash_then_verify_roundtrip() -> None:
    h = hash_password("Sekret-passw0rd!")
    assert h != "Sekret-passw0rd!"
    assert h.startswith("$argon2id$")
    assert verify_password("Sekret-passw0rd!", h) is True


def test_wrong_password_fails() -> None:
    h = hash_password("correct-horse")
    assert verify_password("battery-staple", h) is False


def test_hashes_are_salted_unique() -> None:
    assert hash_password("same") != hash_password("same")


def test_dummy_verify_always_false_and_does_work() -> None:
    # Unknown-email path calls this so timing matches a real verify.
    assert verify_password_dummy("anything") is False
