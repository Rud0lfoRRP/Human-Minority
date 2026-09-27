# Human Minority

> **More agents. Same veto.**
>
> **Claim is not proof.**

[![Public CI](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-ci.yml/badge.svg)](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-ci.yml)
[![Public Integrity](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-integrity.yml/badge.svg)](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-integrity.yml)
[![CodeQL](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-codeql.yml/badge.svg)](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-codeql.yml)
[![OpenSSF Scorecard](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-scorecard.yml/badge.svg)](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-scorecard.yml)
[![License: PolyForm Perimeter 1.0.1](https://img.shields.io/badge/license-PolyForm%20Perimeter%201.0.1-informational)](LICENSE)

Human Minority is a **source-available verification layer for AI coding workflows**.

It is built around a simple rule: an agent saying *"tests passed"* or *"ready to merge"* is still only a claim. Human Minority binds verification to an exact candidate, explicit evidence and verifier results, then produces a decision without giving the producing agent authority to accept or merge its own work.

**Current status:** early development. The repository is still published as an `EARLY_SOURCE_DROP`, but the public V1 CLI is installable and runnable today. Private execution, provider orchestration and deployment machinery are outside this public boundary.

## Quick start

Requires Python **3.12–3.14**.

```bash
git clone https://github.com/Rud0lfoRRP/Human-Minority.git
cd Human-Minority

python -m pip install --no-deps .

human-minority --version
human-minority inspect
human-minority verify \
  --candidate examples/public_verification/candidate.txt \
  --bundle examples/public_verification/bundle.json
```

The package has no runtime dependencies beyond the Python standard library.

To run the public test suite:

```bash
python -m pip install --require-hashes --only-binary=:all: -r requirements-test.txt
python -m pytest
```

## What is available today

The public artifact contains:

- an installable `human-minority` CLI;
- exact candidate-byte identity using SHA-256;
- claim, evidence, verification-result and acceptance contracts;
- a runnable exact-artifact verification vertical;
- deterministic JSON and hashing helpers;
- source/candidate and portable-path contracts;
- bounded repair request, lineage and scope-policy primitives;
- provider-neutral credential-reference, observation and freshness contracts;
- a committed export manifest plus public integrity checks;
- curated public tests and CI.

The exported verification path uses the same canonical acceptance composition as the upstream implementation. It does not replace it with a demo-only reducer.

## CLI

### `human-minority --version`

Reports the public product version.

```bash
human-minority --version
human-minority --version --json
```

### `human-minority inspect`

Checks the **committed Git `HEAD`** against the committed `export-manifest.json`.

It verifies tracked-file membership, file modes, per-file SHA-256 values, the public boundary document and the security contact.

Example:

```bash
human-minority inspect --json
```

Important semantics:

- `integrity: PASS` means the committed tree is internally consistent with its committed manifest;
- `integrity_scope: COMMITTED_HEAD` means uncommitted files are outside that integrity decision;
- `working_tree_clean` reports whether the checkout differs from committed `HEAD`;
- `authenticity: NOT_ESTABLISHED` means self-consistency alone does **not** prove that the checkout is an official published artifact.

To establish authenticity, compare the reported `public_commit` and `manifest_sha256` with values obtained from a trusted published repository or release reference.

### `human-minority verify`

Evaluates an exact candidate against a strict verification bundle:

```bash
human-minority verify \
  --candidate examples/public_verification/candidate.txt \
  --bundle examples/public_verification/bundle.json
```

The bundle binds:

- producer identity and claim;
- exact candidate identity;
- required check IDs;
- trusted verifier IDs;
- verifier result envelopes bound to the same candidate and claim.

Human Minority recomputes the candidate SHA-256 from the actual bytes, rejects missing, extra, duplicate or mismatched results, rejects producer/verifier role collapse, and passes only the required result set into canonical acceptance composition.

The lower-level reference invocation remains available:

```bash
python -m seed.app.verification.vertical \
  --candidate examples/public_verification/candidate.txt \
  --bundle examples/public_verification/bundle.json
```

## Exit codes

The public CLI uses the product exit taxonomy:

| Exit | Meaning |
|---:|---|
| `0` | command succeeded / verification accepted |
| `1` | valid negative outcome, such as drift or repair-needed verification |
| `2` | invalid usage, input or binding |
| `3` | required environment or checkout is unavailable |
| `5` | unexpected internal failure |
| `130` | interrupted |

A negative verification result is not treated as a CLI crash.

## Why Human Minority exists

AI coding agents can write code, run tools and report success. None of that makes their report authoritative.

Human Minority keeps four things separate:

1. **Claim** — what the producing agent says happened.
2. **Evidence and verification** — what can be independently checked against the exact candidate.
3. **Repair** — what may be changed inside an allowed scope after verification fails.
4. **Authority** — who may accept, merge or deploy the result.

The intended control loop is:

```text
task / authority
      |
      v
candidate + claim
      |
      v
bind exact candidate
      |
      v
independent verification
   /       |        \
 FAIL  INCONCLUSIVE  PASS
   |                  |
bounded repair        |
   |                  |
re-verification ------+
      |
      v
human / policy decision
      |
      v
controlled integration
```

The public V1 CLI implements the portable verification portion of that model. It does not claim to publish the complete private execution and orchestration system.

## What this release does not claim

This public artifact does **not** demonstrate or provide:

- secure execution of arbitrary untrusted repositories;
- Docker or WSL confinement as a public product guarantee;
- production agent/provider orchestration;
- cryptographic verifier identity attestation;
- autonomous repair execution;
- merge or deployment authority;
- production secret custody;
- bundled AI inference credits;
- compatibility or support guarantees for a stable production release.

The trusted-verifier list in the public verification bundle is explicit authority input. V1 verifies the binding and decision logic; it does not prove the real-world identity of whoever supplied that list.

See [PUBLIC_BOUNDARY.md](PUBLIC_BOUNDARY.md) for the exact exported capability boundary.

## Public artifact and provenance

Human Minority is exported from a separate canonical upstream through an explicit allowlist and deterministic manifest.

The public repository contains only the selected artifact, not the private development history.

Useful files:

- [export-manifest.json](export-manifest.json) — committed file inventory and SHA-256 bindings;
- [PUBLIC_BOUNDARY.md](PUBLIC_BOUNDARY.md) — what this artifact includes and excludes;
- [SECURITY.md](SECURITY.md) — security scope and reporting instructions;
- [CONTRIBUTING.md](CONTRIBUTING.md) — current contribution policy.

Do not infer security guarantees from design intent. Only properties enforced by the shipped code and documented public boundary apply.

## Technical notes

- Python compatibility target: **3.12–3.14**.
- Runtime dependencies: **standard library only**.
- The project-specific canonical JSON format is `seed-canonical-json-v1`; it does not claim RFC 8785 / JCS compatibility.
- Portable-path collision checks are intentionally conservative across supported host filesystems.
- Provider observation `FRESH` means current, route-bound and integrity-valid; it is not authorization and does not turn a negative fact into a permissive one.
- The exported canonical verification primitives remain under the `seed.app` namespace; `human_minority` is the thin public product/CLI package around the published capability set.

## Security

The public artifact intentionally excludes private operational execution machinery. It should not be treated as a finished sandbox or complete secure-execution product.

See [SECURITY.md](SECURITY.md).

## License

Human Minority is **source-available, not OSI open source**.

The repository is licensed under **PolyForm Perimeter 1.0.1**. The shipped [LICENSE](LICENSE) file controls; this README is not a substitute for the license text.

## Contributions

Issues and technical feedback are welcome.

External code contributions are not currently incorporated until contribution and relicensing terms are explicitly defined. Forking or modifying the published source remains governed by the shipped license.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Status

**Early development · public V1 CLI available · artifact stage: `EARLY_SOURCE_DROP`**
