# YuGiOhAccess

YuGiOhAccess is an accessible Yu-Gi-Oh! dueling client built for blind and
visually impaired players. It focuses on keyboard-first navigation, screen
reader output, audio feedback, and practical access to duel state without
requiring mouse or visual inspection.

The client is written in Python with wxPython and includes an embedded
EDOPro-compatible local server plus WindBot support for offline testing and
solo duels.

## Features

- Screen-reader friendly menus, duel field, card lists, deck editor, card
  search, replay viewer, and settings.
- Keyboard-first duel navigation with Tab traversal for currently playable
  cards.
- In-duel shortcuts for reading card name, text, stats, location, and available
  actions.
- Local offline server for creating rooms and dueling without an external
  server, including best-of-three matches with side decking between games.
- WindBot integration for adding a bot opponent from the room menu.
- Every duel is saved as a duel log: the whole duel in words, reviewable line
  by line afterwards in the replay viewer.
- Public deck selection plus deck import from YDKE/deck strings.
- Banlist validation before starting a duel.
- Card database synchronization from Project Ignis data sources.
- Multi-language card data and localized UI strings.
- Audio feedback, sound effects, music, and screen-reader output integration.
- Discord rich presence when Discord is available.
- Windows/macOS oriented packaging support through PyInstaller and Velopack.

## Recent Stability Work

This fork includes fixes aimed at making local duels with WindBot usable from
start to finish:

- Packet and duel-message callbacks no longer crash the wx event loop with
  unhandled exception dialogs.
- Compact and full `CHAT_2` packets are parsed safely.
- WindBot room join/start flow is handled more consistently.
- Duel state is initialized before first turn messages are processed.
- Drawn hand cards are synchronized into duel-field zones, preventing missing
  `ph*` and `oh*` hand-zone errors.
- Card movement gracefully handles stale or already-removed zones.
- Playable-card matching now uses card controller, location, sequence, and code
  so Tab and action menus focus on legal current choices.

## Keyboard Shortcuts

### Global/Menu Navigation

| Key | Action |
| --- | --- |
| Up / Down | Move through menu items |
| Enter | Activate selected item |
| Backspace | Go back, wherever the screen has a Back, Cancel or Close entry (still deletes text while typing) |
| Escape | The same, and cancels a duel prompt that may be cancelled |

### Duel Field

| Key | Action |
| --- | --- |
| Arrow keys | Navigate duel zones |
| Tab | Jump between currently playable cards/actions |
| Enter | Open the selected card action menu |
| Space | Read full card text |
| N | Read selected card name |
| D | Read selected card description/effect text |
| T | Read selected card stats |
| L | Read selected card location |
| A | Read available actions for the selected card |
| C | Read current chain |
| G | Open/read graveyard |
| R | Open/read banished cards |
| X | Open/read extra deck |
| M | Open chat |
| Backspace | Open duel menu |
| Escape | Cancel chaining when applicable |

## Requirements

- Python `>=3.11,<3.12`
- Windows or macOS for the full desktop experience
- A screen reader is recommended for accessibility testing
- `uv` is recommended for dependency management

Core dependencies include `wxPython`, `accessible-output3`, `requests`,
`aiohttp`, `pythonnet`, `pypresence`, `velopack`, and audio libraries.

## Running From Source

```powershell
uv sync
uv run python src/YuGiOhAccess.py
```

Or with an already-created virtual environment:

```powershell
python -m pip install -e .
python src/YuGiOhAccess.py
```

On first launch, YuGiOhAccess creates its application data directory and
synchronizes card databases, banlists, and language data.

## Local Duel Workflow

1. Start YuGiOhAccess.
2. Choose `Play`.
3. Select `Local (Offline)`.
4. Create a room.
5. Select or import a deck.
6. Add WindBot as opponent.
7. Start the duel.
8. Use Tab and the duel shortcuts above to inspect playable cards and actions.

## Development

Install development dependencies:

```powershell
uv sync --dev
```

Run the checks CI runs:

```powershell
uv run ruff check                      # lint
uv run mypy                            # types
uv run python scripts/check_repo_hygiene.py   # nothing generated got committed
uv run pytest --cov=src --cov-report=term     # tests, with the coverage floor
```

Or have them run before each commit:

```powershell
uv run pre-commit install
uv run pre-commit run --all-files
```

Run a focused test file:

```powershell
uv run pytest tests/test_duel_field_more.py
```

The current test suite covers packet handling, local server flow, WindBot
launching, duel messages, card selection, duel field behavior, and UI helpers.

### Translations

UI strings live in `locales/<lang>/LC_MESSAGES/yugiohaccess.po`. The `.pot`
template and the compiled `.mo` files are build output and are not committed.

```powershell
uv run python scripts/i18n_extract.py   # refresh the template and every .po
uv run python scripts/i18n_compile.py   # compile, and report coverage per language
```

A language is offered in Settings only when its catalogue actually contains
translations, so a `.po` that nobody has filled in yet is never shown as a
choice that does nothing. Compiling prints how far along each language is.
Contributions go in the `.po` files; `scripts/i18n_extract.py` keeps them in
step with the source, and the test suite fails if the template falls behind.

### Duel sound effects

Every sound the duel asks for is checked by the test suite, so an effect that
is referenced but not shipped fails the build instead of going silently
missing. To see the state of the set, or to rebuild it:

```powershell
uv run python scripts/build_sound_effects.py --check
uv run python scripts/build_sound_effects.py --soundpack <path to a clone of https://github.com/Lahrenheit/EDOPRO-Soundpack>
```

Provenance and licensing for each file is recorded in
`src/data/sounds/duel/ATTRIBUTION.md`. The effects are either synthesised by
that script or built from CC0 recordings; nothing is taken from a source whose
terms do not allow it.

## Project Layout

| Path | Purpose |
| --- | --- |
| `src/YuGiOhAccess.py` | Application entry point |
| `src/ui/` | wxPython UI, menus, duel field, accessibility output |
| `src/ui/duel_messages/` | EDOPro duel-message handlers |
| `src/game/` | Client protocol, cards, decks, server definitions |
| `src/server/` | Embedded EDOPro-compatible local server |
| `src/bot/` | WindBot launcher and integration |
| `src/data/` | Bundled decks, scripts, locales, and assets |
| `tests/` | Pytest coverage for client, server, UI, and protocol behavior |

## Contributing

Contributions are welcome, especially in these areas:

- Accessibility improvements for screen-reader workflows.
- Reproducible duel bugs with logs and exact steps.
- Keyboard navigation fixes.
- Card selection and action-menu correctness.
- Localization fixes.
- WindBot and local-server compatibility.
- Test coverage for duel-message handlers.

When reporting a bug, include:

- Operating system and Python version.
- Whether the issue happened on local/offline server or an online server.
- Deck used by the player and bot.
- Exact menu path or duel phase.
- Relevant log excerpt from the application log file.

Before opening a pull request:

- Keep changes focused.
- Add or update tests for behavior changes.
- Run `uv run pytest`.
- Avoid committing local virtual environments, generated caches, or personal
  app data.

## Notes

- Running directly from source may show Velopack "not installed" messages. That
  is expected outside an installed packaged build and does not prevent local
  development.
- Discord presence warnings are harmless when Discord is not running.
- A sound effect with no file is logged once as a warning and does not block
  duels. The set is complete, and a test keeps it that way.
- This project includes and integrates WindBot-derived components for offline
  bot duels.

## License

YuGiOhAccess is free and open source software under the GNU Affero General
Public License, version 3 or later. See [COPYING](COPYING) and [LICENSE](LICENSE)
for details.

