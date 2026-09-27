# Human Minority Public Boundary — Early Source Drop

This document defines the supported boundary of this Early Source Drop.

## Included

The artifact contains a deliberately small, inspectable set of provider-neutral primitives and contracts:

- deterministic JSON and hashing helpers;
- claim, evidence, verification-result and acceptance contracts;
- canonical acceptance composition used by the private control lifecycle;
- a runnable exact-artifact verification bundle path over candidate bytes, producer claim, explicit verifier trust input and bound verifier results;
- an installable `human-minority` CLI limited to version reporting, public artifact inspection and that exact portable verification vertical;
- bounded repair contracts and repair-scope policy;
- source identity and portable-path primitives;
- provider-neutral credential-reference, observation and freshness contracts;
- curated public tests and repository metadata.

Canonical verification primitives remain under `seed.app`; the thin public product package and console entry point use the `human_minority` namespace.

## Excluded

This artifact does not include or claim to provide:

- production agent or provider execution;
- sandbox or host-confinement implementations;
- operational orchestration or deployment machinery;
- production secret backends or credential custody;
- private development history, planning records or operator tooling;
- remote verifier identity attestation;
- the complete authority → verify → repair → re-verify → integrate runtime.

## Trust rules

A claim is not proof. Verification results, repair admission and final acceptance remain distinct facts.

The runnable exact-artifact path does not accept a producer-supplied acceptance decision. It recomputes exact candidate identity, requires verifier results to match an explicit obligation and trusted-verifier set, rejects producer/verifier role collapse, and passes only the exact required result set into canonical acceptance composition. Trusted verifier IDs are explicit authority input, not cryptographic identity attestation.

Provider observation freshness is not authorization. A `FRESH` observation says that the observation is current and integrity-valid for the expected route/stage; any required fact must still be explicitly `SATISFIED` by the consuming policy.

Repair scope is fail-closed. Forbidden paths are checked through conservative portable identity. Allowed paths require exact repository spelling; case-only or Unicode-equivalent aliases do not widen the authorized mutation boundary.

## Security scope

Do not infer secure execution of untrusted repository code from this source drop. The supported security boundary is limited to properties directly enforced by the shipped code and tests.

See `SECURITY.md` for reporting instructions and unsupported security assumptions.
