"""Builds release files for the packages listed in PACKAGES and the VCC listing.

For each package it adds missing Unity .meta files to the package folder, then writes into
release/<name>/:
  <name>-<version>.zip           the VCC / VPM package
  <Folder>-<version>.unitypackage  drag-into-Unity install under Assets/<Folder>
and finally regenerates index.json (the listing VCC reads) with each zip's SHA-256.

    python build.py            build everything
    python build.py --metas    only add missing .meta files
"""
import hashlib
import io
import json
import os
import sys
import tarfile
import uuid
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)

LISTING = {
    "name": "ladyluh's VRChat tools",
    "id": "dev.ladyluh.vpm",
    "url": "https://luna-gelmini.github.io/vpm/index.json",
    "author": "luna-gelmini",
}

# Package folder (relative to the tools folder) and the Assets/ folder for the .unitypackage.
PACKAGES = [
    ("questkit", "QuestKit"),
    ("ps1ify", "PS1ify"),
    ("source2vrchat/unity", "Source2VRChat"),
]

SKIP = {".git", ".gitignore", ".gitattributes", "release", "__pycache__"}

META_HEAD = "fileFormatVersion: 2\nguid: {guid}\n"
TAIL = "  userData: \n  assetBundleName: \n  assetBundleVariant: \n"
IMPORTERS = {
    ".cs": "MonoImporter:\n  externalObjects: {}\n  serializedVersion: 2\n  defaultReferences: []\n"
           "  executionOrder: 0\n  icon: {instanceID: 0}\n" + TAIL,
    ".asmdef": "AssemblyDefinitionImporter:\n  externalObjects: {}\n" + TAIL,
    ".md": "TextScriptImporter:\n  externalObjects: {}\n" + TAIL,
    ".txt": "TextScriptImporter:\n  externalObjects: {}\n" + TAIL,
}
PACKAGE_JSON = "PackageManifestImporter:\n  externalObjects: {}\n" + TAIL
DEFAULT = "DefaultImporter:\n  externalObjects: {}\n" + TAIL
FOLDER = "folderAsset: yes\nDefaultImporter:\n  externalObjects: {}\n" + TAIL


def entries(root):
    """Every file and folder of a package, relative to its root, skipping metas and repo files."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP and not d.startswith(".") and not d.endswith("~"))
        rel = os.path.relpath(dirpath, root)
        if rel != ".":
            yield rel.replace("\\", "/"), True
        for f in sorted(filenames):
            if f.endswith(".meta") or f in SKIP or f.startswith("."):
                continue
            yield os.path.join(rel, f).replace("\\", "/").lstrip("./"), False


def ensure_metas(root):
    added = 0
    for rel, is_dir in entries(root):
        meta = os.path.join(root, rel) + ".meta"
        if os.path.exists(meta):
            continue
        guid = uuid.uuid4().hex
        if is_dir:
            body = FOLDER
        elif os.path.basename(rel) == "package.json":
            body = PACKAGE_JSON
        else:
            body = IMPORTERS.get(os.path.splitext(rel)[1].lower(), DEFAULT)
        with open(meta, "w", newline="\n") as f:
            f.write(META_HEAD.format(guid=guid) + body)
        added += 1
    return added


def guid_of(path):
    with open(path + ".meta") as f:
        for line in f:
            if line.startswith("guid:"):
                return line.split(":", 1)[1].strip()
    raise ValueError("no guid in " + path + ".meta")


def build_zip(root, out):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, is_dir in entries(root):
            if not is_dir:
                z.write(os.path.join(root, rel), rel)
            z.write(os.path.join(root, rel) + ".meta", rel + ".meta")


def build_unitypackage(root, folder, out):
    def add(tar, name, data):
        info = tarfile.TarInfo(name)
        info.size = len(data)
        info.mtime = 0
        tar.addfile(info, io.BytesIO(data))

    with tarfile.open(out, "w:gz") as tar:
        for rel, is_dir in entries(root):
            if rel == "package.json":
                continue
            path = os.path.join(root, rel)
            guid = guid_of(path)
            add(tar, guid + "/pathname", ("Assets/" + folder + "/" + rel).encode("utf-8"))
            with open(path + ".meta", "rb") as f:
                add(tar, guid + "/asset.meta", f.read())
            if not is_dir:
                with open(path, "rb") as f:
                    add(tar, guid + "/asset", f.read())


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    metas_only = "--metas" in sys.argv
    listing = dict(LISTING, packages={})
    index_path = os.path.join(HERE, "index.json")
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            listing["packages"] = json.load(f).get("packages", {})

    for rel_root, folder in PACKAGES:
        root = os.path.join(TOOLS, rel_root)
        added = ensure_metas(root)
        with open(os.path.join(root, "package.json"), encoding="utf-8") as f:
            pkg = json.load(f)
        name, version = pkg["name"], pkg["version"]
        print("%s %s: %d .meta files added" % (name, version, added))
        if metas_only:
            continue

        out_dir = os.path.join(HERE, "release", name)
        os.makedirs(out_dir, exist_ok=True)
        zip_path = os.path.join(out_dir, "%s-%s.zip" % (name, version))
        pkg_path = os.path.join(out_dir, "%s-%s.unitypackage" % (folder, version))
        build_zip(root, zip_path)
        build_unitypackage(root, folder, pkg_path)

        entry = dict(pkg)
        entry["zipSHA256"] = sha256(zip_path)
        listing["packages"].setdefault(name, {"versions": {}})["versions"][version] = entry
        print("  " + os.path.relpath(zip_path, HERE))
        print("  " + os.path.relpath(pkg_path, HERE))

    if not metas_only:
        with open(index_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(listing, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("index.json updated")


if __name__ == "__main__":
    main()
