"""Compute one Stark width and inspect the reliability block.

Authenticate once first: `roboai-stark auth login` (shared with roboai-libs).
"""

from roboai_stark_client import RoboAIStarkClient

client = RoboAIStarkClient()

result = client.compute_width(
    element="S",            # element symbol
    charge=2,               # spectroscopic charge: 2 = singly ionised (S II)
    wavelength_a=5606.151,  # transition wavelength in Å (nearest ASD line)
    temperature_ev=1.0,     # electron temperature in eV (≈ 11 605 K)
    ne_cm3=1e17,            # electron density in cm⁻³
)

print(result.summary())
print()

# The width scales linearly with Ne, so rescaling is free:
for ne in (1e16, 1e17, 1e18):
    print(f"Ne={ne:.0e}: FWHM = {result.fwhm_nm * ne / 1e17:.5f} nm")

# Full trace: every explicit Δn=0 perturbing line with its f-value provenance.
used = [p for p in result.perturbing_lines if p.contribution > 0]
print(f"\n{len(used)} perturbing lines used; strongest contributions:")
for p in sorted(used, key=lambda p: -p.contribution)[:5]:
    print(f"  {p.side:5s} {p.perturber_label:34s} f={p.f:.4g} [{p.f_source}] S={p.contribution:.3g}")
