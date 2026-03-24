def test_unverified_decode_removed():
    from app.core import security

    assert not hasattr(security, "decode_token_without_verification"), (
        "decode_token_without_verification must be removed to prevent misuse"
    )


def test_unverified_decode_not_exported():
    from app import core

    assert not hasattr(core, "decode_token_without_verification"), (
        "decode_token_without_verification should not be exported from app.core"
    )
