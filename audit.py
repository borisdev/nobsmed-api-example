"""Call the NoBSmed clinical-evidence audit API and print what came back.

    uv run audit.py                      # audits sample_input.txt
    uv run audit.py my_plan.txt          # audits your own file

Needs two environment variables:

    NOBSMED_API_KEY    the key you were given
    NOBSMED_API_URL    the service URL

Deliberately one file with no framework. You should be able to read the whole client in a minute
and see that there is no magic: one POST, one JSON response.
"""

# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.31"]
# ///

from __future__ import annotations

import json
import os
import sys
import textwrap

import requests

URL = os.environ.get("NOBSMED_API_URL", "").rstrip("/")
KEY = os.environ.get("NOBSMED_API_KEY", "")


def main() -> int:
    if not URL or not KEY:
        print("Set NOBSMED_API_URL and NOBSMED_API_KEY first. See README.md.", file=sys.stderr)
        return 2

    path = sys.argv[1] if len(sys.argv) > 1 else "sample_input.txt"
    plan = open(path, encoding="utf-8").read()

    print(f"POST {URL}/v1/case   ({len(plan)} chars)")
    print("A build runs live literature retrieval and takes 15-40s.\n")

    # timeout=120 on purpose: the default would give up mid-build and look like an outage.
    r = requests.post(f"{URL}/v1/case",
                      headers={"Authorization": f"Bearer {KEY}"},
                      json={"text": plan}, timeout=120)

    if r.status_code == 403:
        print("403 — " + r.json().get("detail", "not permitted"), file=sys.stderr)
        return 1
    if r.status_code == 503:
        print("503 — the service has no API keys configured. That is our side, not yours.",
              file=sys.stderr)
        return 1
    r.raise_for_status()
    d = r.json()

    g = d["graph"]
    plan_layer = [n for n in g["nodes"] if n.get("in_plan_view") is True]
    findings = [n for n in g["nodes"] if n.get("in_plan_view") is False]
    cited = [e for e in g["edges"] if e.get("pmids")]

    print(f"builder          {d['builder']}")
    print(f"contract         {d['contract_version']}")
    print(f"build time       {d['seconds']}s")
    print(f"plan layer       {len(plan_layer)} nodes   (what the plan targets)")
    print(f"evidence layer   {len(findings)} findings  (what it never addressed)")
    print(f"cited edges      {len(cited)} of {len(g['edges'])}\n")

    for n in findings:
        head = str(n["label"]).splitlines()[0]
        pmids = [p for e in g["edges"] if e["source"] == n["id"] for p in e.get("pmids", [])]
        print(textwrap.fill(f"• {head}", 96, subsequent_indent="  "))
        for p in pmids:
            print(f"    https://pubmed.ncbi.nlm.nih.gov/{p}/")
        print()

    # ⚠️ READ THESE BEFORE RESTATING ANYTHING AS FACT. They say what a JSON Schema cannot: that an
    # empty `pmids` means "not retrieved", NOT "refuted" — and that difference is the product.
    print("how to read this:")
    for line in d["how_to_read_this"]:
        print(textwrap.fill(f"  - {line}", 96, subsequent_indent="    "))

    open("out.json", "w", encoding="utf-8").write(json.dumps(d, indent=2))
    open("out.mmd", "w", encoding="utf-8").write(d["mermaid"])
    print("\nwrote out.json and out.mmd — paste out.mmd into any Mermaid viewer to see the graph.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
