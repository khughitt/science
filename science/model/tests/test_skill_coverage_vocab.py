from science_model.skill_coverage import (
    DOMAIN_KEYS,
    ENROLLMENT_STATUSES,
    GENERATION_3_DOMAINS,
    EnrollmentStatus,
)


def test_domain_keys_are_exactly_the_v1_set():
    # Exact equality, not membership: the closed set is the contract, and a silently-added key
    # would change coverage behavior without a test noticing.
    assert DOMAIN_KEYS == frozenset({"molecular-measurement"})


def test_enrollment_status_members():
    assert EnrollmentStatus.ENROLLED == "enrolled"
    assert EnrollmentStatus.OUT_OF_DOMAIN == "out-of-domain"


def test_enrollment_statuses_are_derived_from_the_enum():
    # The set constant must track the enum -- not a second, drift-prone hand-list.
    assert ENROLLMENT_STATUSES == frozenset(status.value for status in EnrollmentStatus)


def test_generation_3_domains_are_a_subset_of_domain_keys():
    assert GENERATION_3_DOMAINS <= DOMAIN_KEYS


def test_molecular_measurement_requires_generation_3():
    assert "molecular-measurement" in GENERATION_3_DOMAINS
