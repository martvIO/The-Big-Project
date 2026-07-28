import pytest

from app.errors import DomainValidationError
from app.notifications.validation import (
    OTP_CODE_LENGTH,
    OTP_MAX_VERIFY_ATTEMPTS,
    OTP_TTL_SECONDS,
    VERIFICATION_TOKEN_TTL_SECONDS,
    generate_otp_code,
    mask_otp_body,
    normalize_israeli_mobile,
    otp_sms_body,
)


class TestNormalizeIsraeliMobile:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("0501234567", "+972501234567"),
            ("050-123-4567", "+972501234567"),
            ("050 123 4567", "+972501234567"),
            ("(050) 1234567", "+972501234567"),
            ("+972501234567", "+972501234567"),
            ("+972 50-123-4567", "+972501234567"),
            ("972501234567", "+972501234567"),
            ("0521234567", "+972521234567"),
            ("0581234567", "+972581234567"),
        ],
    )
    def test_normalizes_accepted_formats(self, raw: str, expected: str) -> None:
        assert normalize_israeli_mobile(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "   ",
            "031234567",  # landline
            "+97231234567",  # landline via country code
            "12345",  # too short
            "05012345678",  # too long
            "050123456",  # too short mobile
            "+15551234567",  # foreign
            "abc0501234567",  # junk charset
            "0501234567;drop",  # junk charset
            "9720501234567",  # 972 followed by the leading zero
            "++972501234567",  # double plus
            "05a1234567",  # letter inside
        ],
    )
    def test_rejects_everything_else(self, raw: str) -> None:
        with pytest.raises(DomainValidationError):
            normalize_israeli_mobile(raw)


class TestOtpCode:
    def test_shape(self) -> None:
        code = generate_otp_code()
        assert len(code) == OTP_CODE_LENGTH
        assert code.isdigit()

    def test_zero_padding_preserved(self) -> None:
        # 2000 draws make an unpadded short code overwhelmingly likely to appear
        # if padding were broken (P(no <100000 draw) ≈ 0.9^2000 ≈ 10^-92).
        codes = {generate_otp_code() for _ in range(2000)}
        assert all(len(code) == OTP_CODE_LENGTH for code in codes)
        assert len(codes) > 1  # not constant


class TestBodies:
    def test_otp_sms_body_contains_the_code(self) -> None:
        body = otp_sms_body("123456")
        assert "123456" in body

    def test_mask_hides_the_code_but_keeps_the_shape(self) -> None:
        body = otp_sms_body("123456")
        masked = mask_otp_body(body, "123456")
        assert "123456" not in masked
        assert masked != body
        assert len(masked) >= len(body) - OTP_CODE_LENGTH

    def test_mask_without_occurrence_is_identity(self) -> None:
        assert mask_otp_body("no code here", "123456") == "no code here"


class TestConstants:
    def test_epic_bounds(self) -> None:
        assert OTP_TTL_SECONDS <= 300  # epic: ≤ 5 minutes
        assert OTP_MAX_VERIFY_ATTEMPTS == 5
        assert VERIFICATION_TOKEN_TTL_SECONDS == 600
