import asyncio
import gzip
import socket
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import List, Optional, Tuple

import click as click


class App:
    directory: Path
    encoding = {"gzip"}


@dataclass(slots=True)
class Headers:
    headers: List[Tuple[str, str]]

    def __post_init__(self):
        self.headers = [(k.lower(), v.lower()) for k, v in self.headers]

    @property
    def headers_dict(self) -> dict:
        return {k: v for k, v in self.headers}


@dataclass(slots=True)
class Request(Headers):
    method: str
    path: str
    version: str
    body: Optional[str]

    @property
    def path_parts(self):
        return self.path.split("/")


@dataclass(slots=True)
class Response(Headers):
    version: str
    status: int
    message: str
    body: str
    request: Request

    def encode_body(self) -> bytes:
        encodings = set(self.request.headers_dict.get("accept-encoding", "").split(", ")) & App.encoding
        encoding = next(iter(encodings), None)
        if encoding:
            self.headers.append(("content-encoding", encoding))
            if encoding == "gzip":
                body = gzip.compress(self.body.encode())
            else:
                raise NotImplementedError
        else:
            body = self.body.encode()
        return body

    def raw(self) -> bytes:
        body = self.encode_body()
        self.headers.append(("content-length", str(len(body))))
        headers = "\r\n".join([f"{k}:{v}" for k, v in self.headers])
        return f"{self.version} {self.status} {self.message}\r\n{headers}\r\n\r\n".encode() + body


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
        make_response = partial(Response, request=request, version="HTTP/1.1")
        match (request.method, path_parts):
            case "GET", ("", ""):
                response = make_response(status=200, message="OK", headers=[], body="")
            case "GET", ("", "echo", var):
                response_headers = [("content-type", "text/plain")]
                response = make_response(status=200, message="OK", headers=response_headers, body=var)
            case "GET", ("", "user-agent"):
                response = make_response(status=200, message="OK", headers=[("content-type", "text/plain")],
                                         body=request.headers_dict["user-agent"])
            case "GET", ("", "files", filename):
                try:
                    content = read_file(filename)
                    response = make_response(status=200, message="OK",
                                             headers=[("content-type", "application/octet-stream")], body=content)
                except FileNotFoundError:
                    response = make_response(status=404, message="Not Found", headers=[], body="")
            case "POST", ("", "files", filename):
                write_file(filename, request.body)
                response = make_response(status=201, message="Created", headers=[], body="")
            case _:
                response = make_response(status=404, message="Not Found", headers=[], body="")

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
    return Request(method=method.decode(), path=path.decode(), version=version.decode(), headers=headers,
                   body=body.decode())


@click.command
@click.option("--directory", )
def start_server(directory):
    App.directory = Path(directory) if directory else Path.cwd()
    asyncio.run(main())


if __name__ == "__main__":
    start_server()
