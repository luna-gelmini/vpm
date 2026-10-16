# vpm

VRChat Creator Companion listing for questkit, ps1ify and source2vrchat, served with GitHub Pages
at https://vpm.ladyluh.dev/.

## How it works

- Each package repo has a **Release** workflow. Publishing a GitHub release tagged `vX.Y.Z` builds
  the VCC zip and the `.unitypackage` with `build.py` and attaches both to the release.
- The **Listing** workflow here runs `update_listing.py`: it reads every published release of the
  package repos, downloads each zip, and writes `index.json` with the real checksums. It then
  deploys `index.json`, `index.html` and `CNAME` to Pages. It runs on push, every hour, on demand,
  and right after a release if the package repo has a `VPM_DISPATCH_TOKEN` secret.

`index.json` isn't committed; the workflow generates it on every deploy.

## Releasing a new version

1. Bump `version` (and the version in `url`) in the package's `package.json`. If you added files,
   run `python build.py --metas` here and commit the new `.meta` files too.
2. Push, then publish a release on GitHub with tag `v<version>`, a title and notes.
3. The Release workflow attaches the files. The listing picks the version up within the hour, or
   right away with the dispatch token, or when you run the Listing workflow by hand.

The Release workflow refuses to build if the tag doesn't match `package.json` or a `.meta` file
is missing. To rebuild the files of an existing release, run it by hand with that tag.

## Local use

    python build.py --metas        add missing .meta files to the local package folders
    python build.py                build every package into release/
    python update_listing.py       build the site into site/ from the live releases
