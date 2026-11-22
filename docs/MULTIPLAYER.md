# Local-host multiplayer research

Private History Edition tests ran direct LAN and Internet matches between a
Windows host and a Hyper-V guest, including New Earth with optional World
Settings. The test history below records the tested configurations and open
issues.

The public source includes the multiplayer research and a runnable preflight.
Building the in-game candidate requires local licensed game inputs and private
build and staging helpers. Multiplayer support in the public installer is
pending. See the [roadmap](ROADMAP.md#priority-research-local-host-multiplayer).

## Run the preflight

From the source checkout in PowerShell, set `PYTHONPATH` to `src`. Each player
chooses an independent stock History Edition game folder. Close the game
before checking its files.

```powershell
$env:PYTHONPATH = 'src'
python -m anno1503_overhaul lan check --game 'C:\Games\Anno1503-Stock'
```

Use the host PC's private LAN IPv4 address in both commands. Each player may
choose a display name with `--name` before connecting.

```powershell
# On the host PC
python -m anno1503_overhaul lan host --game 'C:\Games\Anno1503-Stock' --bind 192.168.1.20 --name 'Harbor Master'

# On the guest PC
python -m anno1503_overhaul lan join 192.168.1.20 --game 'C:\Games\Anno1503-Stock' --name 'Navigator'
```

The commands use TCP port 51503 by default. If the port is already in use, add
the same `--port` to both commands. On one PC, use the loopback address
`127.0.0.1` and pass a distinct `--player-file <path>` before `host` or `join`
in each terminal.

The local display name persists between runs. Use `lan name` to show it or
`lan name "New name"` to change it. A rename preserves the local player ID.
The preflight exchanges only the peer IDs, display names, compatibility
fingerprint and protocol messages. Run it with a known peer on a trusted LAN.

The fingerprint checks the pinned stock executable, engine modules and
building archives, plus selected DLLs and data files. It also compares
the multiplayer scenario files, scene cache and loose island templates.
Both players need the same preflight version. The commands finish after
the exchange.

## Preflight validation

Two Windows console processes used separate local identities and the same
verified stock copy over loopback. They exchanged display names and produced
the same fingerprint. A later rename preserved the guest ID. Automated tests
also exercise mismatched game files, duplicate identities and invalid input.

## Early stock game observations

- On the verified Dutch stock copy, Multiplayer opens a selector with Custom
  and Quick Match. Custom opens the native New Game and Load Game menu. No
  LAN or direct-address control was observed on those screens.
- The stock executable and frame module contain a legacy address parser and
  LAN role-selection code. The transport option defaults to the Ubisoft
  overlay. Static inspection found a raw UDP branch and no stock control
  that selects it. An authenticated launch probe with the legacy host
  switch still reached the ordinary main menu.
- The stock role setup reads the Ubisoft account username. The saved
  preflight display name is used between the two preflight commands.
  Displaying that name in the game requires an engine integration.
- Use two separate licensed History Edition installations for the first native
  test. Select one stock scenario. Verify both players can issue commands,
  the simulation stays synchronized, and a save resumes with the expected
  player ownership. Establish a new session with internet access unavailable
  after normal startup to verify the match is independent of online services.

## Native LAN host test

The 18 November 2026 test used the inspected Dutch History Edition copy and
normal Ubisoft Connect startup. The baseline main menu had no listener on
UDP 61503. For the test, a one-byte change in the copied `AnnoDisplay.dll`
selected the built-in direct UDP mode before the menus were initialized.

Multiplayer → Custom reached the native **Session name** screen. The center
of the screen initially rendered black and the controls became visible after
keyboard input. Confirming the default session name opened UDP 61503 on the
copied game process. A read-only probe confirmed that both the host and its
built-in local client selected direct sockets and linked to each other. The
local client reported a UDP error and the host-ready signal stayed clear.
Both attempts returned to the multiplayer selector and released UDP 61503
before reaching the scenario lobby.

The inspected raw transport branch skips the Ubisoft session-creation call.
The startup screens still update the Ubisoft overlay, and stock multiplayer
scenario selection still checks online-services readiness. Internet access
was available and there was one licensed game instance in the host test.
Service-independent lobby creation, guest join and gameplay remain
unverified.

The copied display DLL was restored to its original SHA-256 after closing
the test process. The stock game preflight returned the same fingerprint as
before the experiment.

## Native LAN loopback retest

Two new runs on the isolated copy used normal Ubisoft Connect startup with
internet access available. A temporary runtime change enabled discovery on
the native host's own UDP client, which was configured to contact
`127.0.0.1:61503`. Both runs opened UDP 61503 for the server and acquired a
new ephemeral UDP port for the client. The host remained on the session name
screen. The client received no discovery reply, its player slot stayed
unassigned, and the scenario lobby did not open.

The History Edition's direct UDP receive loop expects the sender to exist in
the server's peer table before dispatch. The host's own client is still
unknown during discovery. The receive loop has no route to the native
pre-session handler, which replies to discovery and registers players. The
legacy 32-bit engine has a separate route for this stage. History Edition
requires a corresponding implementation using its own packet checks and
queue handling.

The temporary discovery change exited with the test process. The isolated
copy returned to its stock fingerprint after restoring the display DLL.
The test involved one game instance and never reached a match, so Ubisoft
service independence remains unverified.

## Native server discovery adapter

The isolated prototype binds the native UDP listener to loopback and
accepts discovery and join requests only from the game's own host client
socket. It checks the datagram length, native checksum and game identifier
before routing an eligible request to the native pre-session queue. The game
handles discovery replies, player registration and the acceptance response.

The standalone Windows fixture verified the loopback bind and ten packet
framing and checksum cases.

The 18 November 2026 live test used normal Ubisoft Connect startup with
internet available. The listener bound `127.0.0.1:61503`. The adapter
queued one genuine discovery and one join. The game assigned the host
its own player slot, the client and server agreed on the session ID, and
the native **New Game / Load Game** screen opened.

Selecting **New Game** displayed the stock multiplayer scenario list.
Confirming **New Earth** left the game in that selector while the UDP
session continued carrying traffic. The native code checks Ubisoft
online-services readiness, which was true when sampled. Direct mode
skips the Ubisoft session creation call, and the selector has no direct
lobby transition for the five available stock scenarios. The final lobby
did not open during this test.

The adapter and stock DLL backups remain in the isolated test workspace.
Each fresh test process requires the temporary client discovery change.
Only the host's in-process loopback connection was tested. Guest join and
gameplay without Ubisoft services remain unverified.

## New Earth native lobby test

The isolated copy now opens the game's stock multiplayer color-selection
lobby after a confirmed direct UDP scenario selection. The selector checks
the joined local UDP session before opening the lobby. The game still
loads the scenario, owns the player roster and enforces its Start rules.

In the final live run, the host completed discovery and join on
`127.0.0.1:61503`. Confirming **New Earth** made one direct readiness
check, zero online readiness calls at the selector, and one native lobby
transition. Direct mode skipped Ubisoft session creation. The **Mission**
control opened the scenario briefing, and **Back** returned to scenario
selection with the native UDP session still connected.

The direct paint change displays the lobby controls. The previous screen
can remain visible behind them. **Start** stayed disabled with one player
because the stock New Earth scenario requires at least two. The test used
normal Ubisoft Connect startup with internet available. An actual match
and a guest connection from another machine remain unverified.

## Direct LAN guest candidate

The private test build lets the host bind UDP port `61503` to a selected
private IPv4 address and gives the guest that exact destination. Before
staging the build, both players exchange their chosen display names and
verify matching stock game and New Earth files over the TCP preflight.
The two endpoints must be on the same private subnet.

The host completes its own native join before admitting the selected
guest. The adapter accepts discovery and join from the guest's discovered
UDP endpoint and assigns the guest the second player slot. The guest uses
the game's own session list and lobby. Display names from preflight still
need to be wired into the game. Start a fresh host room to try again after
a failed join or a guest disconnect.

The candidate builds separately from the previously tested host-only
copy. A live trial uses two normally licensed game instances in separate
Windows environments.

## New Earth host and VM trial

On 18 November 2026, the Windows host and Hyper-V guest both completed
normal Ubisoft Connect startup and passed the compatibility check. The
guest joined over the private Hyper-V LAN and the host registered both
native player slots. Both players reached the color-selection lobby.

Starting New Earth loaded the game world on both systems. The game
reported a synchronization error on both screens and aborted the match.
The guest also showed the inactive-player free overview at the abort
screen. The host wrote a native desync save. The cause of the divergence
remains undetermined.

Internet access stayed on for this run. A fresh join with WAN unavailable
and a synchronized gameplay run remain unverified.

The paired desync saves agree on island placement, elevation, and
world timers. All 464 island templates match byte for byte. The guest
save is missing the starting ship that the host saved for player 7.
Ground-object state and wildlife records also differ.

The next candidate applies the host's received roster colors to matching
players on the direct-LAN guest before the native lobby refresh. The
compatibility check also binds the trial to identical adapter builds on
both peers. The game still validates synchronization during the match.

### Wi-Fi-on retest

Both peers passed the updated compatibility check, joined the native
lobby, and started New Earth with host Wi-Fi connected. The guest
entered as an active player with a starting ship. The host wrote a
native desync save during the opening seconds, and the guest displayed
the native synchronization error and stopped. The host still advanced
its command sequence after the save, so host progress alone did not
indicate agreement between the two game worlds.


### Paired retest saves and fixes

The paired retest saves contain both human starting ships at the same
coordinates. Their world timers, 41 island layouts, elevations, and
wildlife agree. The host was one growth update ahead on most of the
changed ground records, and several NPC records were further along.
The game writes these error saves after receiving the notification, so
the two files can represent different updates of the same command slot.

The earlier checksum covers the native player name and profile fields.
Player 0 used the host's local profile name on the host and a Windows
computer-name fallback in the VM. The direct LAN launch now supplies the
paired display names to the stock setters for both fields before play.
The private trial uses the role's default LAN label when a display name
cannot be represented as printable ASCII.

The Host/Join selector was black even though both native render surfaces
existed. Its paint handler suppressed both surfaces. The isolated
direct LAN path now lets the stock painter draw the active selector.
The native buttons continue to open their normal Host and Join screens.


### Wi-Fi-on verification after the fixes

On 18 November 2026, the updated host and Hyper-V guest passed
compatibility checks, joined the native lobby, and started New Earth.
Both players submitted matching native checksums at four successive
checkpoints. The guest moved its ship during the match and both games
continued for more than three minutes with host Wi-Fi connected.

The updated host and guest navigated through the Host/Join selector.
The paint change was verified against the pinned selector code and
compiled for the live candidate. The rendered selector has not yet been
observed while it was open on this build.


## Internet launcher candidate

The Internet button on the isolated direct-mode selector opens a
separate Windows launcher. Host starts the compatibility listener and
shows the public IPv4 address to share. Join connects to that address.
The launcher supports one host and one guest. After verifying the
matching game and adapter builds, it starts Anno through the normal
Ubisoft Connect launch path. Choose LAN Host or LAN Join in the
reopened game to enter its native lobby.

The host forwards TCP 51503 and UDP 61503 to the game PC's local IPv4
address. TCP carries the compatibility exchange and UDP carries the
match. The guest enters the host's public IPv4 and uses an outbound
connection. The launcher uses distinct local and public addresses
when the host is behind a router.

The launcher and native callback were built separately from the tested
LAN candidate. The compatibility exchange was exercised over local
sockets and tested with simulated public endpoints. The native image
and staging were verified in disposable fixtures. A New Earth match
across two internet connections remains unverified.



### Public IPv4 VM test

On 21 November 2026, the Hyper-V guest paired with the host through
the router's public IPv4 on TCP 51503. With Wi-Fi connected, the
guest then joined the native NoName room through UDP 61503 and both
copies started New Earth. The host confirmed both native player slots
and four completed checks with matching native checksums. The match
ran for more than three minutes, including a host ship move, with
no sync error reported.

The router looped the public-address connection back to the host
because both copies used the same home internet connection. Testing
a guest on a separate internet connection is still pending. The
Host/Join/Internet selector was visible on the host. The color-selection
lobby still drew some controls over the previous scenario screen.


## Custom-map compatibility trial

The first custom-map trial uses an isolated copy of New Earth with one
island moved 16 tiles and 50,000 starting gold for each human seat.
The stock New Earth menu entry selects the trial map in that copy.
Each PC generates the same scenario from its licensed installation.
The guest tools include the changes to apply and check locally.

The updated preflight rejected the stock map against the custom map
on both ends of a local TCP exchange. It accepted matching custom
fingerprints.

On 21 November 2026, the host and the Hyper-V guest paired over the
private VM network with host Wi-Fi connected. Both players loaded the
modified scenario. The host started with 50,000 gold, and an in-game
read confirmed the moved island at `(712, 936)`. The guest moved
its starting ship. Both players submitted matching native checksums
at three consecutive checkpoints over more than two minutes.

The World Settings setup screen still runs through the single-player
endless-game path. The multiplayer trial loaded a fixed scenario.

## Earlier launcher-based World Settings trial

Multiplayer alone uses the base game's scenario list and starting rules.
With the World Settings submod enabled, the multiplayer host can open
**World Settings** in the launcher. It opens the same native settings and
preview dialog used for single-player. The host can accept the preview or
select **Use base game maps** to return to the stock flow. A guest with
the companion enabled can join the generated map. Both installations
reconstruct the host's preview from their licensed scenario and island
files and verify the same generated scenario hash before launching.
Choose **Custom world (2-4)** in the host's native scenario list.

The current preview supports the seed, layout, island count and size,
spacing, climate, and starting gold on a 1024 × 1024 world. Options that
require the single-player runtime, such as AI configuration, island
rotation, custom starting fleets and cargo, and disasters, are disabled
for multiplayer. The generated map gives every human seat one trade ship
with 50 tons of wood, 10 of food, and 80 of tools. World Settings applies
this loadout only to its generated map.

The first World Settings VM match used seed 37, Central ocean, 24 islands,
eight-tile spacing, and 80,000 starting gold. Both peers reconstructed the
same scenario and joined with host Wi-Fi connected. The loaded host map
matched all 24 preview island positions. The VM moved its ship and the
match continued for over five minutes with matching native checksums.
That session used the original New Earth label and cargo. The follow-up
build corrects the label and normalizes the stock template's uneven cargo.

In the follow-up VM match, both copies reconstructed the revised scene
and the refreshed host cache retained **Custom world (2-4)**. The loaded
positions matched all 24 preview islands. A read of both starting ships
confirmed the same cargo amounts. The guest moved its ship and the host
observed the new position. Both copies submitted matching checksums at
four native checkpoints over three minutes with host Wi-Fi connected.
The test launcher reported a handoff error after the copied host had
left the main menu. The original process had already closed, and the
exact isolated process and build were verified again for observation.

## In-game multiplayer menu candidate

The separate menu candidate starts Anno normally. Clicking **Internet**,
**LAN Server** or **LAN Client** opens a dialog owned by the running game.
The pairing worker opens only on **Host game** or **Join game** and has no
window. It verifies the game, the active dialog and the matching peer
before handing the route back in memory. Returning from the dialog
discards the request. A completed request proceeds to the stock lobby
flow in the same process.

In the first isolated smoke test, the game reached its normal menu with
no multiplayer worker or listener on TCP 51503 or UDP 61503. All three
buttons opened the correct game-owned dialog. Submitting **Host game**
opened TCP 51503 on the selected private adapter. The local test peer
timed out, and the game returned to the selector without restarting.

Multiplayer alone uses the base-game maps. With the matching World
Settings submod enabled, **World Settings…** in either the LAN Server
or Internet Host dialog opens
the same map editor and preview used in single-player. The guest checks
**Join a World Settings map**. Both copies generate the scene locally
and compare its digest and their game inputs before entering the native
lobby. The native scenario selection uses **New Earth (2–4)** for the
generated match. **Use base game maps** clears the host's selection.
The private candidate installer can stage a copy with World Settings
unselected. That copy has the same multiplayer adapter and worker without
the companion DLL, and its in-game host and join dialogs omit the custom
map controls. The base-game compatibility fingerprint allows the two
install selections to pair on stock maps. Generated maps also require
the exact companion fingerprint on both peers.

The reviewed multiplayer controls cover 256, 512 and 1024 tile worlds,
island count, size, spacing, climate, map layout, seed, fertility and
resource distribution, starting funds, cargo and fleet. The extended
companion also supports balanced starts, preferred starting islands and
climates, guaranteed basic resources for each start, and per-copy presets.
Test 18 uses the individual-climate counts and sizes from World Settings
source revision `369c4ef`. Its optional companion includes a starting
difficulty preset, individual disaster switches and frequencies, and the
single-player severity choices for volcanoes, earthquakes and drought.
Both peers apply the selected disaster policy to the same generated scene.
Neutral cultures, faction activity and separate AI difficulty are still
under development.

Generated matches need the same verified map bytes at the native
scenario open, the lobby's seat reader, and every native checksum read.
On the reviewed stock Windows build, the relevant opens include
AnnoScene `0x356B` and AnnoFrame `0x3E679`, `0x3EAD5`, `0x400E3`,
`0x45163`, and `0x4BE22`. The in-game candidate routes those reviewed
reads to a held, verified match file. The shipped scenario and its
catalogue cache are preserved on both copies.

The optional visibility companion supports Unexplored (Terra Incognita),
Geography revealed, and Fully explored, each with strict line of sight.
It draws the verified local seat's view while the native lockstep checksum
continues to read the shared island discovery bits. Fully explored seeds
the native discovery bits for all four New Earth human seats identically
on both peers, including the inactive seats.

The first integrated host-to-VM test passed map compatibility with Wi-Fi
connected and reached the native New Earth lobby. The host observer
recorded the first simulation steps in Unexplored mode for seat 0. Both
game processes closed before a complete lockstep checkpoint. That run
did not establish sustained sync or independent visibility on the guest.
The follow-up build also clears the held file and local visibility when
the native network session ends and withholds rendering during an
unverified view transition. During the follow-up launch, Ubisoft Connect
on the host reported that the account had been accessed from another
location and signed out. After normal startup resumed, a generated
match again reached simulation with the Unexplored renderer active on
the host. Anno closed with exit status 3 before the first checksum. The
exit source is unconfirmed.

A control using the same menu build and stock New Earth ran on both
systems with Wi-Fi up and matched five native multiplayer checkpoints
over four minutes. The control used the stock renderer. Both players
then returned to the game menus without restarting. The next custom
match loaded all 24 generated islands and opened with a blank minimap
on the VM. The host reported Unexplored on seat 0, reached simulation
sequence 1, and again exited with status 3 before a checksum in that run.

A private follow-up build kept the inline scene generator and native
in-game loader and used stock rendering. Its generated 24-island New
Earth passed pairing and loaded all 24 islands. The host again exited
with status 3 at sequence 1 before a checksum. The custom visibility
hooks were never installed in this run.

A private control restored stock island links and resource requests
while keeping the same in-game route and scenario selection. Both
players entered the generated 24-island map with host Wi-Fi connected.
The host moved its ship and the game recorded three distinct matching
native checkpoints. This control used the stock renderer and stock
island resources. It did not test inline resource or rotation edits.

A second control loaded the identical seed 37 scene with Terra
Incognita and Strict line of sight active. The host's first discovery
changed the counts from 0/0 to 1/0 while the VM showed charted water and
its own ship. The VM sailed to a different coast and rendered the new
shoreline. The counts changed to 1/1 and the host's local count stayed
at one. The VM saw the host ship during the approach. Both peers matched
five native checkpoints, including one after both exploration commands,
with host Wi-Fi connected.

The inline exporter now emits the empty per-island state records used
by licensed scenarios. A mineral absent from the plan has no ore record.
The corrected inline candidate rebuilt the same advanced seed 37 map
on both peers. It loaded 24 islands, including 14 rotated ones, with
guaranteed resources, balanced starts, merchant fleets and custom cargo.
The host recorded both planned starting positions. The game still exited
with status 3 before the first native checksum. This separates the
inline load failure from the earlier successful linked-map controls.

A second private candidate kept the native linked-island route and
rebuilt the edited islands locally as content-addressed SCP files. Each
peer checked the same scene digest, which includes the 24 file digests.
The recipe retained the previous island positions and rotations,
balanced starts, merchant fleets and cargo, with different resource
choices and 30,000 starting gold. The host loaded all islands and kept
simulating for over three minutes after the VM returned to its main
menu. No checkpoint contained contributions from both peers on that
run.

A retry used identical islands, resources, rotations, positions and cargo,
with 100,000 starting gold. Both players entered the match and contributed
to two distinct matching native checkpoints with Wi-Fi connected. The
host discovered two islands while the guest's discovery count stayed at
zero. The cause of the first guest's return to the menu is unconfirmed.

The next build uses the same linked loader for generated in-game matches.
The native Start handler for those matches now checks for both admitted
players, two different available colours, and an empty native removal
queue. The colour mapping covers all eight native colours. An incomplete
lobby stays open with an explanation so the host can resolve it before
starting.

The host and VM tested this build with Wi-Fi connected. The host lobby
recorded both admitted players, distinct native colours 5 and 1, and an
empty removal queue. Both entered a Fully explored, Strict line of sight
New Earth with 24 islands. The host observed all 24 islands discovered
for both active seats. The VM displayed the populated minimap, and the
host could inspect fertility while viewing a remote island. Both peers
submitted matching native checksums at four separate checkpoints over
more than three minutes. The incomplete-lobby cases passed isolated
tests. The initial host launch exceeded the readiness deadline, then
reached the verified menu. The scenario list remained visible behind some
of the native lobby controls during this run.

Two independent offline planners generated byte-identical 2048-tile
linked scenes with 24 islands, using both regular and balanced starts.
The experimental Huge and AI build exposes 2048 tiles and up to three
stock computer opponents in the optional in-game chooser. The adapter
reads the dimensions from the verified scene and activates the reviewed
173 geometry edits only for a Huge match, before World creation on
each peer. It restores the original engine bytes once the native World
has closed. Offline tests cover both transitions and reject modification
while a World exists.

The experimental AI exporter verifies a stock Dutch scene as the donor
for ordinary CPU seat records and profiles. It reserves the native
computer colours and places starting ships near separate islands. The
adapter uses the stock controller and the matching peer rebuild checks
its generated scene digest. Independent licensed copies produced the
same seed 37 Huge scene, with 24 islands and three CPU seats. This build
uses stock AI behavior. The companion's game-free planner and the native
linked exporter produced the same scene in the reviewed kit build.
The VM downloaded that kit. On the host, Ubisoft Connect reported an
account sign-out and the normal startup timed out before launching the
isolated game.

After sign-in, the host and VM passed compatibility for the seed 37
2048-tile scene. The host stopped at the native session-name screen
before the lobby or World was created, and Windows recorded an application
hang. The retry and a 1024-tile control with the same three CPUs also
stopped there. The host observer recorded zero successful native UDP
binds. Windows reserved the range containing UDP 61503, and a local
bind on the verified VM adapter returned WinSock error 10013. A bind on
UDP 41503 succeeded.

Guest Test 12 uses UDP 41503 for its native LAN listener and peers. The
Internet route still uses UDP 61503. The test host opened the native LAN
lobby after confirming the session name. The roster contained both human
players in distinct colours, with no pending removals. The host and VM
agreed on the seed 37 scene (SHA-256
`0d00b25441db5d6ab841afe8898e30258bba5dca7061bca7243e29de026a75b7`)
and entered the 2048×2048, 24-island New Earth match with host Wi-Fi
connected. The host saw all three stock CPU controllers active. The
extended log recorded movement from all three CPU ships, and the tester
confirmed that all three AI opponents settled islands. Both peers
matched 15 distinct native sync checkpoints over about 14 minutes,
including after the VM ship order. The scenario list still appeared
behind the host's lobby controls.

### Shared flags and larger multiplayer rooms

The direct LAN lobby clears the two shared render layers when it opens,
then restores the stock lobby backdrop. The player list reads the native
LAN roster. In Test 15, the host and Hyper-V guest joined the same lobby
and both showed the stone backdrop, both player rows and clear controls.
The scenario list stayed out of the lobby on both screens.

For a new two-player New Earth match, both players can select
**Share the host’s flag (co-op)** in LAN or Internet Play. The host's
flag appears by both player names in the lobby. The guest flag picker
is disabled in co-op. Both connections play that nation with their own
gameplay input, selection and info panel. Co-op save/resume and
independent departure or rejoin remain unverified.

The host and Hyper-V guest started a stock New Earth co-op match on Test
13. Both separate native connection IDs mapped to the same World owner.
Only that owner's starting ship remained. Orders from each PC moved the
ship and both connections submitted matching native checksums afterward.
The tester reported that ship selection also changed the other player's
info panel. The separate Test 16 build keeps each connection's active
selection and info panel separate. The native command dispatcher uses
the sending player's selection for orders.

The host and Hyper-V guest tested these independent selections on stock
New Earth with only Multiplayer enabled and Wi-Fi on. The host placed
a pioneer house while the guest kept its scout selected. The guest saw
the house and moved the scout without changing the host's build panel.
Both native connection IDs mapped to the host's nation and matched
four successive sync checkpoints, including after the house and scout
orders. Test 16 was a Multiplayer-only installation. The revised build
combines independent co-op selections with the optional World Settings
companion. In Test 17, the Hyper-V guest and host joined through the
router's public address with Wi-Fi on. Both saw the same lobby flag and
started the same 1024-tile, 24-island generated world. The guest's sailing
order moved the shared ship on the host and all twelve observed sync
checkpoints matched. Live play between two independent internet
connections and full army combat remain untested.

Test 18 repeated the public-address Internet test with separate human
flags and two AI opponents on a generated 1024-by-1024 map with 24
islands. Terra Incognita and Reveal all activity were active. The
host's first discovery stayed uncharted for the guest until its own
ships explored it. Both connections continued to submit matching
synchronization checkpoints while their fleets sailed.

Test 19 used the public IPv4 route with separate flags on a generated
1024-by-1024 map with 50 islands, eight populated cultures, Pirates and
Venetians. The tester saw the building placement preview on both
screens. Both peers matched a checkpoint after the guest built its
first warehouse. A later checkpoint differed and Anno automatically
reloaded the match. Native checkpoints matched again, but the map
stayed black because the renderer still referenced the previous world
and player. The warehouse takeover was still pending at the reload.

The next candidate rebinds each view after the native reload succeeds.
The renderer fixtures cover replacement world and player objects for
both test seats, including reuse of a world address. The first
divergent Test 19 payload was overwritten. The paired diagnostic
recorder preserves each peer's local checkpoint before the next
reload so the original differing records can be compared.

Test 20 exposed an island export failure with several settings. One
reviewed, uninhabited Polar template includes empty native discovery,
warehouse ID and production records. The exporter now validates that
complete empty layout and emits it once. Offline generation reproduced
the original error with Pirates both enabled and disabled. Independent
stock copies produced identical linked scenes and island files after
the fix.

Test 21 started a 2048-by-2048, 50-island New Earth with Pirates,
Venetians and eight native cultures on the host and Hyper-V guest.
They joined through the router's public IPv4 address with Wi-Fi
connected and matched eight successive native sync checkpoints.
After the guest's warehouse was removed, the host established its
warehouse at the same location. The host trade ship fell from 38 to
26 wood and 75 to 70 tools and kept all 10 food. The guest ship
inventory held steady, and the following checkpoint matched. The
match did not enter native recovery during this observation.

The Test 21 return-to-menu attempt ended unexpectedly on both
copies. The host changed the native window owner to the startup
screen while the server and listener remained, then exited with
code 3. Stock Frame code assigns that window before game and network
destruction. The optional Huge restoration runs after both network
objects are cleared. Windows recorded no crash dump for this exit,
so the teardown trace does not identify the failing call.

Test 22 adds independent Rare, Normal and Frequent controls for
pirate reinforcements and Venetian merchant visits in optional
World Settings. The generated scene carries the selected values
in its native faction controller records. Each peer derives the
two exact AI modules from its own licensed files. Normal uses the
stock thresholds. Pirate frequency changes the reinforcement
interval and merchant frequency changes the fleet target. Nine
offline combinations produced identical scenes and island assets
on independent copies, and the native fixtures verified how both
AI variants load and apply the values.

For the live Test 22 Internet match, both peers used Frequent
pirate and merchant settings on a 1024-by-1024 map with 24 islands.
The host's native controllers loaded both values and all four observed
checkpoints matched. The host returned to the main menu and cleared
both network objects. The VM was restarted during the test, so its
return was not independently captured. The earlier Huge-map exit
failure remains unresolved.

Test 22 also reproduced an empty minimap with Geography revealed
and Reveal all activity. Early setup cleared the minimap, then that
visibility combination bypassed the full terrain redraw. Test 23
rebuilds the bitmap when the verified local view first binds or
rebinds. The native fixtures verify both player seats, initial binding,
resync, and preservation of the world's shared discovery state.

LAN and Internet rooms let players select the same count from two to
eight, including the host. The host waits for all guests to verify their
copy and map before opening the native room. Each player picks a
distinct available flag in a separate-flag match. The Internet host
uses TCP 51503 and UDP 61503. The public IPv4 address is the address the
host shares. In an Internet group, each guest receives their own
temporary ticket so players on the same remote router can join the
same host through separate UDP endpoints.

Three- and four-player rooms can use compatible base scenarios. Five to
eight players use a generated New Earth with the World Settings submod
enabled. The eight-slot generator uses distinct human owners, starting
fleets and flags, with standard visibility, default starting positions
and zero ordinary AI opponents.

Offline checks paired one host and seven LAN guests and repeated the
Internet pairing with seven guests originating from the same address.
Native fixtures exercised distinct endpoints, ticket validation, and
all eight roster positions and flags. Independent runs produced
byte-identical linked eight-slot scenes from the licensed New Earth
inputs. Live eight-player gameplay remains untested.

[Per-player visibility audit](WORLD_SETTINGS_MULTIPLAYER_VISIBILITY.md)
