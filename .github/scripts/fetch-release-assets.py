#!/usr/bin/env python3
"""Download release assets by numeric release id.

`gh release download <tag>` resolves a tag through the git reference, which a
draft release created by CI does not have yet, so assets are fetched through the
releases API instead.
"""
import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path


def gh(*api_args):
    result = subprocess.run(["gh", "api", *api_args], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"gh api {' '.join(api_args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def pick_release(releases, tag):
    candidates = [release for release in releases
                  if (tag is not None and release.get("tag_name") == tag)
                  or (tag is None and release.get("draft"))]
    if not candidates:
        seen = ", ".join(f"{release.get('tag_name')}(draft={release.get('draft')})" for release in releases)
        raise SystemExit(f"No release found for {'tag ' + tag if tag else 'draft'}; "
                         f"the API returned {len(releases)} release(s): {seen or 'nothing'}")
    return max(candidates, key=lambda release: release["id"])


def select_assets(assets, patterns):
    chosen = [asset for asset in assets
              if any(fnmatch.fnmatch(asset["name"], pattern) for pattern in patterns)]
    if not chosen:
        raise SystemExit(f"Release has no asset matching {patterns}")
    incomplete = [asset["name"] for asset in chosen if asset.get("state") != "uploaded"]
    if incomplete:
        raise SystemExit(f"Asset upload not finished for: {', '.join(incomplete)}")
    return sorted(chosen, key=lambda asset: asset["name"])


def download(repo, asset, directory):
    target = directory / asset["name"]
    if target.is_file() and target.stat().st_size == asset["size"]:
        print(f"already present: {target}")
        return target
    if target.exists():
        raise SystemExit(f"{target} exists with the wrong size; remove it first")
    with target.open("wb") as stream:
        result = subprocess.run(
            ["gh", "api", "-H", "Accept: application/octet-stream",
             f"repos/{repo}/releases/assets/{asset['id']}"], stdout=stream, check=True)
    if result.returncode != 0:
        raise SystemExit(f"Failed to download {asset['name']}")
    if target.stat().st_size != asset["size"]:
        raise SystemExit(f"{asset['name']}: expected {asset['size']} bytes, got {target.stat().st_size}")
    print(f"downloaded: {target} ({asset['size']} bytes)")
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", help="release tag; omit to take the newest draft")
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--pattern", action="append", required=True)
    args = parser.parse_args()
    args.dir.mkdir(parents=True, exist_ok=True)
    release = pick_release(gh(f"repos/{args.repo}/releases"), args.tag)
    print(f"release {release['id']} tag {release.get('tag_name')} draft={release.get('draft')} "
          f"assets={release.get('assets')}")
    assets = select_assets(gh(f"repos/{args.repo}/releases/{release['id']}/assets"), args.pattern)
    for asset in assets:
        download(args.repo, asset, args.dir)
    total = sum(asset["size"] for asset in assets)
    print(f"{len(assets)} assets, {total} bytes: " + ", ".join(asset["name"] for asset in assets))


if __name__ == "__main__":
    sys.exit(main())
