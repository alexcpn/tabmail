# gmail-tui

A read-only Gmail inbox for the terminal, sorted into tabs by an AI.

You describe your tabs in plain English ("Important: written to me by a real
person, or needs me to act"). A small, fast model (Claude Haiku by default)
reads each email's **sender and subject** and puts it in the tab that fits.
There are no hard-coded sender lists or filters to maintain.

```
 Important (4, 2●) │ Notifications (31) │ Jobs (12) │ News (40) │ Other (3)
 ● Priya             Dinner on Saturday?                      14:02 │ From: Priya <…>
 ● Electricity Board Your bill of Rs 3,420 is due on 28 Nov   09:15 │ Subject: Dinner on Saturday?
   Me                Portfolio: close of 20 Nov               23 Nov │
                                                                    │ Hi! Are you free…
```

- **Read-only by default.** It uses the `gmail.readonly` scope, so it can't
  send, delete or change anything. Set `allow_changes = true` to have opening
  an email mark it read, and `D` move it to Trash (`u` undoes it). That asks
  Google for `gmail.modify` instead. Mail is never deleted permanently or sent.
- **Only sender and subject go to the AI**, never email bodies. Email text is
  passed as data, and the `claude` CLI runs with no tools.
- **Each email is sorted once.** Results are cached per conversation, so a
  refresh only sends new mail. Edit your config and everything is re-sorted.

## Setup

### 1. Gmail API access (one time)

1. In [Google Cloud Console](https://console.cloud.google.com/), create or pick a project.
2. **APIs & Services → Library**: enable the **Gmail API**.
3. **APIs & Services → OAuth consent screen**: choose External, add yourself
   as a test user, and add the scope `.../auth/gmail.readonly` (plus
   `.../auth/gmail.modify` if you'll use `allow_changes`).
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   choose **Desktop app** and download the JSON file.
5. Save it as `~/.config/gmail-tui/credentials.json`.

On the first run a browser window opens so you can sign in. The token is saved
to `~/.config/gmail-tui/token.json` (mode 600).

### 2. An AI backend (pick one)

| `ai =` | What it uses | Setup |
|---|---|---|
| `claude-cli` | the [Claude Code](https://claude.com/claude-code) CLI in headless mode (`claude -p`); it runs on whatever `claude` is logged in with, such as a Claude subscription | install `claude` and log in |
| `anthropic-api` | the Anthropic API | `export ANTHROPIC_API_KEY=…` |
| `auto` (default) | `claude-cli` if installed, else the API if a key is set | |
| `off` | no AI; a simple fallback using Gmail's own labels | |

### 3. Your config

```sh
mkdir -p ~/.config/gmail-tui
cp config.example.toml ~/.config/gmail-tui/config.toml
```

Edit the tab names, the `description` of each tab, and the free-form
`instructions`. That text is all the AI goes on. Optional `senders` pins mail
from given addresses to a tab, overriding the AI; `"me"` matches mail you send
to yourself. Set `GMAIL_TUI_CONFIG` to use a config file somewhere else.

## Run

```sh
uv run gmail_tui.py
```

[uv](https://docs.astral.sh/uv/) installs the dependencies on the first run.

| Key | Action |
|---|---|
| `↑/↓` | move between emails (the side panel follows while it is open) |
| `←/→` or `h/l` | switch tabs |
| `Enter` | show the email text in a side panel |
| `PgDn/Space`, `PgUp` | scroll the side panel |
| `o` | open the email in Gmail |
| `Shift+↑/↓` | select several conversations (■); the side panel stays put |
| `D` or `Delete` | move the selected conversations, or the current one, to Trash (needs `allow_changes = true`) |
| `u` | undo the last move to Trash (the whole batch) |
| `c` | move the current or selected conversations to another tab, or to a new one, with an optional note for the AI |
| `Esc` | clear the selection, or close the side panel |
| `r` | refresh |
| `q` or `Ctrl+C` | quit |

`●` means unread. With `allow_changes = true`, opening an email marks it read in Gmail. The header shows how many conversations were loaded and which
AI backend is in use.

## Teaching it

When the AI gets one wrong, press `c` on it (or on a Shift-selection), pick the
right tab, and optionally add a note such as "daily updates from this cafe are
notifications". Then:

- that conversation stays where you put it;
- your most recent corrections (up to 40), with notes, are shown to the AI as examples
  every time it sorts;
- other mail from the same sender is re-sorted straight away with the new example.

Choosing **+ New tab…** asks for a name and a one-line description, adds the tab
to your `config.toml`, and re-sorts everything so the new tab can pick up mail.

## Files

| Path | What |
|---|---|
| `~/.config/gmail-tui/config.toml` | your tabs and instructions |
| `~/.config/gmail-tui/credentials.json` | your Google OAuth client (never commit it) |
| `~/.config/gmail-tui/token.json` | your Gmail sign-in token |
| `~/.config/gmail-tui/corrections.json` | your manual moves and notes for the AI |
| `~/.cache/gmail-tui/ai_tabs.json` | cached AI sorting results |

## Tests

```sh
uv run --with pytest --with textual --with google-api-python-client \
  --with google-auth-oauthlib --with anthropic pytest -q tests
```

The tests run offline and don't call Gmail or any AI.

## License

MIT, see [LICENSE](LICENSE).
