from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from .auth import load_stored_api_key, save_api_key, token_from_env
from .errors import RoboAIStarkAPIError
from .models import (
    Level,
    LevelSearchRequest,
    LevelSearchResult,
    StarkWidthRequest,
    StarkWidthResult,
)

DEFAULT_BASE_URL = "https://libs.roboai.fi/api"


class RoboAIStarkClient:
    """Synchronous Python client for the RoboAI Stark-width API.

    Computes electron-impact Stark FWHM values with the modified semi-empirical
    method (Dimitrijević & Konjević 1980) on the hosted NIST-ASD-backed engine,
    returning the full calculation trace (perturbing lines with oscillator-
    strength provenance, per-side term sums, reliability assessment).

    Authentication is shared with ``roboai-libs-client``: one platform token
    (``roboai-stark auth login`` or ``roboai-libs auth login``) serves both.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_key: str | None = None,
        timeout: float | httpx.Timeout = 60.0,
        http_client: httpx.Client | None = None,
    ):
        resolved_base_url = base_url or os.getenv("ROBOAI_LIBS_BASE_URL") or DEFAULT_BASE_URL
        self.base_url = resolved_base_url.rstrip("/")
        self.api_key = api_key or token_from_env() or load_stored_api_key()
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "RoboAIStarkClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ------------------------------------------------------------- plumbing
    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        merged_headers = {**self._headers(), **headers}
        response = self._client.request(method, url, headers=merged_headers, **kwargs)

        if response.status_code >= 400:
            message = response.text
            try:
                detail = response.json().get("detail")
                if detail:
                    message = str(detail)
            except ValueError:
                pass
            raise RoboAIStarkAPIError(
                response.status_code,
                message,
                response_text=response.text,
            )

        return response

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request("POST", path, json=payload)
        return response.json()

    # ----------------------------------------------------------------- auth
    def get_token_info(self) -> dict[str, Any]:
        return dict(self._request("GET", "/v1/auth/token").json())

    def request_login_otp(self, email: str) -> None:
        self._request("POST", "/v1/auth/otp", json={"email": email})

    def save_authenticated_token(self) -> Path:
        self.get_token_info()
        return save_api_key(self.api_key)

    # ---------------------------------------------------------------- stark
    def compute_width(
        self,
        request: StarkWidthRequest | None = None,
        **kwargs: Any,
    ) -> StarkWidthResult:
        """Compute the Stark FWHM for one line; returns the full trace.

        Either pass a :class:`StarkWidthRequest`, or the same fields as
        keywords::

            client.compute_width(
                element="S", charge=2, wavelength_a=5606.151,
                temperature_ev=1.0, ne_cm3=1e17,
            )
        """
        if request is None:
            request = StarkWidthRequest(**kwargs)
        elif kwargs:
            raise TypeError("Pass either a request or keyword fields, not both.")
        data = self._post_json("/v1/stark/width", request.api_payload())
        return StarkWidthResult.model_validate(data)

    def search_levels(
        self,
        request: LevelSearchRequest | None = None,
        **kwargs: Any,
    ) -> list[Level]:
        """Fuzzy level lookup by configuration / term / J text for one ion.

        Matching ignores dots, spaces, and punctuation, so ``"3s2 3p2 3d 4F"``
        matches ``3s2.3p2.(3P).3d 4F``. Use the returned ``level_id`` values as
        ``low_level_id``/``upp_level_id`` in :meth:`compute_width`.
        """
        if request is None:
            request = LevelSearchRequest(**kwargs)
        elif kwargs:
            raise TypeError("Pass either a request or keyword fields, not both.")
        data = self._post_json("/v1/stark/levels", request.api_payload())
        return LevelSearchResult.model_validate(data).levels
