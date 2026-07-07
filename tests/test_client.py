import json

import httpx
import pytest

from roboai_stark_client import (
    RoboAIStarkAPIError,
    RoboAIStarkClient,
    StarkWidthRequest,
)

LEVEL = {
    "level_id": "016002.000029",
    "element": "S",
    "spectr_charge": 2,
    "energy_cm1": 110766.59,
    "conf": "3s2.3p2.(3P).3d",
    "term": "4F",
    "j": "9/2",
    "g": 10.0,
    "core": "3s2.3p2.(3p)",
    "n": 3,
    "l": 2,
    "nl": "3d",
}

SIDE = {
    "level_id": "016002.000029",
    "label": "3s2.3p2.(3P).3d 4F J=9/2",
    "energy_cm1": 110766.59,
    "n": 3,
    "l": 2,
    "n_star": 2.38,
    "explicit_sum": 3.86,
    "explicit_sum_low": 3.8,
    "explicit_sum_high": 3.95,
    "lumped_r2": 12.28,
    "lumped_gaunt_x": 0.42,
    "lumped_gaunt": 0.2,
    "lumped_sum": 2.46,
    "perturber_count": 6,
    "used_perturber_count": 4,
    "skipped_perturber_count": 2,
}

RESULT = {
    "target": {
        "line_id": "9874",
        "element": "S",
        "ion": "S II",
        "spectr_charge": 2,
        "wavelength_A": 5606.151,
        "wavelength_nm": 560.6151,
        "lower": LEVEL,
        "upper": {**LEVEL, "level_id": "016002.000047", "conf": "3s2.3p2.(3P).4p"},
        "ionization_energy_cm1": 188232.7,
    },
    "plasma": {
        "temperature_K": 11604.5,
        "temperature_eV": 1.0,
        "electron_density_cm3": 1e17,
        "kT_cm1": 8065.5,
        "same_core_only": True,
    },
    "low_side": SIDE,
    "upp_side": SIDE,
    "s_total": 12.36,
    "s_total_low": 12.3,
    "s_total_high": 12.6,
    "c_front": 6.46e-27,
    "fwhm_nm": 0.07986,
    "fwhm_low_nm": 0.07956,
    "fwhm_high_nm": 0.08136,
    "hwhm_nm": 0.03993,
    "hwhm_low_nm": 0.03978,
    "hwhm_high_nm": 0.04068,
    "reliability": {
        "confidence": "high",
        "domain": "singly/doubly ionized — validated MSE domain",
        "charge_class": "II",
        "benchmark": {
            "median_ratio": 1.16,
            "within_factor2_pct": 72.0,
            "n": 107,
            "scope": "vs StarkB SCP, optical 2000-9000 A",
        },
        "lumped_share": 0.38,
        "flags": [],
        "notes": [],
    },
    "perturbing_lines": [],
}


def make_client(handler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return RoboAIStarkClient(
        base_url="https://example.test", api_key="tok_test", http_client=http_client
    )


def test_compute_width_sends_payload_and_parses_trace():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/stark/width"
        assert request.headers["Authorization"] == "Bearer tok_test"
        seen.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=RESULT)

    client = make_client(handler)
    result = client.compute_width(
        element="S", charge=2, wavelength_a=5606.151, temperature_ev=1.0, ne_cm3=1e17
    )

    assert seen["element"] == "S"
    assert seen["charge"] == 2
    assert seen["wavelength_A"] == 5606.151
    assert seen["same_core_only"] is True
    assert seen["temperature_eV"] == 1.0
    assert "temperature_K" not in seen

    assert result.fwhm_nm == pytest.approx(0.07986)
    assert result.target.ion == "S II"
    assert result.reliability.confidence == "high"
    assert result.reliability.benchmark.n == 107
    assert result.low_side.explicit_sum == pytest.approx(3.86)
    assert "S II" in result.summary()
    assert "HIGH" in result.summary()


def test_compute_width_by_level_pair():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["low_level_id"] == "016002.000029"
        assert payload["upp_level_id"] == "016002.000047"
        assert "wavelength_A" not in payload
        assert payload["temperature_K"] == 11600.0
        return httpx.Response(200, json=RESULT)

    client = make_client(handler)
    request = StarkWidthRequest(
        element="S",
        charge=2,
        low_level_id="016002.000029",
        upp_level_id="016002.000047",
        temperature_k=11600.0,
        ne_cm3=1e17,
    )
    assert client.compute_width(request).hwhm_nm == pytest.approx(0.03993)


def test_api_error_surfaces_detail():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404, json={"detail": "No S charge=2 line within 0.05 A of 9999.0 A."}
        )

    client = make_client(handler)
    with pytest.raises(RoboAIStarkAPIError, match="No S charge=2 line"):
        client.compute_width(
            element="S", charge=2, wavelength_a=9999.0, temperature_ev=1.0, ne_cm3=1e17
        )


def test_search_levels():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/stark/levels"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["query"] == "3s2 3p2 3d 4F"
        return httpx.Response(200, json={"levels": [LEVEL]})

    client = make_client(handler)
    levels = client.search_levels(element="S", charge=2, query="3s2 3p2 3d 4F")
    assert len(levels) == 1
    assert levels[0].level_id == "016002.000029"
    assert "4F" in levels[0].label()


def test_request_and_kwargs_are_mutually_exclusive():
    client = make_client(lambda request: httpx.Response(200, json=RESULT))
    request = StarkWidthRequest(
        element="S", charge=2, wavelength_a=5606.151, temperature_ev=1.0, ne_cm3=1e17
    )
    with pytest.raises(TypeError):
        client.compute_width(request, element="O")
