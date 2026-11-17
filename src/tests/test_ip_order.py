from src.utils import _resolve_public_ip_candidates


def test_ipv4_is_tried_before_ipv6(monkeypatch):
    infos = [(0, 0, 0, "", (ip, 0)) for ip in ("2606:4700::1", "93.184.216.34", "2606:4700::2", "8.8.8.8")]
    monkeypatch.setattr("src.utils.socket.getaddrinfo", lambda host, port: infos)

    ips = _resolve_public_ip_candidates("example.com")

    assert [":" in ip for ip in ips] == [False, False, True, True]
