from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from typing import Any

from .auth import (
    clear_stored_api_key,
    extract_access_token,
    get_token_file,
    load_stored_api_key,
    token_from_env,
)
from .client import RoboAIStarkClient
from .errors import RoboAIStarkAPIError


def _client_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if getattr(args, "base_url", None):
        kwargs["base_url"] = args.base_url
    return kwargs


def _missing_token_error() -> int:
    print(
        "No API token configured. Run `roboai-stark auth login` first "
        "(the token is shared with roboai-libs).",
        file=sys.stderr,
    )
    return 2


# ------------------------------------------------------------------------ auth
def _request_login(args: argparse.Namespace) -> int:
    if args.token:
        raw_token = args.token
    else:
        email = args.email or input("Email: ").strip()
        if not email:
            print("Email is required.", file=sys.stderr)
            return 2

        with RoboAIStarkClient(**_client_kwargs(args)) as client:
            base_url = client.base_url
            try:
                client.request_login_otp(email)
            except RoboAIStarkAPIError as exc:
                print(f"Authentication request failed: {exc}", file=sys.stderr)
                return 1
            except Exception as exc:
                print(f"Authentication request failed against {base_url}: {exc}", file=sys.stderr)
                if not args.base_url and not os.getenv("ROBOAI_LIBS_BASE_URL"):
                    print(
                        "If you are testing a local deployment, set ROBOAI_LIBS_BASE_URL "
                        "or pass --base-url.",
                        file=sys.stderr,
                    )
                return 1

        print("Verification link sent. Open it from your email, then paste the access_token here.")
        raw_token = getpass.getpass("access_token: ")

    try:
        token = extract_access_token(raw_token)
    except ValueError as exc:
        print(f"Token parsing failed: {exc}", file=sys.stderr)
        return 1

    client = RoboAIStarkClient(api_key=token, **_client_kwargs(args))
    try:
        with client:
            token_file = client.save_authenticated_token()
    except Exception as exc:
        print(f"Token validation failed against {client.base_url}: {exc}", file=sys.stderr)
        return 1

    print(f"Saved API token to {token_file}")
    print("Authentication setup complete. RoboAIStarkClient() is ready to use.")
    return 0


def _auth_status(args: argparse.Namespace) -> int:
    if token_from_env():
        print("API token is configured from environment.")
        return 0
    if load_stored_api_key():
        print(f"API token is stored in {get_token_file()}")
        return 0
    print("No API token configured.")
    return 1


def _auth_logout(args: argparse.Namespace) -> int:
    removed = clear_stored_api_key()
    if removed:
        print(f"Removed stored API token from {get_token_file()}")
    else:
        print("No stored API token found.")
    return 0


# ----------------------------------------------------------------------- width
def _width(args: argparse.Namespace) -> int:
    client = RoboAIStarkClient(**_client_kwargs(args))
    if not client.api_key:
        return _missing_token_error()

    request_kwargs: dict[str, Any] = dict(
        element=args.element,
        charge=args.charge,
        ne_cm3=args.ne_cm3,
        same_core_only=not args.no_same_core,
    )
    if args.lower and args.upper:
        request_kwargs.update(low_level_id=args.lower, upp_level_id=args.upper)
    else:
        request_kwargs.update(wavelength_a=args.wavelength_a, wavelength_tol_a=args.tol)
    if args.temperature_k is not None:
        request_kwargs["temperature_k"] = args.temperature_k
    else:
        request_kwargs["temperature_ev"] = args.temperature_ev

    try:
        with client:
            result = client.compute_width(**request_kwargs)
    except RoboAIStarkAPIError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(result.summary())
        used = [p for p in result.perturbing_lines if p.contribution > 0]
        print(f"explicit Δn=0 perturbing lines used: {len(used)} (--json for the full trace)")
    return 0


# ---------------------------------------------------------------------- levels
def _levels(args: argparse.Namespace) -> int:
    client = RoboAIStarkClient(**_client_kwargs(args))
    if not client.api_key:
        return _missing_token_error()

    try:
        with client:
            levels = client.search_levels(
                element=args.element,
                charge=args.charge,
                query=args.query,
                max_results=args.max_results,
            )
    except RoboAIStarkAPIError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not levels:
        print("No matching level found.")
        return 1
    for level in levels:
        print(f"{level.level_id}  {level.label()}  E={level.energy_cm1:.3f} cm⁻¹")
    return 0


# ---------------------------------------------------------------------- doctor
def _doctor(args: argparse.Namespace) -> int:
    client = RoboAIStarkClient(**_client_kwargs(args))
    print(f"base_url: {client.base_url}")
    if not client.api_key:
        print("token: none configured")
        return 1
    try:
        with client:
            info = client.get_token_info()
        print(f"token: valid ({info.get('email', 'unknown account')})")
        return 0
    except Exception as exc:
        print(f"token check failed: {exc}", file=sys.stderr)
        return 1


# ------------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="roboai-stark",
        description="Stark widths from the RoboAI LIBS platform (MSE method, full trace).",
    )
    parser.add_argument("--base-url", help="Override the API base URL")
    sub = parser.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth", help="Authentication (shared with roboai-libs)")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)
    login = auth_sub.add_parser("login", help="Request an OTP link and store the token")
    login.add_argument("--email")
    login.add_argument("--token", help="Skip the OTP round-trip and store this token directly")
    login.set_defaults(func=_request_login)
    auth_sub.add_parser("status", help="Show whether a token is configured").set_defaults(
        func=_auth_status
    )
    auth_sub.add_parser("logout", help="Remove the stored token").set_defaults(func=_auth_logout)

    width = sub.add_parser("width", help="Compute the Stark FWHM for one line")
    width.add_argument("--element", required=True)
    width.add_argument("--charge", type=int, required=True,
                       help="Spectroscopic charge: 1 = neutral (I), 2 = singly ionised (II)")
    width.add_argument("--wavelength-a", type=float, dest="wavelength_a",
                       help="Transition wavelength in Å")
    width.add_argument("--tol", type=float, default=0.05, help="Wavelength tolerance in Å")
    width.add_argument("--lower", help="Lower level_id (from `roboai-stark levels`)")
    width.add_argument("--upper", help="Upper level_id (from `roboai-stark levels`)")
    width.add_argument("--temperature-ev", type=float, dest="temperature_ev", default=1.0)
    width.add_argument("--temperature-k", type=float, dest="temperature_k")
    width.add_argument("--ne", type=float, dest="ne_cm3", default=1e17,
                       help="Electron density in cm⁻³")
    width.add_argument("--no-same-core", action="store_true",
                       help="Allow Δn=0 perturbers with a different parent core")
    width.add_argument("--json", action="store_true", help="Print the full calculation trace")
    width.set_defaults(func=_width)

    levels = sub.add_parser("levels", help="Fuzzy level lookup for one ion")
    levels.add_argument("--element", required=True)
    levels.add_argument("--charge", type=int, required=True)
    levels.add_argument("--query", required=True,
                        help='Configuration / term / J text, e.g. "3s2 3p2 3d 4F"')
    levels.add_argument("--max-results", type=int, default=30)
    levels.set_defaults(func=_levels)

    sub.add_parser("doctor", help="Check connectivity and the stored token").set_defaults(
        func=_doctor
    )

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except json.JSONDecodeError as exc:
        print(f"Unexpected non-JSON response: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
