# Blaze Universe TUF Publication Runbook

This runbook defines the Milestone 10 Phase C.2 release boundary. Published
repositories contain no private keys. Root and targets signing happens on an
offline machine; snapshot and timestamp signing happens on the publisher.

## Trust layout

Each channel has an independent root of trust:

- `stable`: user-facing, production packages only.
- `staging`: release candidates and explicit test fixtures.

The offline key store contains only `root` and `targets` private keys. The
online key store contains only `snapshot` and `timestamp` private keys. Both
stores contain the same public-key inventory. Key files and private directories
must retain mode `0600` and `0700` respectively.

The generated keys under `build/m10-c2-keys/` are disposable acceptance-test
keys. They must never be uploaded or promoted to a public repository.

## Initial key ceremony

Run this on an encrypted, offline release workstation. Store two encrypted
backups of the offline directory in separate physical locations.

```sh
python3 tools/publish-tuf-repository.py keygen \
  --offline-dir /secure/blaze-tuf/offline \
  --online-dir /transfer/blaze-tuf/online
```

Move only the `online` directory to the publication host. Never copy the
offline private directory to a network-connected server.

## Offline signing

Use a monotonically increasing metadata version and a fixed, recorded
`SOURCE_DATE_EPOCH`. The stable policy automatically excludes the known
conflict, corruption, dependency-cycle and broken-format fixtures.

```sh
python3 tools/publish-tuf-repository.py offline-sign \
  --channel stable \
  --packages-dir build/packages \
  --offline-dir /secure/blaze-tuf/offline \
  --bundle-dir /transfer/blaze-stable-vVERSION \
  --source-date-epoch EPOCH \
  --version VERSION
```

Transfer the resulting bundle to the publisher. The online step verifies every
transferred file before signing or changing the live channel.

## Atomic online publication

```sh
python3 tools/publish-tuf-repository.py online-publish \
  --bundle-dir /transfer/blaze-stable-vVERSION \
  --online-dir /srv/blaze-tuf/online \
  --output-root /srv/blaze-repository
```

The publisher refuses metadata version rollback, refuses a different payload
at an already-published version, stages all files in a sibling directory,
fsyncs them, and atomically exchanges the channel directory. The previous
channel is restored if activation fails.

## Required release checks

```sh
python3 tools/test-m10-phase-c2.py
(cd /srv/blaze-repository/stable && sha256sum -c SHA256SUMS)
python3 tools/verify_tuf_independent.py /srv/blaze-repository/stable
find /srv/blaze-repository -type f \
  \( -name '*.key' -o -name private_keys.json \) -print
```

The final `find` command must print nothing. Verify `release-manifest.sig`
against the snapshot public key recorded in `metadata/root.json`. Public upload
automation and mirror failover belong to Phase C.3.
