import asyncio
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import click as click


class App:
    directory: Path


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


def read_file(filename: str):
    path = App.directory / filename
    return path.read_text()


async def handler(client_socket):
    loop = asyncio.get_running_loop()
    try:
        data = await loop.sock_recv(client_socket, 1024)
        if not data:
            return

        request = parse_request(data)
        print("Got request", request)
        path_parts = request.path_parts
        match path_parts:
            case ("", ""):
                response = Response("HTTP/1.1", 200, "OK", [], "")
            case ("", "echo", var):
                response = Response("HTTP/1.1", 200, "OK", [("Content-Type", "text/plain")], var)
            case ("", "user-agent"):
                headers = dict(request.headers)
                response = Response("HTTP/1.1", 200, "OK", [("Content-Type", "text/plain")], headers["User-Agent"])
            case ("", "files", filename):
                content = read_file(filename)
                response = Response("HTTP/1.1", 200, "OK", [("Content-Type", "application/octet-stream")], content)
            case _:
                response = Response("HTTP/1.1", 404, "Not Found", [], "")

        print("Sending response", response)
        await loop.sock_sendall(client_socket, response.raw())
    finally:
        client_socket.close()


async def main():
    server_socket = socket.create_server(("localhost", 4221), reuse_port=False)
    server_socket.setblocking(False)
    loop = asyncio.get_running_loop()

    while True:
        # wait until client connects, note we're still accepting clients synchronously
        client_socket, _ = await loop.sock_accept(server_socket)
        client_socket.setblocking(False)
        # handle the request asynchronously, pass the client socket to handler to handle i/o main loop
        asyncio.create_task(handler(client_socket))


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


@click.command
@click.argument("--directory", type=click.Path)
def start_server(directory):
    App.directory = Path(directory)
    asyncio.run(main())


if __name__ == "__main__":
    start_server()
