"""Demo traffic driver: replays realistic application traffic against a running API.

Usage:  python -m backend.data.simulate --n 60 --rate 4 --ring
The --ring burst reuses one device across many applicant names, so device and IP
velocity build up inside the live database exactly as a real fraud ring would.
"""
import argparse
import os
import random
import sys
import time

import httpx

from .generate import make_event

API = os.getenv("API_URL", "http://127.0.0.1:8000")


def clean(event: dict) -> dict:
    return {k: v for k, v in event.items() if not k.startswith("_")}


def login(client: httpx.Client, email: str, password: str) -> str:
    response = client.post(f"{API}/v1/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return response.json()["access_token"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=40, help="number of applications")
    parser.add_argument("--rate", type=float, default=4.0, help="applications per second")
    parser.add_argument("--fraud-rate", type=float, default=0.15)
    parser.add_argument("--ring", action="store_true", help="inject a device-farm burst")
    parser.add_argument("--email", default=os.getenv("SEED_ANALYST_EMAIL", "analyst@sentinel.local"))
    parser.add_argument("--password", default=os.getenv("SEED_ANALYST_PASSWORD", ""))
    args = parser.parse_args()

    if not args.password:
        print("Set SEED_ANALYST_PASSWORD (see .env) or pass --password", file=sys.stderr)
        return 2

    rng = random.Random()
    with httpx.Client(timeout=30) as client:
        headers = {"Authorization": f"Bearer {login(client, args.email, args.password)}"}
        ring_device = f"dev-{rng.randint(100000, 999999)}"
        ring_ip = f"49.{rng.randint(1, 250)}.{rng.randint(1, 250)}.{rng.randint(1, 250)}"
        counts: dict[str, int] = {}

        for i in range(args.n):
            in_ring = args.ring and args.n // 3 <= i < args.n // 3 + 6
            event, _ = make_event(rng, fraud=in_ring or rng.random() < args.fraud_rate,
                                  kind="ring" if in_ring else None)
            if in_ring:  # same handset, same network, different identity every time
                event["device"]["device_id"], event["device"]["ip"] = ring_device, ring_ip

            response = client.post(f"{API}/v1/applications/score", json=clean(event), headers=headers)
            response.raise_for_status()
            body = response.json()
            counts[body["decision"]] = counts.get(body["decision"], 0) + 1
            print(f"{body['application_id']}  {body['decision']:<8} risk={body['risk_score']:.2f} "
                  f"{body['latency_ms']:>6.1f}ms  {body['reasons'][0]['detail'] if body['reasons'] else ''}"[:150])
            time.sleep(1 / max(args.rate, 0.1))

    print("\nDecision mix:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
