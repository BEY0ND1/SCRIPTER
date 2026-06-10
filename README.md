# Scripter

A Final Draft–style screenwriting program in a single Python file. No
dependencies — it runs on the `tkinter` library that ships with Python,
so it works anywhere Python does, including straight from IDLE.

## Run it

1. Install Python 3.8+ from python.org (tkinter is included)
2. Open IDLE → File → Open… → `scripter.py`
3. Press **F5**

Or from a terminal: `python scripter.py`

## The Final Draft workflow

| Key | What it does |
| --- | --- |
| `Enter` | Next logical element (Scene Heading → Action, Character → Dialogue, Dialogue → Character…) |
| `Tab` | Empty line: cycle element type · with text: jump (Action → Character, Dialogue → Parenthetical…) |
| `Shift+Tab` | Cycle element type backwards |
| `Ctrl/Cmd + 1–7` | Scene · Action · Character · Parenthetical · Dialogue · Transition · Shot |
| `Backspace` at line start | Merge with the element above |
| `F1` | All shortcuts |

**SmartType** suggests INT./EXT., your characters, your locations, times of
day, and standard transitions as you type — arrows to choose, Enter to accept.

## Features

- Industry-standard formatting: Courier 12pt, 1.5" left margin, correct
  indents and widths per element, auto-uppercase, auto-parentheses
- Scene navigator sidebar — click any slugline to jump
- Live page estimate (≈55 lines/page), scene and word counts
- Title page editor
- Saves to `.screenplay` (plain JSON), **opens and exports real Final
  Draft `.fdx`** files, exports formatted text

## Supporting development

Scripter is free. If it helps your writing, you can support development on
Ko-fi: **[ko-fi.com/beyondak](https://ko-fi.com/beyondak)** — or just hit
the **♥ Donate** button in the toolbar (Help → Support Scripter works too).

**Forking?** Point the buttons at your own pages at the top of `scripter.py`:

```python
DONATION_URL = "https://ko-fi.com/beyondak"           # any donation URL
PROJECT_URL  = "https://github.com/yourname/scripter"
```

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, ship it.
