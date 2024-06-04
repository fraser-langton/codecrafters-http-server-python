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

    @property
    def path_parts(self):
        return self.path.split("/")


@dataclass(slots=True)
class Response:
    version: str
    status: int
    message: str
    headers: List[Tuple[str, str]]
    body: str

    def __post_init__(self):
        self.headers.append(("Content-Length", str(len(self.body.encode()))))

    def raw(self) -> bytes:
        headers = "\r\n".join([f"{k}:{v}" for k, v in self.headers])
        return f"{self.version} {self.status} {self.message}\r\n{headers}\r\n\r\n{self.body or ''}".encode()


def main():
    server_socket = socket.create_server(("localhost", 4221), reuse_port=False)
    conn, addr = server_socket.accept()

    with conn:
        while True:
            data = conn.recv(1024)
            if not data:
                break

            request = parse_request(data)
            print("Got request", request)
            path_parts = request.path_parts
            match path_parts:
                case ("", ""):
                    response = Response("HTTP/1.1", 200, "OK", [], "")
                case ("", "echo", var):
                    response = Response("HTTP/1.1", 200, "OK", [("Content-Type", "text/plain")], var)
                case _:
                    response = Response("HTTP/1.1", 404, "Not Found", [], "")
            print("Sending response", response)
            conn.sendall(response.raw())


def parse_request(raw_request: bytes) -> Request:
    i = raw_request.index(b"\r\n")
    method, path, version = raw_request[:i].split(b" ")

    headers: list[Tuple[str, str]] = []

    while True:
        ni = raw_request.index(b"\r\n", i + 1)
        if ni - i == 2:  # indicates a blank line
            break
        header_k, header_v = raw_request[i + 2: ni].decode().split(": ")
        headers.append((header_k, header_v))
        i = ni

    body = raw_request[ni + 2:]
    return Request(method.decode(), path.decode(), version.decode(), headers, body.decode())


if __name__ == "__main__":
    main()
