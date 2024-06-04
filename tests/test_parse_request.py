from app.main import Request, parse_request


def test_parse_empty_req():
    request = b"GET / HTTP/1.1\r\n\r\n"

    assert parse_request(request) == Request(
        "GET",
        "/",
        "HTTP/1.1",
        [],
        "",
    )


def test_ih0_example():
    request = b"GET /index.html HTTP/1.1\r\nHost: localhost:4221\r\nUser-Agent: curl/7.64.1\r\nAccept: */*\r\n\r\n"

    assert parse_request(request) == Request(
        "GET",
        "/index.html",
        "HTTP/1.1",
        [
            ("Host", "localhost:4221"),
            ("User-Agent", "curl/7.64.1"),
            ("Accept", "*/*")
        ],
        "",
    )
