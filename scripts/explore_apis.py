"""
Exploration script, not production ingestion.

Pulls small samples from USGS, EONET and GDACS to inspect their structure
and quirks. Findings are written up in docs/source-notes.md.
Production ingestion lives in ingestion/<source>/.

Outputs:
    data/     full responses, timestamped (git-ignored)
    samples/  small trimmed samples with stable names (committed)

Usage (from the repo root, with the virtual environment active):
    python scripts/explore_apis.py
    python scripts/explore_apis.py --days 30
"""
import argparse
import json
import pathlib
import time
from datetime import datetime, timedelta, timezone

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
DATA = ROOT / "data"

HEADERS = {"User-Agent": "terrawatch-lakehouse-exploration"}
SAMPLE_SIZE = 5
GDACS_CAP = 100
GDACS_BASE = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def trim(data, list_key, n=SAMPLE_SIZE):
    """Copy of the response with only the first n records in list_key."""
    trimmed = dict(data)
    trimmed[list_key] = data[list_key][:n]
    return trimmed


def fetch_gdacs(etype, level, start, end):
    url = (f"{GDACS_BASE}?eventlist={etype}&fromdate={start}&todate={end}"
        f"&alertlevel={level}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    time.sleep(0.5)  # be polite
    if resp.status_code == 204 or not resp.content:
        return []
    resp.raise_for_status()
    return resp.json().get("features", [])


def fetch_gdacs_window(etype, level, start, end):
    """Split the date window in half whenever a response hits the 100-row cap."""
    feats = fetch_gdacs(etype, level, start, end)
    if len(feats) < GDACS_CAP:
        return feats
    if start >= end:
        print(f"WARNING: cap hit on a single day: {etype} {level} {start}")
        return feats
    mid = start + (end - start) // 2
    return (fetch_gdacs_window(etype, level, start, mid)
            + fetch_gdacs_window(etype, level, mid + timedelta(days=1), end))


def run_simple_sources(sources, stamp):
    for name, (url, params, list_key) in sources.items():
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
            print(f"\n== {name}: HTTP {resp.status_code}, "
                f"{resp.elapsed.total_seconds():.1f}s")
            print("URL:", resp.url)
            print("Rate-limit headers:",
                {k: v for k, v in resp.headers.items() if "limit" in k.lower()})
            resp.raise_for_status()
            if resp.status_code == 204 or not resp.content:
                print("No content returned")
                continue
            data = resp.json()
            write_json(DATA / f"{name}_{stamp}.json", data)
            write_json(SAMPLES / f"{name}_sample.json", trim(data, list_key))
            print(f"Records: {len(data[list_key])} "
                f"(full pull in data/, {SAMPLE_SIZE}-record sample in samples/)")
        except (requests.RequestException, KeyError, ValueError) as exc:
            print(f"\n== {name}: FAILED -> {exc}")


def run_gdacs(start_date, today, stamp):
    print("\n== gdacs")
    try:
        all_feats, sample_feats = [], []
        for etype in ["EQ", "TC", "FL"]:
            for level in ["red", "orange", "green"]:
                feats = fetch_gdacs_window(etype, level, start_date, today)
                print(f"{etype} {level}: {len(feats)} records")
                all_feats.extend(feats)
                if feats:
                    sample_feats.append(feats[0])  # one example per type and level
        unique_ids = {f["properties"].get("eventid") for f in all_feats}
        print(f"Total: {len(all_feats)} records, {len(unique_ids)} unique event IDs")
        write_json(DATA / f"gdacs_{stamp}.json", {"features": all_feats})
        write_json(SAMPLES / "gdacs_sample.json", {"features": sample_feats})
    except (requests.RequestException, KeyError, ValueError) as exc:
        print(f"gdacs: FAILED -> {exc}")


def main():
    parser = argparse.ArgumentParser(description="Explore the hazard APIs.")
    parser.add_argument("--days", type=int, default=7,
                        help="how many days back to pull (default 7)")
    args = parser.parse_args()

    SAMPLES.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)

    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=args.days)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    simple_sources = {
        "usgs": (
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            {"format": "geojson", "starttime": start_date.isoformat(),
            "endtime": today.isoformat(), "minmagnitude": 4, "limit": 20},
            "features",
        ),
        "eonet": (
            "https://eonet.gsfc.nasa.gov/api/v3/events",
            {"status": "all", "days": args.days, "limit": 20},
            "events",
        ),
    }
    run_simple_sources(simple_sources, stamp)
    run_gdacs(start_date, today, stamp)


if __name__ == "__main__":
    main()