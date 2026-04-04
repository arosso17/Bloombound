import json
import socket
from typing import Callable


BUFFER_SIZE = 65536
PROTOCOL_VERSION = 1


def encode_message(message: dict) -> bytes:
    payload = dict(message)
    payload.setdefault("version", PROTOCOL_VERSION)
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


def send_message(sock: socket.socket, message: dict) -> None:
    sock.sendall(encode_message(message))


def read_messages_forever(
    sock: socket.socket,
    should_stop: Callable[[], bool],
    on_message: Callable[[dict], None],
    on_disconnect: Callable[[], None],
) -> None:
    buffer = ""
    try:
        while not should_stop():
            data = sock.recv(BUFFER_SIZE)
            if not data:
                break
            buffer += data.decode("utf-8")
            while "\n" in buffer:
                raw_line, buffer = buffer.split("\n", 1)
                if not raw_line.strip():
                    continue
                try:
                    on_message(json.loads(raw_line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    finally:
        on_disconnect()


def safe_close(sock: socket.socket | None) -> None:
    if sock is None:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass

