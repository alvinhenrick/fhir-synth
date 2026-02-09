"""Tests for utilities (RNG, ID generation, dates)."""

from datetime import datetime

from fhir_synth.utils import DateGenerator, DeterministicRNG, IDGenerator


def test_deterministic_rng_seed():
    """Test that the same seed produces same results."""
    rng1 = DeterministicRNG(42)
    rng2 = DeterministicRNG(42)

    vals1 = [rng1.random() for _ in range(10)]
    vals2 = [rng2.random() for _ in range(10)]

    assert vals1 == vals2


def test_deterministic_rng_fork():
    """Test forking RNG with namespace."""
    rng = DeterministicRNG(42)
    child1 = rng.fork("child1")
    child2 = rng.fork("child2")

    # Children should produce different values from each other
    val1 = child1.random()
    val2 = child2.random()
    assert val1 != val2

    # But same fork should be deterministic
    rng_copy = DeterministicRNG(42)
    child1_copy = rng_copy.fork("child1")
    assert child1_copy.random() == val1


def test_id_generator_sequential():
    """Test sequential ID generation."""
    rng = DeterministicRNG(42)
    id_gen = IDGenerator(rng)

    id1 = id_gen.sequential("Patient")
    id2 = id_gen.sequential("Patient")
    id3 = id_gen.sequential("Encounter")

    assert id1 == "Patient-1"
    assert id2 == "Patient-2"
    assert id3 == "Encounter-1"


def test_id_generator_namespaced():
    """Test namespaced ID generation."""
    rng = DeterministicRNG(42)
    id_gen = IDGenerator(rng)

    id1 = id_gen.namespaced("Patient", "baylor")
    id2 = id_gen.namespaced("Patient", "sutter")
    id3 = id_gen.namespaced("Patient", "baylor")

    assert id1 == "baylor-Patient-1"
    assert id2 == "sutter-Patient-1"
    assert id3 == "baylor-Patient-2"


def test_id_generator_uuid_deterministic():
    """Test that UUID generation is deterministic."""
    rng1 = DeterministicRNG(42)
    rng2 = DeterministicRNG(42)

    id_gen1 = IDGenerator(rng1)
    id_gen2 = IDGenerator(rng2)

    uuid1 = id_gen1.uuid()
    uuid2 = id_gen2.uuid()

    assert uuid1 == uuid2


def test_date_generator_within_bounds():
    """Test that generated dates are within bounds."""
    rng = DeterministicRNG(42)
    start = datetime(2020, 1, 1)
    end = datetime(2023, 1, 1)

    date_gen = DateGenerator(rng, start, end)

    for _ in range(100):
        dt = date_gen.random_datetime()
        assert start <= dt <= end


def test_date_generator_deterministic():
    """Test that date generation is deterministic."""
    rng1 = DeterministicRNG(42)
    rng2 = DeterministicRNG(42)
    start = datetime(2020, 1, 1)
    end = datetime(2023, 1, 1)

    date_gen1 = DateGenerator(rng1, start, end)
    date_gen2 = DateGenerator(rng2, start, end)

    dates1 = [date_gen1.random_datetime() for _ in range(10)]
    dates2 = [date_gen2.random_datetime() for _ in range(10)]

    assert dates1 == dates2


def test_date_generator_between():
    """Test date generation between specific dates."""
    rng = DeterministicRNG(42)
    start = datetime(2020, 1, 1)
    end = datetime(2023, 1, 1)

    date_gen = DateGenerator(rng, start, end)

    after = datetime(2021, 6, 1)
    before = datetime(2021, 12, 1)

    for _ in range(20):
        dt = date_gen.datetime_between(after, before)
        assert after <= dt <= before
