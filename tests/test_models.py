import pytest
from pydantic import ValidationError

from roboai_stark_client import StarkWidthRequest

VALID = dict(element="S", charge=2, wavelength_a=5606.151, temperature_ev=1.0, ne_cm3=1e17)


def test_valid_request_payload_drops_none():
    payload = StarkWidthRequest(**VALID).api_payload()
    assert payload["wavelength_A"] == 5606.151
    assert payload["temperature_eV"] == 1.0
    assert "low_level_id" not in payload
    assert "temperature_K" not in payload


def test_exactly_one_selector():
    with pytest.raises(ValidationError, match="exactly one transition selector"):
        StarkWidthRequest(**{k: v for k, v in VALID.items() if k != "wavelength_a"})
    with pytest.raises(ValidationError, match="exactly one transition selector"):
        StarkWidthRequest(**VALID, low_level_id="a", upp_level_id="b")


def test_exactly_one_temperature():
    with pytest.raises(ValidationError, match="exactly one of temperature"):
        StarkWidthRequest(**VALID, temperature_k=11600.0)
    with pytest.raises(ValidationError, match="exactly one of temperature"):
        StarkWidthRequest(**{k: v for k, v in VALID.items() if k != "temperature_ev"})


def test_bounds():
    with pytest.raises(ValidationError):
        StarkWidthRequest(**{**VALID, "charge": 0})
    with pytest.raises(ValidationError):
        StarkWidthRequest(**{**VALID, "ne_cm3": -1.0})
