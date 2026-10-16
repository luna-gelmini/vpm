"""Builds the release files of a Unity package: the VCC zip and a .unitypackage.

    python build.py --package DIR --folder NAME [--tag vX.Y.Z] [--out DIR]
        Builds one package (what the release workflows run). Fails if a .meta file is missing,
        or if --tag doesn't match the version in package.json.
    python build.py
        Builds every package in LOCAL_PACKAGES into release/<name>/.
    python build.py --metas
        Adds missing .meta files to every package in LOCAL_PACKAGES.

Output names:
    <name>-<version>.zip             the package VCC installs
    <Folder>-<version>.unitypackage  drag-into-Unity install under Assets/<Folder>
"""
import argparse
import io
import json
import os
import sys
import tarfile
import uuid
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

# For local builds: package folder (relative to the folder holding all the repos) and the
# Assets/ folder its .unitypackage installs into.
LOCAL_PACKAGES = [
    ("questkit", "QuestKit"),
    ("ps1ify", "PS1ify"),
    ("source2vrchat/unity", "Source2VRChat"),
    ("visememaker", "VisemeMaker"),
]

SKIP = {".git", ".github", ".gitignore", ".gitattributes", "release", "dist", "__pycache__"}

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
        if is_dir:
            body = FOLDER
        elif os.path.basename(rel) == "package.json":
            body = PACKAGE_JSON
        else:
            body = IMPORTERS.get(os.path.splitext(rel)[1].lower(), DEFAULT)
        with open(meta, "w", newline="\n") as f:
            f.write(META_HEAD.format(guid=uuid.uuid4().hex) + body)
        added += 1
    return added


def missing_metas(root):
    return [rel for rel, _ in entries(root) if not os.path.exists(os.path.join(root, rel) + ".meta")]


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


def build(root, folder, out_dir, tag=None):
    missing = missing_metas(root)
    if missing:
        sys.exit("Missing .meta files (run build.py --metas locally and commit them):\n  " + "\n  ".join(missing))
    with open(os.path.join(root, "package.json"), encoding="utf-8") as f:
        pkg = json.load(f)
    name, version = pkg["name"], pkg["version"]
    if tag is not None and tag.lstrip("v") != version:
        sys.exit("Tag %s doesn't match package.json version %s. Bump the version or fix the tag." % (tag, version))
    expected_zip = "%s-%s.zip" % (name, version)
    if not pkg.get("url", "").endswith("/" + expected_zip):
        print("warning: package.json url doesn't end in %s; VCC uses the listing's url, so this is only cosmetic" % expected_zip)

    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, expected_zip)
    pkg_path = os.path.join(out_dir, "%s-%s.unitypackage" % (folder, version))
    build_zip(root, zip_path)
    build_unitypackage(root, folder, pkg_path)
    print(zip_path)
    print(pkg_path)
    return pkg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", help="package folder (contains package.json)")
    ap.add_argument("--folder", help="Assets/ folder name for the .unitypackage")
    ap.add_argument("--tag", help="release tag; must match the package version")
    ap.add_argument("--out", default="dist")
    ap.add_argument("--metas", action="store_true", help="only add missing .meta files to local packages")
    args = ap.parse_args()

    if args.package:
        if not args.folder:
            ap.error("--package needs --folder")
        build(args.package, args.folder, args.out, args.tag)
        return

    tools = os.path.dirname(HERE)
    for rel_root, folder in LOCAL_PACKAGES:
        root = os.path.join(tools, rel_root)
        added = ensure_metas(root)
        print("%s: %d .meta files added" % (rel_root, added))
        if not args.metas:
            with open(os.path.join(root, "package.json"), encoding="utf-8") as f:
                name = json.load(f)["name"]
            build(root, folder, os.path.join(HERE, "release", name))


if __name__ == "__main__":
    main()
