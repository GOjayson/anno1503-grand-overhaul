ANNO 1503 HISTORY EDITION - COMBINED FOOD MOD
Version 0.5.0 - consumer goods and market price display

INSTALL / UPDATE
1. Close Anno 1503.
2. Extract anno1503_food_mod beside Anno1503.exe. Replace the previous
   anno1503_food_mod folder when Windows asks.
3. Open that folder and double-click INSTALL.cmd.
4. Wait for "Finished successfully."

Install directly over Combined Food Mod 0.4.0 or 0.4.1; do not restore first.
This is the complete mod. No earlier installer folders or separate installs
are required. Keep the game's files and existing *_Backup_* folders.

Supported inputs: the inspected vanilla History Edition, Fish 0.1.4,
Game Meat 0.2.2, either Food Market 0.3 variant, and Combined 0.4.0/0.4.1.
INSTALL.cmd includes all file checks; CHECK.cmd checks without installing.
Python 3.10 or newer is required, with no additional Python packages or tools.
Unrecognized game binaries are rejected before any installation writes.

NEW IN 0.5.0
- Fish, Game Meat, Potatoes, Bread and Butcher's Meat occupy the first five
  positions under Consumer Goods in city storage, the general goods chooser,
  and the ship-loading chooser. The other consumer goods follow normally.
- Game Meat and Bread are removed from those Raw Materials tabs; Butcher's
  Meat is removed from their Building Materials tabs.
- Ship scrolling and automatic selection reach all 18 consumer goods.
- All six Food market prices now draw ABOVE their coin frames. In 0.4.1,
  the later-drawn opaque frames covered every number despite correct values.
- The building preview is moved up 20 pixels, the old two-branch connectors
  are hidden, and icons/prices use aligned three-column rows with clearance
  above the maintenance/demolition controls. Other stands restore their
  original preview, icons, price labels and decorations.

The categories are explicit UI lists. Stock/save IDs, resident needs,
production, trade commands and sale accounting stay compatible with 0.4.1.
Sprite-sheet group names still reflect the original resource organization;
menus resolve each item's actual icon by its good ID.

ALL EARLIER CHANGES INCLUDED
Fish replaces vanilla Food and remains the main staple/starvation good.
One Food market offers Fish, Salt, Game Meat, Potatoes, Bread and Butcher's
Meat. Jewelry and Wine stands retain their original goods.

Food             Production                         First requirement
Fish             Fisherman's hut                    From the start
Game Meat        Hunting lodge (+ Hides)            From the start
Potatoes         Small farm (+ Alcohol)             From the start
Butcher's Meat   Existing butcher chain             Butcher-chain unlock
Bread            Existing grain/mill/bakery chain   Bread-chain unlock

The full diet is unchanged: Fish 60%, Game Meat 15%, Potatoes 15%, Bread 5%,
Butcher's Meat 5% of the original total Food demand. Other needs, including
Salt, retain their normal requirements. All five foods have distinct colour
and grey icons. Salt keeps its original icon.

The 0.4.1 repairs are included: house selection among all six market goods,
working sale switches and red crosses, stock debit, house receipt and city
sale income for the added foods. Prices use the original climate/world-price
formula rather than fixed display values.

SAVES AND IN-GAME CHECK
- From Combined 0.4.0/0.4.1 or full-diet 0.3: use a COPY of an existing save.
  Good IDs, production, resident needs and six saved sale bits are unchanged.
  This installer does not edit saved games.
- From vanilla, Fish, Game Meat or Fish-only 0.3: start a NEW sandbox because
  stocks and/or requirements differ.
- Use a sandbox without AI opponents. The existing AI index guard is included;
  computer-player planning for extra foods has not been implemented.
- Check the five foods in Consumer Goods in city storage and goods selection.
  On a ship, scroll down/up and select the last goods as well as the foods.
- Check all six market prices and click each sale switch off/on. Leave the
  desired foods enabled. Let residents make several shopping trips: stock
  labels show whole tons while individual purchases can be smaller.
- Check house supply, falling stocks, sale income and save/reload behavior.

RESTORE
Close the game and run THIS package's RESTORE.cmd. It returns to the exact
setup present before 0.5.0. An upgrade from 0.4.1 therefore restores 0.4.1.
The new backup is FoodMod_Backup_0_5. Earlier backups are left intact.

Do not run an older installer/restore while 0.5.0 is active. Restore 0.5.0
first before returning through earlier layers. Completed backups are retained
with .previous-N suffixes when reinstalling after restoration.

IF SOMETHING FAILS
- Installation error: copy the ERROR line.
- Game hangs: leave it open, run CAPTURE_HANG.cmd and attach its report ZIP.
- Game crashes: run COLLECT_CRASH.cmd and attach its report ZIP.
Reports omit game DLLs, saves and raw memory dumps. Nothing is uploaded
without your action.

VALIDATION AND LIMITS
11 original-data tests pass, including seven installation inputs, exact
restore, rollback, diagnostics and low-resolution/localized UI assets.
Native x64 checks execute the category constructors, ship paging/selection,
price text drawing/order and the previously repaired purchases/accounting.
The complete Windows game/graphics engine cannot be launched here; confirm
these changes in your game. See VALIDATION.txt for details.
