"""Batch Stark widths for a line list, with reliability screening."""

from roboai_stark_client import RoboAIStarkAPIError, RoboAIStarkClient

LINES = [
    ("S", 2, 5606.151),
    ("O", 2, 4070.5),
    ("Si", 2, 6347.1),
    ("Na", 1, 5889.95),  # neutral resonance line — expect an out-of-domain flag
]

with RoboAIStarkClient() as client:
    for element, charge, wavelength in LINES:
        try:
            r = client.compute_width(
                element=element, charge=charge, wavelength_a=wavelength,
                wavelength_tol_a=1.0, temperature_ev=1.0, ne_cm3=1e17,
            )
        except RoboAIStarkAPIError as exc:
            print(f"{element} {charge} {wavelength:9.2f} Å  — {exc}")
            continue
        rel = r.reliability
        flags = f"  [{', '.join(rel.flags)}]" if rel.flags else ""
        print(
            f"{r.target.ion:6s} {r.target.wavelength_A:9.3f} Å  "
            f"FWHM {r.fwhm_nm:9.5f} nm  {rel.confidence.upper():6s}{flags}"
        )
