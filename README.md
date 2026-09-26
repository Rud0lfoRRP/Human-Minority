# Human Minority

> **More agents. Same veto.**
>
> **Claim is not proof.**

[![Public CI](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-ci.yml/badge.svg)](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-ci.yml)
[![Public Integrity](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-integrity.yml/badge.svg)](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-integrity.yml)
[![CodeQL](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-codeql.yml/badge.svg)](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-codeql.yml)
[![OpenSSF Scorecard](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-scorecard.yml/badge.svg)](https://github.com/Rud0lfoRRP/Human-Minority/actions/workflows/public-scorecard.yml)
[![License: PolyForm Perimeter 1.0.1](https://img.shields.io/badge/license-PolyForm%20Perimeter%201.0.1-informational)](LICENSE)

Human Minority is a **source-available verification and policy-enforcement layer for AI coding agents**.

A coding agent can say *"tests passed"* or *"ready to merge."* Human Minority asks a different set of questions: **which exact candidate, which evidence, which verifier, and who still has authority to accept it?**

It separates what an agent *claims* from what an independent verifier can *prove*. Candidate identity, evidence, verification, bounded repair and final integration remain distinct steps, with acceptance authority kept outside the agent that produced the work.

### The idea in 15 seconds

Conceptually, a failed claim should look like this:

```text
Agent claim: "Tests passed. Ready to merge."

Human Minority:
candidate       BOUND
evidence        PRESENT
verification    FAILED

decision:       NEEDS_REPAIR
next step:      bounded repair -> re-verification
```

That block illustrates the broader control model. The public source now also includes a smaller runnable exact-artifact verification vertical described below.

**Status:** Early Source Drop — inspectable public primitives plus one runnable exact-artifact verification vertical are available today; the complete `hmin` runtime/CLI is not yet published.

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
- a runnable local exact-artifact verification vertical that binds candidate bytes, producer claim, producer evidence, verifier-created result and acceptance decision;
- public tests and integrity checks for the exported slice.

The runnable vertical uses the same canonical acceptance composer as the broader control lifecycle. The exact exported files are selected from the canonical upstream through an explicit allowlist and deterministic export manifest.

### Run the public test suite

```bash
git clone https://github.com/Rud0lfoRRP/Human-Minority.git
cd Human-Minority

python -m pip install --require-hashes --only-binary=:all: -r requirements-test.txt
python -m pytest
```

### Run the exact-artifact verification vertical

A complete V1 bundle is shipped under `examples/public_verification/`:

```bash
python -m seed.app.verification.vertical \
  --candidate examples/public_verification/candidate.txt \
  --bundle examples/public_verification/bundle.json
```

The bundle declares:

- the producer identity and claim;
- the exact candidate identity expected by the obligation;
- ordered required check IDs;
- the trusted verifier IDs allowed for this decision;
- verifier result envelopes bound to the same candidate and claim.

Human Minority recomputes the candidate SHA-256 from the actual candidate bytes, rejects missing/extra/duplicate/stale results, rejects a producer acting as its own trusted verifier, and feeds only the exact required `VerificationResult` set into the same canonical acceptance reducer used by private Seed Control.

The reference module prints deterministic JSON containing candidate identity, claim/plan IDs, per-check verifier/result/status data, acceptance outcome, canonical decision ID and the overall binding fingerprint. The final product CLI will define its own stable exit-code taxonomy; this module is only a reference invocation.

This V1 demonstrates:

- exact candidate-byte identity;
- producer claim vs verifier-result separation;
- explicit trusted-verifier input;
- exact candidate/claim/check/evidence bindings;
- canonical Seed acceptance reduction;
- fail-closed missing, substituted or ambiguous proof.

It does **not** demonstrate secure execution of untrusted code, Docker/WSL confinement, cryptographic verifier authentication, provider orchestration, autonomous repair, merge authority or deployment authority. The trusted-verifier list is explicit caller-supplied authority input to this portable decision; V1 does not prove the identity or provenance of the party that supplied that list.


## Current public boundary

This repository is an **Early Source Drop**: a deliberately small, inspectable subset published before the complete runnable product is ready.

It is **not**:

- the complete Human Minority product;
- a production-ready release with compatibility or support guarantees;
- proof that untrusted repository code can already be executed safely on every platform;
- the private provider/runtime/orchestration stack;
- private self-improvement or internal orchestration machinery;
- a hosted AI service with bundled inference credits.

Public API, CLI and runtime interfaces may still change and are not yet covered by compatibility or support guarantees.

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

**Early development · Early Source Drop**

The private canonical upstream remains separate. Public artifacts are produced through a controlled export with fresh public history rather than by exposing private Git history.
