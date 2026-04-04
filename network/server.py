from __future__ import annotations

import queue
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field

from gameplay.state import GameState
from network.shared import read_messages_forever, safe_close, send_message


@dataclass
class ClientSession:
    player_id: str
    sock: socket.socket
    address: tuple[str, int]
    name: str
    send_lock: threading.Lock = field(default_factory=threading.Lock)


class GameServer:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5050,
        tick_rate: int = 20,
        expected_players: int = 2,
    ) -> None:
        self.host = host
        self.port = port
        self.tick_rate = tick_rate
        self.state = GameState(expected_players=expected_players)
        self.stop_event = threading.Event()
        self.server_socket: socket.socket | None = None
        self.accept_thread: threading.Thread | None = None
        self.loop_thread: threading.Thread | None = None
        self.message_queue: queue.Queue[tuple[str, dict]] = queue.Queue()
        self.disconnect_queue: queue.Queue[str] = queue.Queue()
        self.sessions: dict[str, ClientSession] = {}
        self.sessions_lock = threading.Lock()

    def start(self) -> None:
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        self.server_socket.settimeout(0.5)
        self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.accept_thread.start()
        self.loop_thread.start()

    def run_forever(self) -> None:
        self.start()
        print(f"Server listening on {self.host}:{self.port}")
        try:
            while not self.stop_event.is_set():
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        safe_close(self.server_socket)
        with self.sessions_lock:
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for session in sessions:
            safe_close(session.sock)
        if self.accept_thread:
            self.accept_thread.join(timeout=1.0)
        if self.loop_thread:
            self.loop_thread.join(timeout=1.0)

    def _accept_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                assert self.server_socket is not None
                client_sock, address = self.server_socket.accept()
            except (socket.timeout, OSError):
                continue

            client_sock.settimeout(None)
            player_id = uuid.uuid4().hex[:8]
            default_name = f"Player-{len(self.sessions) + 1}"
            self.state.add_player(player_id, default_name)
            session = ClientSession(player_id=player_id, sock=client_sock, address=address, name=default_name)
            with self.sessions_lock:
                self.sessions[player_id] = session

            self._send_to_session(
                session,
                {
                    "type": "welcome",
                    "player_id": player_id,
                    "tick_rate": self.tick_rate,
                    "match_phase": self.state.match_phase,
                    "world": self.state.build_snapshot()["world"],
                },
            )

            threading.Thread(
                target=self._client_reader,
                args=(session,),
                daemon=True,
            ).start()

    def _client_reader(self, session: ClientSession) -> None:
        read_messages_forever(
            session.sock,
            should_stop=self.stop_event.is_set,
            on_message=lambda message: self.message_queue.put((session.player_id, message)),
            on_disconnect=lambda: self.disconnect_queue.put(session.player_id),
        )

    def _run_loop(self) -> None:
        tick_duration = 1.0 / self.tick_rate
        while not self.stop_event.is_set():
            start = time.perf_counter()
            self._drain_disconnects()
            self._drain_messages()
            if self.state.match_phase == "playing":
                self.state.update(tick_duration)
                self._broadcast(self.state.build_snapshot())
            else:
                self._broadcast(self.state.build_lobby_state())
            elapsed = time.perf_counter() - start
            time.sleep(max(0.0, tick_duration - elapsed))

    def _drain_disconnects(self) -> None:
        while True:
            try:
                player_id = self.disconnect_queue.get_nowait()
            except queue.Empty:
                break
            with self.sessions_lock:
                session = self.sessions.pop(player_id, None)
            if session:
                safe_close(session.sock)
            self.state.remove_player(player_id)

    def _drain_messages(self) -> None:
        while True:
            try:
                player_id, message = self.message_queue.get_nowait()
            except queue.Empty:
                break
            if message.get("type") == "join":
                requested_name = str(message.get("name", "")).strip()
                self.state.rename_player(player_id, requested_name)
            elif message.get("type") == "set_profile":
                requested_name = str(message.get("name", "")).strip()
                if requested_name:
                    self.state.rename_player(player_id, requested_name)
                if "color_index" in message:
                    self.state.set_color(player_id, int(message["color_index"]))
            elif message.get("type") == "player_input":
                self.state.apply_input(player_id, message)
            elif message.get("type") == "start_game":
                if self.state.start_match(player_id):
                    self._broadcast(self.state.build_lobby_state())

    def _broadcast(self, message: dict) -> None:
        with self.sessions_lock:
            sessions = list(self.sessions.values())
        stale_ids = []
        for session in sessions:
            if not self._send_to_session(session, message):
                stale_ids.append(session.player_id)
        for player_id in stale_ids:
            self.disconnect_queue.put(player_id)

    def _send_to_session(self, session: ClientSession, message: dict) -> bool:
        try:
            with session.send_lock:
                send_message(session.sock, message)
            return True
        except OSError:
            return False
