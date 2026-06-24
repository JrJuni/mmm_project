"""Developer/admin CLI — the project's hidden control surface.

This tool can change *everything* (tracked keyword, geo, cache pool size, grid
display, country selection) and can trigger a live collection. It does so by
writing a gitignored `dev_overrides.json` that `collector.config.load_config`
merges over the shipped defaults.

WHY THIS IS A CLI, NOT AN MCP TOOL
----------------------------------
The project's hard invariant is that the *MCP surface* exposed to the model is
read-only: no write, no refresh, no send. That is what removes the cost channel
and the exfiltration channel (see docs/security.md). This admin surface is
deliberately a plain terminal CLI: it is run by a developer directly and is
structurally unreachable by the model or by untrusted content. DO NOT expose
any of this over MCP, and never wire it to untrusted input.

Usage:
    python -m collector.admin show
    python -m collector.admin set-keyword "Arencia"
    python -m collector.admin set-geo ""                # "" = worldwide
    python -m collector.admin set-topn 50               # or: all  (keep every country)
    python -m collector.admin set-display-n 12
    python -m collector.admin select US KR JP AE        # show exactly these
    python -m collector.admin clear-select              # back to top display-n
    python -m collector.admin refresh                   # run a live collection now
    python -m collector.admin reset                     # drop all dev overrides
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields

from .config import DEV_OVERRIDES_PATH, CollectorConfig, load_config


def _read_overrides() -> dict:
    try:
        with DEV_OVERRIDES_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return raw if isinstance(raw, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def _write_overrides(data: dict) -> None:
    valid = {f.name for f in fields(CollectorConfig)}
    clean = {k: v for k, v in data.items() if k in valid}
    with DEV_OVERRIDES_PATH.open("w", encoding="utf-8") as handle:
        json.dump(clean, handle, ensure_ascii=False, indent=2)
    print(f"[ok] wrote {DEV_OVERRIDES_PATH.name}: {clean}")


def _set(key: str, value) -> None:
    data = _read_overrides()
    data[key] = value
    _write_overrides(data)


def _normalize_codes(codes: list[str]) -> list[str]:
    out: list[str] = []
    for raw in codes:
        code = raw.strip().upper()
        if code.isalpha() and len(code) <= 3:
            out.append(code)
        else:
            print(f"[warn] ignoring invalid country code: {raw!r}", file=sys.stderr)
    return out


def cmd_show(_: argparse.Namespace) -> int:
    cfg = load_config()
    print("Effective config (defaults + dev_overrides.json):")
    print(f"  keyword(s)         : {cfg.keywords}")
    print(f"  geo                : {cfg.geo or 'worldwide'}")
    print(f"  cache pool (top_n) : {'all' if cfg.top_n is None else cfg.top_n}")
    print(f"  grid display_n     : {cfg.display_n}")
    print(f"  selected_countries : {cfg.selected_countries or '(none -> top display_n)'}")
    print(f"  periods/keyword    : {cfg.periods_per_keyword}")
    print(f"  refreshes/day      : {cfg.refreshes_per_day}")
    print(f"  quota: projected {cfg.projected_monthly_calls()}/month, "
          f"budget {cfg.monthly_quota_budget}, within={cfg.within_budget()}")
    print(f"  overrides file     : {DEV_OVERRIDES_PATH} "
          f"({'present' if DEV_OVERRIDES_PATH.exists() else 'absent'})")
    return 0


def cmd_set_keyword(args: argparse.Namespace) -> int:
    _set("keywords", [args.keyword])
    return 0


def cmd_set_keywords(args: argparse.Namespace) -> int:
    kws = [k.strip() for k in args.keywords if k.strip()][:5]
    if not kws:
        print("[error] no keywords given", file=sys.stderr)
        return 1
    _set("keywords", kws)
    return 0


def cmd_set_geo(args: argparse.Namespace) -> int:
    _set("geo", args.geo)
    return 0


def cmd_set_topn(args: argparse.Namespace) -> int:
    if args.n.lower() == "all":
        _set("top_n", None)
    else:
        _set("top_n", int(args.n))
    return 0


def cmd_set_display_n(args: argparse.Namespace) -> int:
    _set("display_n", int(args.n))
    return 0


def cmd_select(args: argparse.Namespace) -> int:
    codes = _normalize_codes(args.codes)
    if not codes:
        print("[error] no valid country codes given", file=sys.stderr)
        return 1
    _set("selected_countries", codes)
    return 0


def cmd_clear_select(_: argparse.Namespace) -> int:
    data = _read_overrides()
    data.pop("selected_countries", None)
    _write_overrides(data)
    return 0


def cmd_refresh(_: argparse.Namespace) -> int:
    from . import fetch_data  # local import: only needed for a live run
    print("[info] running a live collection with the effective config...")
    return fetch_data.main()


def cmd_reset(_: argparse.Namespace) -> int:
    if DEV_OVERRIDES_PATH.exists():
        DEV_OVERRIDES_PATH.unlink()
        print(f"[ok] removed {DEV_OVERRIDES_PATH.name}; back to shipped defaults")
    else:
        print("[ok] no dev overrides to remove")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="collector.admin",
        description="DEV/ADMIN ONLY control surface. Not an MCP tool.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("show", help="print the effective config").set_defaults(func=cmd_show)

    sp = sub.add_parser("set-keyword", help="set the (primary) tracked keyword")
    sp.add_argument("keyword")
    sp.set_defaults(func=cmd_set_keyword)

    sp = sub.add_parser("set-keywords", help="set keywords for Trend comparison (<=5; first is primary)")
    sp.add_argument("keywords", nargs="+")
    sp.set_defaults(func=cmd_set_keywords)

    sp = sub.add_parser("set-geo", help='set geo ("" = worldwide)')
    sp.add_argument("geo")
    sp.set_defaults(func=cmd_set_geo)

    sp = sub.add_parser("set-topn", help="cache pool size (integer or 'all')")
    sp.add_argument("n")
    sp.set_defaults(func=cmd_set_topn)

    sp = sub.add_parser("set-display-n", help="grid display default count")
    sp.add_argument("n")
    sp.set_defaults(func=cmd_set_display_n)

    sp = sub.add_parser("select", help="show exactly these ISO codes")
    sp.add_argument("codes", nargs="+")
    sp.set_defaults(func=cmd_select)

    sub.add_parser("clear-select", help="clear the selection").set_defaults(func=cmd_clear_select)
    sub.add_parser("refresh", help="run a live collection now").set_defaults(func=cmd_refresh)
    sub.add_parser("reset", help="drop all dev overrides").set_defaults(func=cmd_reset)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
