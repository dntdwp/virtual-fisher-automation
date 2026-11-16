# Virtual Fisher Automation

An automated Python Discord client & terminal UI (TUI) bot for the **Virtual Fisher** Discord bot, upgraded for modern **Discord Components V2** payloads, resilient OCR captcha handling, startup state recovery, and concurrency-safe command scheduling.

> **Attribution:** Forked and significantly upgraded from [`thejoabo/autofishbot`](https://github.com/thejoabo/autofishbot) under the [MIT License](LICENSE).
>
> **Disclaimer:** This project is maintained for educational and automation-engineering portfolio purposes. Automating user accounts (self-botting) may violate Discord's Terms of Service—use responsibly and at your own risk.

---

## Key Features & Engineering Improvements

### 1. Discord Components V2 Support (`app/message.py`, `app/captcha.py`)
- Recursive extraction of nested **Discord Components V2** structures (`type: 17` Container, `type: 10` Text Display, `type: 12` Media Gallery, and `type: 1` Action Row / Buttons) alongside legacy embeds.
- Reliably parses catch logs (`You caught:`), interactive **Fish Again** button IDs, and captcha media URLs even when `content` and `embeds` are empty.

### 2. Resilient Captcha Pipeline (`app/captcha.py`)
- **CDN-Safe Image Fetching:** Downloads captcha images directly and uploads them as Base64 payloads to the OCR.space API (`OCREngine` `2` and `1`), preventing Discord CDN link blocking or token expiration errors.
- **OCR Disambiguation:** `generate_candidates()` automatically generates fallback candidates for commonly misread characters (`g` ↔ `q`, `l` ↔ `1`, `0` ↔ `O`, `5` ↔ `S`, `2` ↔ `Z`) so a single character confusion is retried immediately before regenerating.
- **Multi-Source Extraction:** Supports plain-text codes (stripping Markdown formatting), Components V2 Media Gallery items, attachments, embeds, and regex CDN URL fallbacks, with up to `5` automatic captcha regenerations (`MAX_CAPTCHA_REGENS = 5`).

### 3. Startup Recovery & Concurrency Locks (`autofishbot.py`, `app/scheduler.py`)
- **Startup Captcha Check (`check_initial_captcha`):** Inspects recent channel messages at startup to detect and resolve any pending captcha *before* starting the fishing loop or scheduler.
- **Strict Captcha Lock:** Fixed boolean precedence in `Scheduler.check_task()` and added blocking waits so background tasks (`/buy`, `/sell`, `/daily`, `/profile`) never fire while a captcha is active or paused.
- **Safety Auto-Stop:** Automatically kills threads and exits cleanly if a ban message is detected.

### 4. Discord API & Gateway Resilience (`app/api_wrapper.py`, `autofishbot.py`)
- **Dynamic Slash Command Mapping:** Automatically adapts slash command option names (e.g., `result` vs `answer`) against Discord's application command schema.
- **Safe Event & Rate-Limit Handling:** Guards against `None` payloads in Gateway heartbeat ACKs (`check_event`), safely parses HTTP `429` rate-limit responses, and suppresses noisy expired-button `COMPONENT_VALIDATION_FAILED` errors so the dispatcher smoothly falls back to `/fish`.

### 5. Humanized Timing & TUI Dashboard (`app/cooldown.py`, `app/menu.py`)
- Gaussian-distributed fishing cooldowns, randomized scheduler delays, and periodic break intervals.
- Interactive `curses`-based TUI (`MainMenu` and `CompactMenu`) with customizable keybinds and optional HTTPS proxy support.

---

## Project Structure

```text
autofishbot/
├── autofishbot.py          # Main entry point (Receiver, Dispatcher, initialization)
├── requirements.txt        # Python dependencies
├── assets/
│   └── template.config     # Sample configuration template
├── configs/                # Local user configs (*.config is git-ignored)
└── app/
    ├── api_wrapper.py      # Discord REST API & WebSocket Gateway wrapper
    ├── captcha.py          # Captcha detector & multi-engine OCR solver
    ├── config.py           # Config parser, validator, and generator
    ├── cooldown.py         # Gaussian cooldown calculator
    ├── menu.py             # Curses TUI dashboard & keybind handler
    ├── message.py          # Discord Components V2 & embed parser
    ├── profile.py          # Inventory, charms, buffs, quests, leaderboard models
    ├── scheduler.py        # Periodic automation queue & break scheduler
    └── utils.py            # Sanitization helpers and file debugger
```

---

## Requirements

- **Python 3.10+** (uses `match/case` and modern typing)
- **OCR.space API Key** (free tier available at [ocr.space/ocrapi/freekey](https://ocr.space/ocrapi/freekey))

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/dntdwp/virtual-fisher-automation.git
   cd virtual-fisher-automation
   ```

2. **Install dependencies:**
   ```bash
   python -m pip install -r requirements.txt
   ```
   > **Linux / macOS note:** Remove or skip the `windows-curses` line in `requirements.txt`, as `curses` is built into Python on Unix-like systems.

---

## Configuration

Your credentials and IDs stay completely local—`configs/*.config`, `.env*`, and `*.log` are excluded in `.gitignore`.

### Option A: Interactive Generator
```bash
python autofishbot.py --create
```

### Option B: Manual Setup from Template
1. Copy [`assets/template.config`](assets/template.config) into `configs/mybot.config`.
2. Fill in the required fields:

```ini
[SYSTEM]
USER_TOKEN = YOUR_DISCORD_USER_TOKEN
USER_COOLDOWN = 2.4
CHANNEL_ID = YOUR_TARGET_CHANNEL_ID
GUILD_ID = YOUR_TARGET_GUILD_ID
DEBUG = True

[CAPTCHA]
OCR_API_KEY = YOUR_OCR_SPACE_API_KEY
```

- `USER_COOLDOWN`: Valid range is `2.0` to `3.5` seconds (adjust to match your in-game boat/rod cooldown).
- Optional sections in `template.config` configure HTTPS proxies (`[NETWORK]`), auto boosts/sell/daily/baits (`[AUTOMATION]`), and UI refresh rate/compact mode (`[MENU]`).

---

## Usage

Run the bot from the repository root:

```bash
python autofishbot.py
```

Or specify a config file directly:

```bash
python autofishbot.py mybot.config
```

### Default Keybinds

| Key | Action |
| :---: | :--- |
| `p` | Pause / Resume bot |
| `Q` | Quit bot safely |
| `s` | Sell inventory |
| `I` | Update inventory / profile |
| `L` | Update leaderboards |
| `K` | Update cosmetics |
| `F` | Buy More Fish boost |
| `T` | Buy More Treasures boost |
| `D` | Claim daily reward |
| `Y` | Show quests popup |
| `o` | Show current inventory popup |
| `C` | Show charms popup |
| `B` | Show buffs popup |
| `e` | Show exotic fishes popup |

Keybinds can be customized after first launch in `app/keybinds.json` (also git-ignored).

---

## License

Released under the [MIT License](LICENSE). Original codebase copyright (c) 2021 Joabo.
