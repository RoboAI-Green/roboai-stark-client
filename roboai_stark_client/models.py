"""Request and response models for the RoboAI Stark width API.

The response mirrors the server's full calculation trace: the resolved target
line, plasma block, per-side term summaries, every explicit Δn=0 perturbing
line with its oscillator-strength provenance, the front factor, and the
method-domain reliability block — everything needed to audit how a width was
computed, not just the number.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class StarkWidthRequest(BaseModel):
    """One Stark-width request.

    Select the transition with either ``wavelength_a`` (nearest ASD line within
    ``wavelength_tol_a``) or a ``low_level_id``/``upp_level_id`` pair from
    :meth:`RoboAIStarkClient.search_levels`. Give exactly one temperature,
    ``temperature_ev`` or ``temperature_k``.
    """

    element: str = Field(min_length=1)
    charge: int = Field(ge=1, description="Spectroscopic charge: 1 = neutral (I), 2 = singly ionised (II)")

    wavelength_a: float | None = Field(default=None, gt=0, description="Transition wavelength in Å")
    wavelength_tol_a: float = Field(default=0.05, gt=0)
    low_level_id: str | None = None
    upp_level_id: str | None = None

    temperature_ev: float | None = Field(default=None, gt=0)
    temperature_k: float | None = Field(default=None, gt=0)
    ne_cm3: float = Field(gt=0, description="Electron density in cm⁻³")

    same_core_only: bool = True

    @model_validator(mode="after")
    def _one_selector_one_temperature(self) -> "StarkWidthRequest":
        selectors = (
            self.wavelength_a is not None,
            bool(self.low_level_id and self.upp_level_id),
        )
        if sum(selectors) != 1:
            raise ValueError(
                "provide exactly one transition selector: wavelength_a, "
                "or both low_level_id and upp_level_id"
            )
        if (self.temperature_ev is None) == (self.temperature_k is None):
            raise ValueError("provide exactly one of temperature_ev or temperature_k")
        return self

    _API_NAMES = {
        "wavelength_a": "wavelength_A",
        "wavelength_tol_a": "wavelength_tol_A",
        "temperature_ev": "temperature_eV",
        "temperature_k": "temperature_K",
    }

    def api_payload(self) -> dict[str, Any]:
        payload = self.model_dump(exclude_none=True)
        return {self._API_NAMES.get(key, key): value for key, value in payload.items()}


class LevelSearchRequest(BaseModel):
    element: str = Field(min_length=1)
    charge: int = Field(ge=1)
    query: str = Field(min_length=1, description="Configuration / term / J text, fuzzy-matched")
    max_results: int = Field(default=30, ge=1, le=200)

    def api_payload(self) -> dict[str, Any]:
        return self.model_dump()


# ---------------------------------------------------------------- responses
class Level(BaseModel):
    level_id: str
    element: str
    spectr_charge: int
    energy_cm1: float
    conf: str
    term: str
    j: str
    g: float | None = None
    core: str = ""
    n: int | None = None
    l: int | None = None  # noqa: E741 — orbital quantum number, standard notation
    nl: str = ""

    def label(self) -> str:
        parts = [self.conf, self.term, f"J={self.j}" if self.j else ""]
        return " ".join(part for part in parts if part)


class Target(BaseModel):
    line_id: str
    element: str
    ion: str
    spectr_charge: int
    wavelength_A: float
    wavelength_nm: float
    lower: Level
    upper: Level
    ionization_energy_cm1: float


class Plasma(BaseModel):
    temperature_K: float
    temperature_eV: float
    electron_density_cm3: float
    kT_cm1: float
    same_core_only: bool


class SideSummary(BaseModel):
    level_id: str
    label: str
    energy_cm1: float
    n: int | None = None
    l: int | None = None  # noqa: E741
    n_star: float | None = None
    explicit_sum: float
    explicit_sum_low: float
    explicit_sum_high: float
    lumped_r2: float | None = None
    lumped_gaunt_x: float | None = None
    lumped_gaunt: float | None = None
    lumped_sum: float
    perturber_count: int
    used_perturber_count: int
    skipped_perturber_count: int


class Perturber(BaseModel):
    side: str
    reference_level_id: str
    perturber_level_id: str
    perturber_label: str
    perturber_energy_cm1: float
    transition_low: dict[str, Any]
    transition_upper: dict[str, Any]
    delta_e_cm1: float
    gaunt_x: float
    gaunt: float
    transition_line_id: str | None = None
    f: float | None = None
    f_low: float | None = None
    f_high: float | None = None
    f_source: str
    f_provider: str
    f_confidence: str
    f_method: str
    f_details: str | None = None
    r2: float | None = None
    contribution: float
    contribution_low: float
    contribution_high: float


class Benchmark(BaseModel):
    """Per-charge accuracy of the method vs the STARK-B SCP database."""

    median_ratio: float
    within_factor2_pct: float
    n: int
    scope: str


class Reliability(BaseModel):
    """Method-domain confidence, orthogonal to the per-line data provenance.

    ``confidence`` (high/medium/low) follows the emitter charge (MSE is
    ion-only and charge-dependent) and the lumped share of the width (widths
    dominated by the lumped Δn≠0 approximation underestimate). ``flags`` are
    machine-readable: ``neutral_out_of_domain``, ``high_charge_underestimate``,
    ``lumped_dominated``, ``unvalidated_charge``.
    """

    confidence: str
    domain: str
    charge_class: str
    benchmark: Benchmark | None = None
    lumped_share: float | None = None
    flags: list[str] = []
    notes: list[str] = []


class StarkWidthResult(BaseModel):
    """Full calculation trace for one line."""

    target: Target
    plasma: Plasma
    low_side: SideSummary
    upp_side: SideSummary
    s_total: float
    s_total_low: float
    s_total_high: float
    c_front: float
    fwhm_nm: float
    fwhm_low_nm: float
    fwhm_high_nm: float
    hwhm_nm: float
    hwhm_low_nm: float
    hwhm_high_nm: float
    reliability: Reliability
    perturbing_lines: list[Perturber] = []

    def summary(self) -> str:
        """One-paragraph human-readable summary of the result."""
        rel = self.reliability
        lines = [
            f"{self.target.ion} {self.target.wavelength_A:.4f} Å "
            f"({self.target.lower.label()} → {self.target.upper.label()})",
            f"FWHM = {self.fwhm_nm:.5g} nm  [{self.fwhm_low_nm:.5g}, {self.fwhm_high_nm:.5g}]  "
            f"(HWHM {self.hwhm_nm:.5g} nm)",
            f"reliability: {rel.confidence.upper()} — {rel.domain}"
            + (f"; lumped share {rel.lumped_share:.0%}" if rel.lumped_share is not None else ""),
        ]
        if rel.flags:
            lines.append(f"flags: {', '.join(rel.flags)}")
        if rel.benchmark:
            lines.append(
                f"benchmark ({rel.charge_class}): median W_MSE/W_SCP = "
                f"{rel.benchmark.median_ratio:.2f}, "
                f"{rel.benchmark.within_factor2_pct:.0f}% within ×2 (n={rel.benchmark.n})"
            )
        return "\n".join(lines)


class LevelSearchResult(BaseModel):
    levels: list[Level] = []
