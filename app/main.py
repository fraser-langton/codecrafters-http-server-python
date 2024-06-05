import asyncio
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import click as click


class App:
    directory: Path
    encoding = {"gzip"}


@dataclass(slots=True)
class Request:
    method: str
    path: str
    version: str
    headers: List[Tuple[str, str]]
    body: Optional[str]

    def __post_init__(self):
        self.headers = [(k.lower(), v.lower()) for k, v in self.headers]

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
        self.headers.append(("content-length", str(len(self.body.encode()))))
        self.headers = [(k.lower(), v.lower()) for k, v in self.headers]

    def raw(self) -> bytes:
        headers = "\r\n".join([f"{k}:{v}" for k, v in self.headers])
        return f"{self.version} {self.status} {self.message}\r\n{headers}\r\n\r\n{self.body or ''}".encode()


def read_file(filename: str):
    path = App.directory / filename
    return path.read_text()


def write_file(filename: str, content: str):
    path = App.directory / filename
    path.write_text(content)


async def handler(client_socket):
    loop = asyncio.get_running_loop()
    try:
        data = await loop.sock_recv(client_socket, 1024)
        if not data:
            return

        request = parse_request(data)
        print("Got request", request)
        path_parts = request.path_parts
        headers = dict(request.headers)
        match (request.method, path_parts):
            case "GET", ("", ""):
                response = Response("HTTP/1.1", 200, "OK", [], "")
            case "GET", ("", "echo", var):
                response_headers = [("content-type", "text/plain")]
                encoding = set(headers.get("accept-encoding", "").split(", ")) & App.encoding
                if encoding:
                    response_headers.append(("content-encoding", next(iter(encoding))))
                response = Response("HTTP/1.1", 200, "OK", response_headers, var)
            case "GET", ("", "user-agent"):
                response = Response("HTTP/1.1", 200, "OK", [("content-type", "text/plain")], headers["user-agent"])
            case "GET", ("", "files", filename):
                try:
                    content = read_file(filename)
                    response = Response("HTTP/1.1", 200, "OK", [("content-type", "application/octet-stream")], content)
                except FileNotFoundError:
                    response = Response("HTTP/1.1", 404, "Not Found", [], "")
            case "POST", ("", "files", filename):
                write_file(filename, request.body)
                response = Response("HTTP/1.1", 201, "Created", [], "")
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
@click.option("--directory", )
def start_server(directory):
    App.directory = Path(directory) if directory else Path.cwd()
    asyncio.run(main())


if __name__ == "__main__":
    start_server()
