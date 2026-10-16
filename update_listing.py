"""Builds the VCC listing from what the package repos' GitHub releases actually contain.

For every published release of every repo in REPOS it downloads the package zip, reads the
package.json inside, computes the zip's SHA-256 and lists that version. A release without a zip
(or a broken one) is skipped with a warning, so the listing never points at a missing file.

Writes the site to OUT (default: site/): index.json plus the static files in STATIC.

    python update_listing.py [OUT]

Set GITHUB_TOKEN to avoid the API's anonymous rate limit.
"""
import hashlib
import io
import json
import os
import shutil
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

LISTING = {
    "name": "ladyluh's VRChat tools",
    "id": "dev.ladyluh.vpm",
    "url": "https://vpm.ladyluh.dev/index.json",
    "author": "luna-gelmini",
}

REPOS = [
    "luna-gelmini/QuestKit",
    "luna-gelmini/AvatarPSXify",
    "luna-gelmini/Source2VRChat",
]

STATIC = ["index.html", "CNAME"]


def get(url, accept="application/vnd.github+json"):
    headers = {"Accept": accept, "User-Agent": "vpm-listing"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as r:
        return r.read()


def releases(repo):
    page = 1
    while True:
        batch = json.loads(get("https://api.github.com/repos/%s/releases?per_page=100&page=%d" % (repo, page)))
        if not batch:
            return
        for r in batch:
            if not r["draft"]:
                yield r
        page += 1


def version_key(v):
    parts = []
    for p in v.split("-")[0].split("."):
        parts.append(int(p) if p.isdigit() else 0)
    return parts


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "site")
    packages = {}
    problems = 0
    for repo in REPOS:
        for rel in releases(repo):
            zips = [a for a in rel["assets"] if a["name"].endswith(".zip")]
            if not zips:
                print("warning: %s %s has no .zip asset, skipped" % (repo, rel["tag_name"]))
                problems += 1
                continue
            for asset in zips:
                data = get(asset["browser_download_url"], accept="application/octet-stream")
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        pkg = json.loads(z.read("package.json").decode("utf-8-sig"))
                except (zipfile.BadZipFile, KeyError, ValueError) as e:
                    print("warning: %s %s: %s is not a package zip (%s), skipped" % (repo, rel["tag_name"], asset["name"], e))
                    problems += 1
                    continue
                entry = dict(pkg)
                entry["url"] = asset["browser_download_url"]
                entry["zipSHA256"] = hashlib.sha256(data).hexdigest()
                packages.setdefault(pkg["name"], {"versions": {}})["versions"][pkg["version"]] = entry
                print("%s %s from %s %s" % (pkg["name"], pkg["version"], repo, rel["tag_name"]))

    for p in packages.values():
        p["versions"] = dict(sorted(p["versions"].items(), key=lambda kv: version_key(kv[0]), reverse=True))

    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(LISTING, packages=packages), f, indent=2, ensure_ascii=False)
        f.write("\n")
    for name in STATIC:
        if os.path.exists(os.path.join(HERE, name)):
            shutil.copy(os.path.join(HERE, name), os.path.join(out, name))
    print("wrote %s (%d packages, %d problems)" % (out, len(packages), problems))


if __name__ == "__main__":
    main()
