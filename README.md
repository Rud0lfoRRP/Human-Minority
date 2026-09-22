# Human Minority

> **More agents. Same veto.**
>
> Human-governed verification core for multi-agent software workflows.
>
> **Claim is not proof.**
>
> **Early development · Early Source Drop · Not a supported release**

Human Minority is a source-available verification and policy-enforcement core for software-engineering work produced by AI agents.

It focuses on a simple boundary: an agent may produce a candidate or evidence, but that output does not become authority or truth merely because the agent says the work is complete. Human authority, exact candidate identity, evidence, independent verification, bounded repair, re-verification and controlled integration remain separate concerns.

**Claim is not proof** is a system principle, not a claim that this Early Source Drop already implements the complete execution and verification vertical.

## What this repository is

This repository is an **Early Source Drop**: a deliberately small, inspectable subset published before the complete runnable product is ready.

The initial public boundary exposes provider-neutral primitives such as:

- deterministic/canonical identity helpers;
- claims, evidence and verification-result contracts;
- bounded repair request and lineage contracts;
- repair admission/scope policy;
- source/candidate contracts and portable path rules;
- provider-neutral facts, credential references and freshness policy.

The exact exported files are selected from the private canonical upstream through an explicit allowlist and deterministic export manifest.

## What this repository is not

This Early Source Drop is **not**:

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

The broader product direction is:

> **Controlled execution and independent verification for untrusted software agents.**

That describes the intended full system, not the capability boundary of this Early Source Drop.

The intended product model is self-service and **BYO AI / BYO Compute**. Human Minority should control and verify agent work without making the maintainer's API spend the customer's hidden cost center.

A future runnable public preview must demonstrate a bounded vertical similar to:

```text
human/task authority
→ exact candidate identity
→ verification
→ FAIL / INCONCLUSIVE / PASS
→ bounded repair candidate
→ re-verification
→ decision
→ controlled integration
```

and must fail closed when a required verification or confinement boundary cannot be established.

## Requirements

This Early Source Drop is tested against **Python 3.12–3.14**. The exported runtime modules use only the Python standard library; `pytest` is needed only for the test suite.

Run examples from the repository root so the exported `seed.app` namespace is importable.

## Quick example

```python
from seed.app.core.hashing import canonical_sha256
from seed.app.source.portable_paths import canonical_path

path = canonical_path("src/example.py")
digest = canonical_sha256({"path": path, "claim": "candidate-produced"})

print(path)
print(digest)
```

This demonstrates two public primitives only; it is not the complete Human Minority execution or verification vertical.

## Running tests

From the repository root:

```bash
python -m pip install -r requirements-test.txt
python -m pytest
```

If the `pytest` console script is on `PATH`, a plain `pytest` invocation works too; the repository ships `pytest.ini` with the public package root and test directory configured.

## Security status

The Early Source Drop intentionally omits private operational execution machinery. It must not be described as a finished sandbox or as a complete secure-execution product.

See `SECURITY.md` for the exact supported security boundary and reporting instructions.

## Licensing

Human Minority is **source-available**, not OSI open source.

The public license is **PolyForm Perimeter 1.0.1**. The shipped `LICENSE` file controls.

The license permits use, modification and distribution for permitted purposes, while excluding providing to others a product that competes with the software as defined by the license terms. Do not rely on this README as a substitute for the license text.

## Contributions

Issues and technical feedback are welcome once the public repository opens.

External code contributions are not accepted/incorporated until contribution and relicensing terms are explicitly defined. Forking or modifying published code remains governed by the shipped software license; contribution policy only governs what the upstream project accepts back.

## Status

The private canonical upstream remains separate. Public artifacts are produced through a controlled export with fresh public history rather than by exposing private Git history.
