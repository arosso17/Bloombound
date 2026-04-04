import argparse
import time

from network.client import run_client
from network.server import GameServer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bloombound networking prototype")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    server_parser = subparsers.add_parser("server", help="Run the authoritative game server")
    server_parser.add_argument("--host", default="0.0.0.0")
    server_parser.add_argument("--port", type=int, default=5050)
    server_parser.add_argument("--tick-rate", type=int, default=20)
    server_parser.add_argument("--expected-players", type=int, default=2)
    server_parser.add_argument("--map-id", default="heart_garden")

    client_parser = subparsers.add_parser("client", help="Run a pygame client")
    client_parser.add_argument("--host", default="127.0.0.1")
    client_parser.add_argument("--port", type=int, default=5050)
    client_parser.add_argument("--name", default="Player")

    host_parser = subparsers.add_parser("host", help="Run a local server and client together")
    host_parser.add_argument("--port", type=int, default=5050)
    host_parser.add_argument("--tick-rate", type=int, default=20)
    host_parser.add_argument("--expected-players", type=int, default=2)
    host_parser.add_argument("--name", default="Host")
    host_parser.add_argument("--map-id", default="heart_garden")

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.mode == "server":
        GameServer(
            host=args.host,
            port=args.port,
            tick_rate=args.tick_rate,
            expected_players=args.expected_players,
            map_id=args.map_id,
        ).run_forever()
        return

    if args.mode == "client":
        run_client(args.host, args.port, args.name)
        return

    if args.mode == "host":
        server = GameServer(
            host="0.0.0.0",
            port=args.port,
            tick_rate=args.tick_rate,
            expected_players=args.expected_players,
            map_id=args.map_id,
        )
        server.start()
        print(f"Hosting on 127.0.0.1:{args.port}")
        try:
            time.sleep(0.2)
            run_client("127.0.0.1", args.port, args.name)
        finally:
            server.stop()


if __name__ == "__main__":
    main()
