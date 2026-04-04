# Bloombound

## Game Design Document

Version: 0.1  
Platform: PC  
Engine/Framework: Python + pygame  
Genre: Multiplayer co-op action exploration  
Target Player Count: 2-4 players for MVP, expandable to 6 later  
Camera: Top-down 2D  
Theme: Spring restoration, revival, hidden discoveries

## 1. High Concept

`Bloombound` is a top-down multiplayer co-op game set in a faded spring world that has lost its color and life. Players explore ruined gardens, festival grounds, and wild overgrowth while searching for hidden eggs, restoring dead zones, and reviving fallen teammates. The game uses resurrection as a core gameplay system rather than a story belief system. It is Easter-adjacent through spring imagery, eggs, color, rebirth, and discovery, without being religious.

The player fantasy is simple: work together, uncover secrets, survive hazards, and bring the world back to life.

## 2. Design Goals

The game should:

- Feel distinctly spring-themed without relying on religion.
- Use resurrection as a mechanical pillar, not just a respawn screen.
- Keep downed players active through a spirit form.
- Reward exploration through hidden eggs and optional secrets.
- Be realistic to prototype in pygame with small-team architecture.
- Support co-op teamwork more than competition.

## 3. Core Pillars

### 3.1 Revival Changes the Match

When a player falls, they should not simply disappear and wait. They enter a spirit state that lets them keep contributing until teammates bring them back.

### 3.2 Exploration is Rewarded

Eggs should be hidden in playful, readable ways. Searching the map should feel meaningful, not random.

### 3.3 The World Responds

Restoration should be visible. Gray, dormant spaces become colorful, active, and newly accessible as players progress.

### 3.4 Co-op Creates Better Outcomes

Players should be more effective when coordinating roles, covering space, and planning revivals together.

## 4. Target Experience

Players enter a withered spring location, split up just enough to search efficiently, then regroup when enemies, hazards, or puzzles force teamwork. As eggs and energy are collected, new routes open and dead parts of the map bloom back to life. If someone is downed, they become a wisp that can still scout and help. Tension comes from deciding whether to keep searching, attempt a risky revival, or secure a safe zone first.

The tone should be hopeful, colorful, slightly mysterious, and playful rather than comedic or dark.

## 5. Audience

- Players who enjoy co-op exploration and collection
- Players who like hidden-object hunts and map secrets
- Small friend groups looking for a short multiplayer game session
- Casual to mid-core players

## 6. Game Structure

The recommended structure is mission-based rather than open world.

Each match takes place on one self-contained map with:

- several restoration zones
- a pool of hidden eggs
- light enemy pressure
- a final restoration objective

A single run should last about 15-25 minutes for the MVP.

## 7. Core Gameplay Loop

1. Spawn into a faded level.
2. Explore to find eggs, seeds, and revival energy.
3. Avoid or manage enemies and environmental hazards.
4. Spend collected resources to restore map zones.
5. Unlock new paths, egg spawns, and support stations.
6. Revive downed teammates when needed.
7. Restore the final zone to complete the mission.

This loop should keep alternating between exploration, danger, recovery, and visible progress.

## 8. Core Mechanics

### 8.1 Movement and Interaction

Players move freely in a top-down space using keyboard controls. Core actions:

- move
- interact
- carry or deposit resources
- use class ability
- ping or emote

Movement should be readable and responsive, with slightly different feel by role if desired later.

### 8.2 Egg Hunt System

Eggs are the main collectible and should be used for both progression and excitement.

Egg types:

- Common Eggs: used for score or basic progression
- Revival Eggs: spent to bring back teammates at shrines
- Mystery Eggs: grant temporary buffs or random support effects
- Golden Eggs: rare hidden collectibles for bonus rewards or cosmetics

Egg hiding methods:

- visible but tucked into corners or foliage
- hidden behind breakable or movable objects
- revealed only after restoring part of the map
- visible only to spirit players
- earned from simple co-op puzzle interactions
- placed along risky routes guarded by hazards

The player should feel clever when finding eggs, not lucky.

### 8.3 Restoration System

Restoration is the game's world-level resurrection mechanic. Players return life to specific zones by activating shrines, planting seeds, powering spring devices, or depositing eggs.

Restoring a zone can:

- change the art from gray to colorful
- activate flowers, windmills, bridges, or creatures
- unlock paths or shortcuts
- disable some hazards
- reveal new eggs
- enable revival stations

The visual shift is important. Restoration should feel immediate and rewarding.

### 8.4 Downed and Spirit States

When a player's health reaches zero, they do not fully die. Instead:

- their body collapses or fades
- they become a spirit/wisp
- they lose direct combat power
- they can still move through limited areas or float faster

Spirit abilities for MVP:

- scout the map
- ping hidden eggs
- reveal invisible paths or clues
- briefly distract enemies

Spirit constraints:

- cannot collect normal eggs
- cannot complete core objectives alone
- cannot remain active forever if a timer is used

This prevents dead time and keeps all players engaged.

### 8.5 Revival System

Players in spirit state can return to physical form through team action.

Possible revival rules:

- carry a revival seed to a shrine
- spend a required number of Revival Eggs
- hold the interact button at a shrine for several seconds
- defend the shrine during a short bloom channel

Recommended MVP rule:

Each downed player leaves behind a dormant bloom. Teammates must bring one Revival Egg to the nearest shrine and channel for 3-5 seconds while the spirit remains within range. If successful, the player respawns with partial health.

This creates tension without being too complex to implement.

### 8.6 Hazards and Enemies

The game needs pressure, but not heavy combat complexity in the first version.

Enemy ideas:

- Bramble Wisps: small fast enemies that chase isolated players
- Thorn Hoppers: leap toward players and guard egg routes
- Mold Crawlers: slow area-denial enemies near dead zones

Hazard ideas:

- thorn patches
- collapsing bridges
- mud that slows movement
- gust vents that push players
- darkness fog that obscures eggs until a zone is restored

For the MVP, use one enemy type and one or two hazards only.

### 8.7 Roles or Classes

Roles should be light-touch. Avoid deep RPG systems at first.

Recommended starter roles:

- Scout: moves faster and detects nearby hidden eggs
- Gardener: restores zones and revives teammates faster
- Keeper: can shield teammates or stun enemies briefly
- Spirit-Touched: weaker in body form but stronger in spirit form

For MVP, two roles is enough:

- Scout
- Gardener

### 8.8 Puzzle and Co-op Interactions

Co-op moments help the game feel multiplayer-first.

Simple interactions:

- two players stand on pressure plates
- one player carries a seed while another defends
- a spirit reveals symbols that living players must activate
- one player powers a gate while another crosses

Puzzles should be short and readable. Avoid anything that stalls the session.

## 9. Win and Loss Conditions

### Win Condition

Restore the final heart of the map after enough zones are revived and required eggs are collected.

### Loss Condition Options

Recommended MVP loss condition:

- all players are simultaneously in spirit state
- and no active shrine revival is available

Alternative softer loss:

- mission timer expires before the map heart is restored

The softer timer can be added later if needed.

## 10. Progression Model

### Match Progression

Progress inside a single run comes from:

- eggs collected
- zones restored
- paths unlocked
- players revived
- final heart activated

### Meta Progression

Optional for post-MVP:

- cosmetics unlocked by Golden Eggs
- new map variants
- alternate role perks
- seasonal modifiers

Do not build meta progression in the first prototype unless the core loop is already fun.

## 11. Setting and Narrative Frame

The story should stay light.

Suggested premise:

Every spring, the Bloom Festival renews the land. This year the Heart Garden has gone dormant, the grounds have withered, and the hidden festival eggs have scattered across the region. A group of caretakers enters the ruined grounds to restore the bloom cycle before the season fades completely.

This keeps the resurrection theme focused on:

- the world returning to life
- teammates being revived
- dormant spaces awakening

There is no need for explicit lore beyond that in the MVP.

## 12. Art Direction

### Visual Style

- stylized 2D top-down
- clear silhouettes
- soft spring palette contrasted against gray dead zones
- bold transitions when restoration occurs

### Color Language

- dead areas: desaturated gray, dusty green, brown
- active areas: mint, yellow, coral, sky blue, pink
- spirit state: pale cyan or glowing white
- hazards: dark green, thorn red, muddy purple-brown

### Animation Priorities

- bloom burst on restoration
- egg sparkle or subtle shimmer
- spirit float effect
- shrine activation pulse
- enemy hit flashes

### UI Style

- simple readable icons
- spring motifs like petals, leaves, ribbon shapes
- avoid clutter

## 13. Audio Direction

### Music

- gentle spring ambience
- light magical co-op tension
- brighter layers added as zones are restored

### SFX

- egg pickup chime
- blossom burst on restoration
- soft ghostly sounds for spirit movement
- satisfying revival pulse
- thorn or root impact sounds for hazards

Even placeholder sounds will help the prototype feel more alive.

## 14. Controls

Suggested keyboard controls for local testing:

- `WASD`: move
- `E`: interact
- `Space`: role ability
- `Q`: ping
- `Tab`: scoreboard or objective panel
- `Esc`: pause

For networked multiplayer, each client controls a single player.

## 15. Camera and Readability

Use a shared top-down presentation with a camera centered on the local player on each client. The host should simulate authoritative game state, and clients should render their local view from replicated positions.

Readability goals:

- eggs visible at short range
- shrines identifiable instantly
- downed vs spirit states distinguishable immediately
- restored vs unrestored zones easy to compare

## 16. Technical Design for pygame

### 16.1 Recommended Multiplayer Model

Use a host-client model.

- one player hosts the match
- the host runs authoritative game logic
- clients send input events
- host validates egg collection, enemy movement, health, revivals, and objective state
- host broadcasts state snapshots at a fixed rate

Do not start with peer-to-peer shared authority. It adds unnecessary complexity.

### 16.2 Main Systems

Recommended systems for code structure:

- `Game`: main loop, state transitions, timing
- `NetworkManager`: sockets, message encoding, connection state
- `GameState`: authoritative world state
- `Player`: movement, state, role, health
- `SpiritPlayerState`: flags and spirit-only behavior
- `Enemy`: AI and collision
- `Egg`: type, position, collected state
- `Shrine`: revival and restoration interactions
- `Zone`: restoration progress and art state
- `MapLoader`: level layout and object placement
- `UIManager`: HUD, prompts, timer, objectives

### 16.3 State Model

Each player should track:

- id
- name
- role
- position
- velocity
- health
- status: alive, downed, spirit, reviving
- carried resource
- current animation/state flags

Each match should track:

- level id
- zone restoration states
- egg states
- shrine states
- enemy states
- connected players
- match outcome
- elapsed time

### 16.4 Networking Scope for MVP

Network only what the game truly needs:

- player input
- player transform/state
- enemy transform/state
- egg collected status
- shrine activation/revival events
- zone restored events
- match start/end state

Avoid synchronizing unnecessary visual effects. Let clients spawn local particles based on replicated events.

### 16.5 Data Formats

For pygame and Python, a simple approach is acceptable:

- JSON messages for early prototyping
- later optimize to compact event packets only if performance becomes an issue

Suggested message categories:

- connect
- lobby_state
- input
- state_snapshot
- interact
- collect_egg
- start_revival
- complete_revival
- restore_zone
- match_result

### 16.6 Performance Constraints

The MVP should keep scope modest:

- one medium-sized map
- low enemy count
- simple pathfinding or direct chase behavior
- no heavy physics
- tile-based or rectangle-based collisions

This is appropriate for pygame and simpler to debug over a network.

## 17. Map Design

### MVP Map: Heart Garden

A good first map is a ruined spring festival garden with three restoration zones and one final heart chamber.

Suggested layout:

- central safe hub with first shrine
- left hedge maze with hidden eggs
- upper greenhouse with a co-op gate puzzle
- lower pond path with slowing mud hazard
- final central heart tree unlocked after all zones recover

### Map Flow

- the first minutes teach searching and depositing
- the midgame creates branching choices
- the late game pulls players back together for final restoration

The map should loop back on itself with shortcuts after restoration.

## 18. Content List for MVP

Build only this first:

- 1 playable map
- 2 player roles
- 3 egg types
- 1 enemy type
- 2 hazard types
- 2-4 player networking
- spirit mode
- shrine revival
- 3 restoration zones
- 1 final win objective
- basic menu and lobby

Anything beyond this is a stretch goal.

## 19. Stretch Goals

After the MVP works, possible additions:

- competitive team race mode
- procedural egg placement rules
- more enemy types
- more maps
- boss encounter guarding the final heart
- cosmetic unlocks from Golden Eggs
- dynamic weather
- spirit-only secret routes

## 20. Balancing Principles

Use these rules to keep the game fair:

- revivals should be risky but not rare
- exploration should be rewarded but not mandatory in every corner
- no player should sit inactive after being downed
- enemy pressure should punish isolation, not constant movement
- the map should offer multiple viable routes, not one correct path

If matches feel too punishing, reduce enemy aggression before reducing exploration depth.

## 21. Risks and Mitigations

### Risk: Multiplayer complexity in pygame

Mitigation:

- keep the host authoritative
- use simple snapshots
- minimize synchronized systems

### Risk: Hidden eggs feel unfair

Mitigation:

- use consistent visual language
- add sparkle or clue props nearby
- let Scout and spirit players reveal hints

### Risk: Revivals feel annoying

Mitigation:

- keep revival costs low in early areas
- place shrines logically
- avoid long revive timers

### Risk: Prototype scope grows too fast

Mitigation:

- cut extra roles first
- cut narrative scenes
- keep one map until the loop is proven

## 22. Prototype Roadmap

### Milestone 1: Movement and Map

- create tile or rect-based map
- implement player movement and collisions
- render eggs and shrines
- basic camera and HUD

### Milestone 2: Collection and Restoration

- collect eggs
- deposit at shrines
- track zone restoration
- update map visuals when restored

### Milestone 3: Health and Spirit Mode

- implement enemy contact damage
- transition to downed and spirit states
- allow scouting and pinging in spirit mode

### Milestone 4: Revival and Victory

- shrine revival channel
- re-materialize player
- activate final heart objective
- win and loss conditions

### Milestone 5: Networking

- host/client connection
- player input replication
- authoritative snapshots
- synced egg collection and revivals

Networking can be started earlier, but this order is safer for debugging.

## 23. Playtest Questions

Use these questions during testing:

- Do players understand the goal quickly?
- Are eggs fun to search for?
- Does spirit mode feel active enough?
- Are revivals too easy or too punishing?
- Do restored zones feel satisfying?
- Is the map readable in motion?
- Does co-op feel useful rather than optional?

## 24. Success Criteria for MVP

The prototype is successful if:

- a group can complete a full match without explanation after a brief intro
- downed players stay engaged in spirit form
- restoration visibly changes the map
- egg hunting feels rewarding
- multiplayer state remains stable for a short session

## 25. Recommended Next Step

After this document, the best next step is to define a thin vertical slice:

- one room cluster
- one shrine
- one restoration zone
- one enemy
- one downed player flow

If that slice is fun, expand into the full Heart Garden map.
