"""Pick a transition by fuzzy level labels instead of wavelength."""

from roboai_stark_client import RoboAIStarkClient

with RoboAIStarkClient() as client:
    # Fuzzy matching ignores dots/spaces/punctuation:
    # "3s2 3p2 3d 4F" matches "3s2.3p2.(3P).3d 4F".
    lower = client.search_levels(element="S", charge=2, query="3s2 3p2 3d 4F J=9/2")
    upper = client.search_levels(element="S", charge=2, query="3s2 3p2 4p 4D J=7/2")

    print("lower candidates:")
    for level in lower[:3]:
        print(f"  {level.level_id}  {level.label()}  E={level.energy_cm1:.1f} cm⁻¹")

    result = client.compute_width(
        element="S",
        charge=2,
        low_level_id=lower[0].level_id,
        upp_level_id=upper[0].level_id,
        temperature_k=11600.0,
        ne_cm3=1e17,
    )
    print()
    print(result.summary())
