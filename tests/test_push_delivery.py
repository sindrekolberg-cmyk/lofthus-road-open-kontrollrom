from api import push_delivery


def _token(i: int) -> str:
    return f"ExpoPushToken[abcdefghijklmnopqrstuvwxyz{i:04d}]"


def test_personalized_pushes_are_chunked_at_100(monkeypatch):
    seen_sizes: list[int] = []

    def fake_post(messages):
        seen_sizes.append(len(messages))
        return ([{"status": "ok", "id": f"ticket-{i}"} for i, _ in enumerate(messages)], None)

    monkeypatch.setattr(push_delivery, "_post_chunk", fake_post)
    messages = [
        {"to": _token(i), "title": f"Tittel {i}", "body": f"Melding {i}", "data": {"i": i}}
        for i in range(205)
    ]

    result = push_delivery.send_expo_messages(messages)

    assert seen_sizes == [100, 100, 5]
    assert result["accepted"] == 205
    assert result["failed"] == 0
    assert result["http_batches"] == 3


def test_device_not_registered_is_exposed_for_cleanup(monkeypatch):
    dead = _token(1)

    def fake_post(messages):
        return ([{"status": "error", "details": {"error": "DeviceNotRegistered"}}], None)

    monkeypatch.setattr(push_delivery, "_post_chunk", fake_post)
    result = push_delivery.send_expo_messages([{"to": dead, "title": "x", "body": "y"}])

    assert result["accepted"] == 0
    assert result["failed"] == 1
    assert result["invalid_tokens"] == [dead]
