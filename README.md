# vpm

VRChat Creator Companion listing for questkit, ps1ify and source2vrchat, served with GitHub Pages
at https://vpm.ladyluh.dev/.

## Releasing a new version

1. Bump `version` (and the version in `url`) in the package's `package.json` and commit it.
2. Run `python build.py`. It adds any missing `.meta` files, builds `release/<package>/` (the VCC
   zip and a `.unitypackage`) and updates `index.json` with the zip's SHA-256. If it added `.meta`
   files, commit them in the package repo.
3. In the package repo, create a GitHub release tagged `v<version>` and upload both files from
   `release/<package>/`. The zip's file name must match the `url` in `package.json`.
4. Commit and push `index.json` here. VCC sees the new version after GitHub Pages updates.

Old versions stay in `index.json`, so people can roll back. `build.py` skips versions that are
already listed, because their zips are already uploaded and a rebuild would change the checksum.
