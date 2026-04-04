# Bloombound

Bloombound is a small Python networking prototype for a co-op game loop built around a server-authoritative model. It includes a TCP game server, a `pygame` client, and shared gameplay state for a simple "collect and revive" objective.

## Current prototype

- Authoritative Python socket server
- `pygame` client with a lobby and in-match view
- Local host mode for running server and client together
- Basic co-op loop: collect a revival egg, bring it to the shrine, revive a downed player

## Project layout

- `easter.py` - command-line entrypoint for server, client, and host modes
- `gameplay/` - gameplay entities and world state updates
- `network/` - TCP transport, server loop, and client networking
- `easter_design_document.md` - design notes for the prototype

## Requirements

- Python 3.10+
- `pygame`

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Running the prototype

Host a local session:

```powershell
python easter.py host --name Host
```

Run a dedicated server:

```powershell
python easter.py server --host 0.0.0.0 --port 5050 --expected-players 2
```

Connect a client:

```powershell
python easter.py client --host 127.0.0.1 --port 5050 --name Player
```

## Visual Asset Editor

Shape-based visuals live in `assets/visuals/` as JSON files and can be edited with the GUI tool:

```powershell
python tools/visual_asset_editor.py
```

The editor saves the same format the game loads at runtime, so authored visuals can be used directly by the client renderer.

## Map Editor

Maps live in `gameplay/maps/` as JSON files and can be edited with the dedicated map tool:

```powershell
python tools/map_editor.py
```

The map editor reads and writes the same schema the server loads at runtime, including collision rectangles, player spawns, egg spawns, shrine placement, enemy spawns, and the final bloom.

## Controls

- `WASD` move
- `E` interact at the shrine
- `Left` / `Right` change player color in the lobby
- `Backspace` edit the lobby name
- `Enter` start the match as host when enough players are connected
- `K` force the local player into spirit form for testing

## GitHub setup

After creating an empty GitHub repository, connect this local folder and push:

```powershell
git remote add origin https://github.com/<your-user>/<repo-name>.git
git add .
git commit -m "Initial commit"
git push -u origin main
```
