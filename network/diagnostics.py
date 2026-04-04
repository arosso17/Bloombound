from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field


def _average(total: float, samples: int) -> float:
    if samples <= 0:
        return 0.0
    return total / samples


def _counter_summary(counter: Counter[str], limit: int = 3) -> str:
    if not counter:
        return "-"
    parts = []
    for key, value in counter.most_common(limit):
        parts.append(f"{key}:{value}")
    return ",".join(parts)


@dataclass
class ServerDiagnostics:
    enabled: bool = False
    interval_seconds: float = 1.0
    last_report_at: float = field(default_factory=time.perf_counter)
    tick_count: int = 0
    tick_total_seconds: float = 0.0
    tick_max_seconds: float = 0.0
    inbound_counts: Counter[str] = field(default_factory=Counter)
    outbound_counts: Counter[str] = field(default_factory=Counter)
    queue_delay_total_seconds: float = 0.0
    queue_delay_max_seconds: float = 0.0
    queue_delay_samples: int = 0
    outbound_bytes_total: int = 0
    outbound_bytes_max: int = 0
    recipients_total: int = 0
    recipients_max: int = 0
    peak_message_queue_size: int = 0
    peak_disconnect_queue_size: int = 0
    session_count: int = 0
    match_phase: str = "lobby"

    def record_tick(
        self,
        elapsed_seconds: float,
        session_count: int,
        match_phase: str,
        message_queue_size: int,
        disconnect_queue_size: int,
    ) -> None:
        if not self.enabled:
            return
        self.tick_count += 1
        self.tick_total_seconds += elapsed_seconds
        self.tick_max_seconds = max(self.tick_max_seconds, elapsed_seconds)
        self.session_count = session_count
        self.match_phase = match_phase
        self.peak_message_queue_size = max(self.peak_message_queue_size, message_queue_size)
        self.peak_disconnect_queue_size = max(self.peak_disconnect_queue_size, disconnect_queue_size)

    def record_message(self, message_type: str, queue_delay_seconds: float) -> None:
        if not self.enabled:
            return
        self.inbound_counts[message_type] += 1
        self.queue_delay_total_seconds += queue_delay_seconds
        self.queue_delay_max_seconds = max(self.queue_delay_max_seconds, queue_delay_seconds)
        self.queue_delay_samples += 1

    def record_broadcast(self, message_type: str, payload_size: int, recipient_count: int) -> None:
        if not self.enabled:
            return
        self.outbound_counts[message_type] += 1
        self.outbound_bytes_total += payload_size
        self.outbound_bytes_max = max(self.outbound_bytes_max, payload_size)
        self.recipients_total += recipient_count
        self.recipients_max = max(self.recipients_max, recipient_count)

    def maybe_emit(self) -> None:
        if not self.enabled:
            return
        now = time.perf_counter()
        elapsed = now - self.last_report_at
        if elapsed < self.interval_seconds:
            return

        avg_tick_ms = _average(self.tick_total_seconds, self.tick_count) * 1000.0
        max_tick_ms = self.tick_max_seconds * 1000.0
        avg_queue_ms = _average(self.queue_delay_total_seconds, self.queue_delay_samples) * 1000.0
        max_queue_ms = self.queue_delay_max_seconds * 1000.0
        avg_payload_bytes = int(round(_average(float(self.outbound_bytes_total), sum(self.outbound_counts.values()))))
        avg_recipients = _average(float(self.recipients_total), sum(self.outbound_counts.values()))
        print(
            "[net][server] "
            f"phase={self.match_phase} sessions={self.session_count} "
            f"ticks={self.tick_count / elapsed:.1f}/s avg_tick={avg_tick_ms:.2f}ms max_tick={max_tick_ms:.2f}ms "
            f"in={sum(self.inbound_counts.values()) / elapsed:.1f}/s[{_counter_summary(self.inbound_counts)}] "
            f"queue={avg_queue_ms:.2f}/{max_queue_ms:.2f}ms "
            f"out={sum(self.outbound_counts.values()) / elapsed:.1f}/s[{_counter_summary(self.outbound_counts)}] "
            f"payload={avg_payload_bytes}B/{self.outbound_bytes_max}B "
            f"rcpts={avg_recipients:.1f}/{self.recipients_max:.0f} "
            f"peak_q={self.peak_message_queue_size}/{self.peak_disconnect_queue_size}",
            flush=True,
        )
        self.last_report_at = now
        self.tick_count = 0
        self.tick_total_seconds = 0.0
        self.tick_max_seconds = 0.0
        self.inbound_counts.clear()
        self.outbound_counts.clear()
        self.queue_delay_total_seconds = 0.0
        self.queue_delay_max_seconds = 0.0
        self.queue_delay_samples = 0
        self.outbound_bytes_total = 0
        self.outbound_bytes_max = 0
        self.recipients_total = 0
        self.recipients_max = 0
        self.peak_message_queue_size = 0
        self.peak_disconnect_queue_size = 0


@dataclass
class ClientDiagnostics:
    enabled: bool = False
    interval_seconds: float = 1.0
    last_report_at: float = field(default_factory=time.perf_counter)
    frame_count: int = 0
    frame_total_seconds: float = 0.0
    frame_max_seconds: float = 0.0
    incoming_counts: Counter[str] = field(default_factory=Counter)
    input_messages_sent: int = 0
    snapshot_count: int = 0
    last_snapshot_at: float | None = None
    snapshot_interval_total_seconds: float = 0.0
    snapshot_interval_max_seconds: float = 0.0
    snapshot_interval_samples: int = 0
    last_snapshot_tick: int | None = None
    snapshot_tick_delta_total: int = 0
    snapshot_tick_delta_max: int = 0
    snapshot_tick_delta_samples: int = 0
    rtt_total_seconds: float = 0.0
    rtt_max_seconds: float = 0.0
    rtt_samples: int = 0
    server_turnaround_total_seconds: float = 0.0
    server_turnaround_max_seconds: float = 0.0
    server_turnaround_samples: int = 0
    local_error_total: float = 0.0
    local_error_max: float = 0.0
    local_error_samples: int = 0
    remote_player_error_total: float = 0.0
    remote_player_error_max: float = 0.0
    remote_player_error_samples: int = 0
    enemy_error_total: float = 0.0
    enemy_error_max: float = 0.0
    enemy_error_samples: int = 0

    def record_frame(self, delta_seconds: float) -> None:
        if not self.enabled:
            return
        self.frame_count += 1
        self.frame_total_seconds += delta_seconds
        self.frame_max_seconds = max(self.frame_max_seconds, delta_seconds)

    def record_message(self, message_type: str) -> None:
        if not self.enabled:
            return
        self.incoming_counts[message_type] += 1

    def record_input_sent(self) -> None:
        if not self.enabled:
            return
        self.input_messages_sent += 1

    def record_world_snapshot(self, tick: int) -> None:
        if not self.enabled:
            return
        now = time.perf_counter()
        self.snapshot_count += 1
        if self.last_snapshot_at is not None:
            delta_seconds = now - self.last_snapshot_at
            self.snapshot_interval_total_seconds += delta_seconds
            self.snapshot_interval_max_seconds = max(self.snapshot_interval_max_seconds, delta_seconds)
            self.snapshot_interval_samples += 1
        if self.last_snapshot_tick is not None:
            tick_delta = max(0, tick - self.last_snapshot_tick)
            self.snapshot_tick_delta_total += tick_delta
            self.snapshot_tick_delta_max = max(self.snapshot_tick_delta_max, tick_delta)
            self.snapshot_tick_delta_samples += 1
        self.last_snapshot_at = now
        self.last_snapshot_tick = tick

    def record_rtt(self, round_trip_seconds: float, server_turnaround_seconds: float | None) -> None:
        if not self.enabled:
            return
        self.rtt_total_seconds += round_trip_seconds
        self.rtt_max_seconds = max(self.rtt_max_seconds, round_trip_seconds)
        self.rtt_samples += 1
        if server_turnaround_seconds is None:
            return
        self.server_turnaround_total_seconds += server_turnaround_seconds
        self.server_turnaround_max_seconds = max(self.server_turnaround_max_seconds, server_turnaround_seconds)
        self.server_turnaround_samples += 1

    def record_local_error(self, error_distance: float) -> None:
        if not self.enabled:
            return
        self.local_error_total += error_distance
        self.local_error_max = max(self.local_error_max, error_distance)
        self.local_error_samples += 1

    def record_remote_player_error(self, error_distance: float) -> None:
        if not self.enabled:
            return
        self.remote_player_error_total += error_distance
        self.remote_player_error_max = max(self.remote_player_error_max, error_distance)
        self.remote_player_error_samples += 1

    def record_enemy_error(self, error_distance: float) -> None:
        if not self.enabled:
            return
        self.enemy_error_total += error_distance
        self.enemy_error_max = max(self.enemy_error_max, error_distance)
        self.enemy_error_samples += 1

    def maybe_emit(self) -> None:
        if not self.enabled:
            return
        now = time.perf_counter()
        elapsed = now - self.last_report_at
        if elapsed < self.interval_seconds:
            return

        fps = self.frame_count / elapsed
        avg_frame_ms = _average(self.frame_total_seconds, self.frame_count) * 1000.0
        max_frame_ms = self.frame_max_seconds * 1000.0
        snapshot_rate = self.snapshot_count / elapsed
        avg_snapshot_gap_ms = _average(self.snapshot_interval_total_seconds, self.snapshot_interval_samples) * 1000.0
        max_snapshot_gap_ms = self.snapshot_interval_max_seconds * 1000.0
        since_snapshot_ms = 0.0
        if self.last_snapshot_at is not None:
            since_snapshot_ms = (now - self.last_snapshot_at) * 1000.0
        avg_tick_delta = _average(float(self.snapshot_tick_delta_total), self.snapshot_tick_delta_samples)
        avg_rtt_ms = _average(self.rtt_total_seconds, self.rtt_samples) * 1000.0
        max_rtt_ms = self.rtt_max_seconds * 1000.0
        avg_server_turn_ms = _average(self.server_turnaround_total_seconds, self.server_turnaround_samples) * 1000.0
        avg_local_error = _average(self.local_error_total, self.local_error_samples)
        avg_remote_player_error = _average(self.remote_player_error_total, self.remote_player_error_samples)
        avg_enemy_error = _average(self.enemy_error_total, self.enemy_error_samples)

        print(
            "[net][client] "
            f"fps={fps:.1f} avg_frame={avg_frame_ms:.2f}ms max_frame={max_frame_ms:.2f}ms "
            f"snapshots={snapshot_rate:.1f}/s gap={avg_snapshot_gap_ms:.2f}/{max_snapshot_gap_ms:.2f}ms "
            f"snap_age={since_snapshot_ms:.2f}ms tick_delta={avg_tick_delta:.2f} "
            f"rtt={avg_rtt_ms:.2f}/{max_rtt_ms:.2f}ms server_turn={avg_server_turn_ms:.2f}ms "
            f"local_err={avg_local_error:.2f}/{self.local_error_max:.2f} "
            f"remote_err={avg_remote_player_error:.2f}/{self.remote_player_error_max:.2f} "
            f"enemy_err={avg_enemy_error:.2f}/{self.enemy_error_max:.2f} "
            f"inputs={self.input_messages_sent / elapsed:.1f}/s in[{_counter_summary(self.incoming_counts)}]",
            flush=True,
        )
        self.last_report_at = now
        self.frame_count = 0
        self.frame_total_seconds = 0.0
        self.frame_max_seconds = 0.0
        self.incoming_counts.clear()
        self.input_messages_sent = 0
        self.snapshot_count = 0
        self.snapshot_interval_total_seconds = 0.0
        self.snapshot_interval_max_seconds = 0.0
        self.snapshot_interval_samples = 0
        self.snapshot_tick_delta_total = 0
        self.snapshot_tick_delta_max = 0
        self.snapshot_tick_delta_samples = 0
        self.rtt_total_seconds = 0.0
        self.rtt_max_seconds = 0.0
        self.rtt_samples = 0
        self.server_turnaround_total_seconds = 0.0
        self.server_turnaround_max_seconds = 0.0
        self.server_turnaround_samples = 0
        self.local_error_total = 0.0
        self.local_error_max = 0.0
        self.local_error_samples = 0
        self.remote_player_error_total = 0.0
        self.remote_player_error_max = 0.0
        self.remote_player_error_samples = 0
        self.enemy_error_total = 0.0
        self.enemy_error_max = 0.0
        self.enemy_error_samples = 0
