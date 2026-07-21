import pytest

from app.tenancy.slugs import RESERVED_SLUGS, extract_slug, is_valid_slug

BASE = "localtest.me"


class TestIsValidSlug:
    def test_accepts_plain_labels(self) -> None:
        assert is_valid_slug("bella")
        assert is_valid_slug("a1")
        assert is_valid_slug("a-b-c")
        assert is_valid_slug("x" * 63)

    def test_rejects_malformed_labels(self) -> None:
        assert not is_valid_slug("")
        assert not is_valid_slug("-bella")
        assert not is_valid_slug("bella-")
        assert not is_valid_slug("Bella")
        assert not is_valid_slug("bel_la")
        assert not is_valid_slug("bel.la")
        assert not is_valid_slug("x" * 64)

    def test_rejects_reserved_names(self) -> None:
        for reserved in ("www", "admin", "api", "app"):
            assert reserved in RESERVED_SLUGS
            assert not is_valid_slug(reserved)


class TestExtractSlug:
    @pytest.mark.parametrize(
        ("host", "expected"),
        [
            ("bella.localtest.me", "bella"),
            ("bella.localtest.me:8000", "bella"),
            ("BELLA.LOCALTEST.ME:8443", "bella"),
            ("bella.localtest.me.", "bella"),
        ],
    )
    def test_extracts_single_label(self, host: str, expected: str) -> None:
        assert extract_slug(host, BASE) == expected

    @pytest.mark.parametrize(
        "host",
        [
            None,
            "",
            "localtest.me",  # apex — no label
            "a.b.localtest.me",  # deeper nesting
            "bella.other.com",  # foreign domain
            "bellalocaltest.me",  # suffix without dot boundary
            "localhost:8000",
            "127.0.0.1:8000",
            "[::1]:8000",  # IPv6 literal
        ],
    )
    def test_fails_closed_on_everything_else(self, host: str | None) -> None:
        assert extract_slug(host, BASE) is None

    def test_base_domain_case_insensitive(self) -> None:
        assert extract_slug("bella.localtest.me", "LOCALTEST.ME") == "bella"
