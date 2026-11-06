from pathlib import Path

from edrockmaster.infrastructure.instance_lock import LOCK_NAME, InstanceLock


def test_a_second_acquisition_fails_until_the_first_is_released(tmp_path: Path) -> None:
    first = InstanceLock(tmp_path)
    second = InstanceLock(tmp_path)

    assert first.acquire()
    assert not second.acquire()

    first.release()

    assert second.acquire()
    second.release()


def test_the_lock_is_created_in_a_missing_directory(tmp_path: Path) -> None:
    directory = tmp_path / "missing" / "EDRockMaster"

    with InstanceLock(directory) as lock:
        assert lock.acquire()
        assert (directory / LOCK_NAME).is_file()


def test_releasing_a_lock_not_held_does_nothing(tmp_path: Path) -> None:
    InstanceLock(tmp_path).release()


def test_acquiring_twice_in_the_same_object_is_fine(tmp_path: Path) -> None:
    with InstanceLock(tmp_path) as lock:
        assert lock.acquire()
        assert lock.acquire()
