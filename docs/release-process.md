# Release Process

## Release channels

KFP uses four channels. A signed tag and a matching approved gate ledger are
required for every public package.

| Channel | Version example | Gate ledger | GitHub type |
|---|---|---|---|
| Alpha | `2.0.0-alpha.1` | `docs/prerelease-gates.json` | Prerelease |
| Beta | `2.0.0-beta.1` | `docs/prerelease-gates.json` | Prerelease |
| Release candidate | `2.0.0-rc.1` | `docs/prerelease-gates.json` | Prerelease |
| Stable | `2.0.0` | `docs/release-gates.json` | Release |

All channels require approved asset rights. Alpha also requires automated
tests, companion contract evidence, migration safety, reproducible packaging,
source integrity, and a complete known-limitations record. Later channels add
visual, parity, platform, performance, leak, uninstall, engine, and community
evidence. A prerelease ledger cannot approve a stable package.

## Host release dependency

KFP does not package a voxel host. A public release names compatible released
versions of Battle Art and Dramaless and links to their owner-controlled release
pages. Local branches, forks, pull requests, patches, and mocked tests are
engineering evidence, not host releases.

## Asset permission

Use `docs/asset-permission-request-template.md`. Keep the original creator reply
and asset inventory in the private evidence directory. After review, commit a
redacted `docs/rights-approval.json` with the evidence SHA-256 and a private
evidence locator. Never commit the private conversation or identity details.

## Signing setup

Release tags use GPG because the packager verifies a full `VALIDSIG`
fingerprint. Configure the repository, not global Git:

```text
git config --local gpg.program "C:/Program Files/Git/usr/bin/gpg.exe"
git config --local user.signingkey <full-fingerprint>
git config --local tag.gpgSign true
```

Create or import the protected private key outside automation. Back it up before
use. Set `KFP_TRUSTED_SIGNING_KEY` to the full fingerprint for packaging.

## Pre-tag checks

Run from a clean source tree:

```text
luajit tools/check_syntax.lua
luajit tools/validate_project.lua
luajit tools/run_tests.lua
luajit tools/run_benchmarks.lua
python -m unittest tests.tools.test_package_release -v
```

Record the exact engine and host commits. Re-audit the latest Gen1recomp release.
Confirm that the selected ledger has the exact manifest version, channel, tag,
gate set, affirmative approval, and immutable evidence hashes.

## Tag and build

Create a signed annotated tag only after the selected ledger and rights record
are approved:

```text
git tag -s v<manifest-version> -m "Kanto First Person v<manifest-version>"
git verify-tag --raw v<manifest-version>
git push origin v<manifest-version>
```

Build from an audited engine checkout and a clean exact tag:

```text
python tools/package_release.py \
  --release \
  --engine <audited-gen1recomp-checkout> \
  --output-dir <new-empty-output-directory> \
  --epoch <SOURCE_DATE_EPOCH> \
  --trusted-signing-key <full-fingerprint>
```

Run the build twice into different empty directories and compare the ZIP and
`.modpkg` byte for byte.

## Artifact set

Every published version has exactly these release assets:

```text
ds_fp_ceiling-<version>.modpkg
ds_fp_ceiling-<version>.zip
ds_fp_ceiling-<version>-SHA256SUMS.txt
ds_fp_ceiling-<version>-attestation.json
```

The archive root contains `manifest.json`. The ZIP and `.modpkg` contain only
allowlisted runtime files. The attestation records the source tag, source commit,
engine commit, build epoch, release channel, file hashes, and artifact hashes.

## GitHub publication

1. Verify the repository visibility and intended audience.
2. Create a draft release from the exact signed tag.
3. Upload the four verified artifacts.
4. Include compatibility, installation, migration, rollback, known limits, and
   host release links.
5. Mark alpha, beta, and RC releases as prereleases.
6. Publish only after a second person verifies the tag, hashes, and release text.

Do not upload a private test build. Its attestation has `publishable=false`.

## Rollback

Never repair an old patched host in place. The rollback and upgrade path is:

1. Close Gen1recomp.
2. Reinstall a verified clean host release.
3. Replace KFP with the selected signed package.
4. Start Gen1recomp and check the compatibility diagnostic.
5. Restore the prior signed KFP package if the new version fails.
