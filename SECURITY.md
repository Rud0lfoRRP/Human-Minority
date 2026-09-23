# Security Policy — Early Source Drop

## Status

The first Human Minority public repository is an **Early Source Drop**, not a supported production release and not a complete sandbox product.

The initial public slice is intentionally limited to inspectable trust-model primitives and provider-neutral contracts. It does not expose the private operational execution stack as a supported public security boundary.

## Supported claims

For the Early Source Drop, security claims must be limited to properties that can be verified directly from the exported code and tests, such as deterministic representation, hash/integrity helpers, immutable contract validation, bounded path normalization, repair scope/lineage rules and provider-neutral reference handling.

Do **not** claim that the Early Source Drop safely executes untrusted repository-owned code unless a released artifact actually includes and proves the required confinement profile.

## Explicitly unsupported in the Early Source Drop

Unless a later release says otherwise, do not assume the public artifact provides:

- a production-grade sandbox for arbitrary repository checks;
- complete filesystem isolation from the host;
- universal network isolation;
- secret-store isolation for arbitrary third-party tools;
- portable process/namespace isolation on every OS;
- production provider credential custody;
- automatic safe execution of arbitrary AI-agent output;
- a complete authority → verify → repair → re-verify → integrate runtime.

## Fail-closed direction for a future runnable preview

A future runnable Human Minority preview must stop or produce an explicit `INCONCLUSIVE`/equivalent state when its required verifier/confinement boundary cannot be established. It must not silently fall back to executing candidate-controlled code with ambient maintainer/verifier authority.

The supported profile must document its exact operating-system/container/runtime assumptions and prove the corresponding filesystem, environment/secret, network, child-process and resource boundaries.

## Reporting a security issue

Report security issues privately to **humanminority.security@proton.me**.

This maintainer-controlled mailbox is the publication security contact. GitHub private vulnerability reporting may also be enabled for the public repository as an additional private reporting channel.

Do not include secrets, live credentials, private customer data or exploit details affecting an unpatched deployment in a public issue.

## Scope changes

Security guarantees belong to a specific released artifact and profile. A planning document, roadmap item, private implementation branch or passing unit test does not by itself extend the supported public security boundary.
