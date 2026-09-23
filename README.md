# Human Minority

> **More agents. Same veto.**
>
> **Claim is not proof.**

[![Public CI](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-ci.yml/badge.svg)](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-ci.yml)
[![CodeQL](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-codeql.yml/badge.svg)](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-codeql.yml)
[![Public Integrity](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-integrity.yml/badge.svg)](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-integrity.yml)

Human Minority is a **source-available verification and policy-enforcement layer for software work produced by AI agents**.

It separates what an agent *claims* from what an independent verifier can *prove*. Candidate identity, evidence, verification, bounded repair and final integration remain distinct steps, with acceptance authority kept outside the agent that produced the work.

**Status:** Early Source Drop — inspectable public primitives are available today; the complete `hmin` runtime/CLI is not yet published.

## Why Human Minority?

AI coding agents can write code, run tools and report success. That does not make their report authoritative.

Human Minority is built around four rules:

- **A claim is not proof.** "Tests passed" is evidence only when independently bound and verified.
- **The candidate must be exact.** Verification must apply to the artifact that may actually be accepted.
- **Repair must stay bounded.** A failed candidate should not silently expand its own authority while fixing itself.
- **Integration is a separate decision.** Passing verification does not let the producing agent grant itself merge/deploy authority.

The goal is not to trust agents more. It is to make **more agent autonomy compatible with the same human veto**.

## Target verification loop

The broader product direction is a controlled verification loop like this:

```text
human task / authority
          │
          ▼
  candidate + evidence
          │
          ▼
bind exact candidate identity
          │
          ▼
 independent verification
      ┌────┼───────────┐
      ▼    ▼           ▼
    FAIL  INCONCLUSIVE PASS
      │                 │
      ▼                 │
 bounded repair         │
      │                 │
      ▼                 │
  re-verification ──────┘
          │
          ▼
   human decision
          │
          ▼
controlled integration
```

A future runnable public preview must fail closed when a required verification or confinement boundary cannot be established. The diagram above describes the intended full vertical; the current Early Source Drop publishes only the inspectable primitives described below.

## What you can inspect and run today

The current public boundary exposes provider-neutral building blocks for that model:

- deterministic/canonical identity helpers;
- claims, evidence and verification-result contracts;
- bounded repair request and lineage contracts;
- repair admission and scope policy;
- source/candidate contracts and portable path rules;
- provider-neutral facts, credential references and freshness policy;
- public tests and integrity checks for the exported slice.

The exact exported files are selected from the private canonical upstream through an explicit allowlist and deterministic export manifest.

### Run the public test suite

```bash
git clone https://github.com/Rud0lfoRRP/Human-Minority.git
cd Human-Minority

python -m pip install --require-hashes --only-binary=:all: -r requirements-test.txt
python -m pytest
```

### Small runnable example

The current source drop can already demonstrate deterministic binding primitives:

```python
from seed.app.core.hashing import canonical_sha256
from seed.app.source.portable_paths import canonical_path

path = canonical_path("src/example.py")
digest = canonical_sha256(
    {
        "path": path,
        "claim": "candidate-produced",
    }
)

print(path)
print(digest)
```

This example intentionally demonstrates only public primitives. It is **not** presented as the complete Human Minority execution or verification vertical.

## Current public boundary

This repository is an **Early Source Drop**: a deliberately small, inspectable subset published before the complete runnable product is ready.

It is **not**:

- the complete Human Minority product;
- a supported production release;
- proof that untrusted repository code can already be executed safely on every platform;
- the private provider/runtime/orchestration stack;
- private self-improvement or internal orchestration machinery;
- a hosted AI service with bundled inference credits.

Do not infer security guarantees from design intent. Only guarantees explicitly supported by the code and documented execution profile of a released artifact apply.

## Naming and interfaces

- Product: **Human Minority**
- Repository: **Human-Minority**
- CLI name: **`hmin`**

The `hmin` CLI name is reserved for the public product but is **not shipped in this Early Source Drop**.

The Python module namespace in this first source drop remains `seed.app`. That is an implementation namespace carried forward from the private upstream and is not the public product name.

## Product direction

> **Controlled execution and independent verification for untrusted software agents.**

That describes the intended full system, not the capability boundary of this Early Source Drop.

The intended product model is self-service and **BYO AI / BYO Compute**. Human Minority should control and verify agent work without making the maintainer's API spend the customer's hidden cost center.

## Requirements

The declared compatibility target for this Early Source Drop is **Python 3.12–3.14**. The first public CI run verified Python 3.12, 3.13 and 3.14 on Ubuntu, Windows and macOS; current public CI results remain the source of truth for continuing platform compatibility.

The exported runtime modules use only the Python standard library; `pytest` is needed only for the test suite.

Run examples from the repository root so the exported `seed.app` namespace is importable.

The shipped canonical JSON format is the project-specific `seed-canonical-json-v1` contract. It does **not** claim RFC 8785 / JCS compatibility. The 8 MiB limit applies to parsing untrusted JSON bytes; canonical serialization and hashing are not capped by that parser-input limit, so large in-memory manifests can still be hashed.

Portable path collision checks are intentionally conservative across supported host filesystems. They may reject some names that a particular filesystem would keep distinct; that is a fail-closed portability tradeoff, not a claim of byte-for-byte filesystem name equivalence.

Provider observation `FRESH` means the observation is current, route-bound and integrity-valid under the freshness policy. It does **not** mean every fact is permissive: callers that authorize selection or dispatch must still require the relevant facts to be `SATISFIED`; `BLOCKING` remains a negative fact.

## Security status

The Early Source Drop intentionally omits private operational execution machinery. It must not be described as a finished sandbox or as a complete secure-execution product.

See `SECURITY.md` for the exact supported security boundary and reporting instructions.

## Licensing

Human Minority is **source-available, not OSI open source**.

The public license is **PolyForm Perimeter 1.0.1**. The shipped `LICENSE` file controls.

The license permits use, modification and distribution for permitted purposes, while excluding providing to others a product that competes with the software as defined by the license terms. Do not rely on this README as a substitute for the license text.

## Contributions

Issues and technical feedback are welcome.

External code contributions are not accepted/incorporated until contribution and relicensing terms are explicitly defined. Forking or modifying published code remains governed by the shipped software license; contribution policy only governs what the upstream project accepts back.

See `CONTRIBUTING.md` for the current contribution boundary.

## Status

**Early development · Early Source Drop · Not a supported release**

The private canonical upstream remains separate. Public artifacts are produced through a controlled export with fresh public history rather than by exposing private Git history.
