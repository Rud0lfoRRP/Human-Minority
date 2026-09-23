from __future__ import annotations

from pathlib import Path

import seed
import seed.app.core as core_package
import seed.app.core.hashing as hashing
import seed.app.repair as repair_package
import seed.app.source as source_package
import seed.app.providers as providers_package
import seed.app.verification as verification_package
from seed.app.core.errors import CoreErrorCode


def test_schema_bound_hashing_is_not_in_early_drop() -> None:
    assert not hasattr(hashing, "contract_self_hash")
    assert not hasattr(hashing, "verify_contract_self_hash")
    assert not hasattr(hashing, "_contract_self_hash_with_registry")


def test_private_runtime_error_vocabulary_is_not_in_early_drop() -> None:
    for name in (
        "STORAGE_NOT_FOUND",
        "JOURNAL_INVALID",
        "CHECKPOINT_INVALID",
        "LIFECYCLE_INVALID",
        "CANONICAL_CASE_FORBIDDEN",
    ):
        assert not hasattr(CoreErrorCode, name)


def test_curated_initializers_do_not_reexport_private_subsystems() -> None:
    assert not hasattr(core_package, "SchemaRegistry")
    assert not hasattr(repair_package, "RepairVerificationProof")
    assert not hasattr(source_package, "GitSourceAdapter")
    assert not hasattr(providers_package, "execute_wsl_run")
    assert not hasattr(verification_package, "execute_verification_plan")


def test_seed_root_is_a_regular_package() -> None:
    assert seed.__file__ is not None
    assert Path(seed.__file__).name == "__init__.py"
