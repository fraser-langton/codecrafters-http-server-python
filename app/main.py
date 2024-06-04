import socket
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(slots=True)
class Request:
    method: str
    path: str
    version: str
    headers: List[Tuple[str, str]]
    body: Optional[str]


@dataclass(slots=True)
class Response:
    version: str
    status: int
    message: str
    headers: List[Tuple[str, str]]
    body: Optional[str]

    def raw(self) -> bytes:
        return f"{self.version} {self.status} {self.message}\r\n\r\n".encode()


def main():
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    conn, addr = server_socket.accept()

    # respond to requests
    with conn:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            request = parse_request(data)
            if request.path == "/":
                response = Response("HTTP/1.1", 200, "OK", [], None)
            else:
                response = Response("HTTP/1.1", 404, "Not Found", [], None)
            conn.sendall(response.raw())


def parse_request(raw_request: bytes) -> Request:
    i = raw_request.index(b"\r\n")
    method, path, version = raw_request[:i].split(b" ")

    headers: list[Tuple[str, str]] = []

    while True:
        ni = raw_request.index(b"\r\n", i + 1)
        if ni - i == 2:  # indicates a blank line
            break
        header_k, header_v = raw_request[i + 2 : ni].decode().split(": ")
        headers.append((header_k, header_v))
        i = ni

    body = raw_request[ni + 2 :]
    return Request(method.decode(), path.decode(), version.decode(), headers, body.decode())


if __name__ == "__main__":
    main()
