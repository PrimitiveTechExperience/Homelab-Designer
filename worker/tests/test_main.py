from worker.main import WorkerSettings, ping


async def test_ping() -> None:
    assert await ping({}) == "pong"


def test_ping_is_registered() -> None:
    assert ping in WorkerSettings.functions
