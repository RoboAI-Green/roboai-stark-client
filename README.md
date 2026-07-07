# RoboAI Stark Client

[![PyPI version](https://img.shields.io/pypi/v/roboai-stark-client.svg)](https://pypi.org/project/roboai-stark-client/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Lightweight Python client SDK and command-line helper for the RoboAI
Stark-width API: electron-impact Stark broadening of isolated ion lines,
computed with the modified semi-empirical method (Dimitrijević & Konjević
1980) on a NIST-ASD-backed engine — returning not just the width, but the
**full calculation trace** (every perturbing line with its oscillator-strength
provenance) and a **validated reliability assessment** for each result.

## Contents

- [Install](#install)
- [Quick Start](#quick-start)
- [Authentication](#authentication)
- [Usage Examples](#usage-examples)
- [What You Get Back](#what-you-get-back)
- [Reliability](#reliability)
- [Scientific Scope](#scientific-scope)
- [Support](#support)
- [License](#license)

## Install

Prerequisite: Python 3.10 or newer.

From PyPI:

```bash
pip install --upgrade roboai-stark-client
```

From GitHub, if you need the latest repository version:

```bash
pip install git+https://github.com/RoboAI-Green/roboai-stark-client.git
```

## Quick Start

Authenticate once:

```bash
roboai-stark auth login
```

Compute a first width from Python:

```python
from roboai_stark_client import RoboAIStarkClient

client = RoboAIStarkClient()

result = client.compute_width(
    element="S",            # element symbol
    charge=2,               # spectroscopic charge: 2 = singly ionised (S II)
    wavelength_a=5606.151,  # transition wavelength in Å (nearest ASD line)
    temperature_ev=1.0,     # electron temperature in eV (≈ 11 605 K)
    ne_cm3=1e17,            # electron density in cm⁻³
)

print(result.fwhm_nm)              # 0.07986  (nm, FWHM)
print(result.reliability.confidence)  # "high"
print(result.summary())
```

Or from the command line:

```bash
roboai-stark width --element S --charge 2 --wavelength-a 5606.151 \
  --temperature-ev 1.0 --ne 1e17
roboai-stark width --element S --charge 2 --wavelength-a 5606.151 \
  --temperature-ev 1.0 --ne 1e17 --json   # full calculation trace
```

## Authentication

The token store is **shared with
[`roboai-libs-client`](https://github.com/RoboAI-Green/roboai-libs-client)** —
both clients talk to the same platform, so one login serves both:

- `roboai-stark auth login` (or `roboai-libs auth login`) requests an email
  verification link and stores the token in `~/.config/roboai-libs/auth.json`.
- Alternatively set `ROBOAI_LIBS_API_KEY` in the environment.
- `roboai-stark auth status` / `auth logout` / `doctor` manage and check it.

## Usage Examples

Runnable scripts live in [`examples/`](examples/):

- [`single_line.py`](examples/single_line.py) — one width, the reliability
  block, and the strongest perturbing-line contributions.
- [`batch_lines.py`](examples/batch_lines.py) — a line list with
  reliability screening (note the flagged Na I resonance line).
- [`level_search.py`](examples/level_search.py) — pick a transition by fuzzy
  level labels (`"3s2 3p2 3d 4F"` matches `3s2.3p2.(3P).3d 4F`) instead of
  wavelength:

```python
lower = client.search_levels(element="S", charge=2, query="3s2 3p2 3d 4F J=9/2")
upper = client.search_levels(element="S", charge=2, query="3s2 3p2 4p 4D J=7/2")
result = client.compute_width(
    element="S", charge=2,
    low_level_id=lower[0].level_id, upp_level_id=upper[0].level_id,
    temperature_k=11600.0, ne_cm3=1e17,
)
```

## What You Get Back

`compute_width` returns a `StarkWidthResult` carrying the complete trace:

| Field | Meaning |
|---|---|
| `fwhm_nm`, `fwhm_low_nm`, `fwhm_high_nm` | Stark FWHM in nm with the f-provenance uncertainty band |
| `hwhm_nm` | half width |
| `target` | the resolved ASD line: ion, wavelength, both level identifications (configuration/term/J/energy) |
| `plasma` | temperature (K and eV), electron density, kT in cm⁻¹ |
| `low_side` / `upp_side` | per-level term sums: explicit Δn=0 (with bounds), lumped Δn≠0 (R², x, Gaunt), effective quantum number n* |
| `s_total`, `c_front` | the two factors of W = Nₑ·C·S·10⁷ |
| `perturbing_lines` | every explicit Δn=0 perturbing line: ΔE, Gaunt, f with **source/provider/method/details**, R², contribution |
| `reliability` | see below |

The width is linear in Nₑ, so one result rescales to any density for free.

## Reliability

Every result carries a method-domain reliability block, backed by a
758-transition benchmark against the STARK-B SCP database:

- `confidence` — `high` / `medium` / `low` from the emitter charge and the
  lumped share of the width.
- `benchmark` — the accuracy numbers for this charge class (e.g. singly
  ionised: median W_MSE/W_SCP = 1.16, 72 % within a factor of 2).
- `lumped_share` — the fraction of the width resting on the lumped Δn≠0
  approximation; ≥ 50 % flags `lumped_dominated` (such widths underestimate).
- `flags` / `notes` — machine-readable warnings: `neutral_out_of_domain`,
  `high_charge_underestimate`, `lumped_dominated`, `unvalidated_charge`.

## Scientific Scope

- Electron-impact broadening of **isolated lines of ionized, non-hydrogenic
  emitters** — the stated domain of the MSE method (class accuracy ±50 %).
- Neutral emitters are computed but flagged out-of-domain (resonance lines
  overestimate); hydrogen lines need dedicated hydrogenic tables and are not
  meaningful here.
- Quasi-static ion broadening and ion dynamics are not included.
- Gaunt treatment follows Dimitrijević & Konjević (1980), JQSRT 24, 451
  (canonical g(x) table and the Δn=0 ion correction g̃ = 0.7 − 1.1/Z + g(x)).

## Support

- Issues and feature requests: [GitHub issues](https://github.com/RoboAI-Green/roboai-stark-client/issues)
- Platform and web UI: [libs.roboai.fi](https://libs.roboai.fi)

## License

[MIT](LICENSE)
