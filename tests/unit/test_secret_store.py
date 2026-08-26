from lassy.secret_store import fingerprint


def test_secret_fingerprint_is_short_and_stable() -> None:
    assert fingerprint("a" * 32) == "3ba3f5f43b92"
