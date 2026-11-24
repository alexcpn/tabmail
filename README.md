# tabmail

A Gmail inbox for the terminal, sorted into tabs by an AI.

## Why

A real inbox is mostly noise: bank alerts, order updates, job alerts,
newsletters, promotions. The few emails a person actually wrote to you get
buried among them. Gmail's own help doesn't fix this:

- **Its "Important" marker is too generous.** It flags a cafe's daily update
  as readily as a message from a friend.
- **Its category tabs are fixed.** You can't say what *you* mean by
  Notifications or Jobs.
- **Filters are endless upkeep.** Every new sender needs another rule, and the
  rules quietly go stale.

tabmail takes a different approach: you describe each tab in a sentence of
plain English, and a small, fast AI model reads each email's sender and
subject and decides. When it gets one wrong, press `c`, move the email and add
a note, and it learns from that. You keep tuning a few sentences, not
hundreds of filter rules.

## What it is

A keyboard-driven terminal app. A tab is just a name and a description, such
as "Important: written to me by a real person, or needs me to act". Claude
Haiku (by default) sorts every email into one of those tabs.

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
- **For sorting, only sender and subject go to the AI**, never email bodies.
  Email text is passed as data, and the `claude` CLI runs with no tools.
- **Summaries on demand.** Press `s` for a short AI summary of the email you're
  on (or of a selection), with any action and deadline first. Only then is that
  email's text sent to the AI; set `summaries = false` to turn this off.
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
5. Save it as `~/.config/tabmail/credentials.json`.

On the first run a browser window opens so you can sign in. The token is saved
to `~/.config/tabmail/token.json` (mode 600).

### 2. An AI backend (pick one)

| `ai =` | What it uses | Setup |
|---|---|---|
| `claude-cli` | the [Claude Code](https://claude.com/claude-code) CLI in headless mode (`claude -p`); it runs on whatever `claude` is logged in with, such as a Claude subscription | install `claude` and log in |
| `anthropic-api` | the Anthropic API | `export ANTHROPIC_API_KEY=…` |
| `auto` (default) | `claude-cli` if installed, else the API if a key is set | |
| `off` | no AI; a simple fallback using Gmail's own labels | |

### 3. Your config

```sh
mkdir -p ~/.config/tabmail
cp config.example.toml ~/.config/tabmail/config.toml
```

Edit the tab names, the `description` of each tab, and the free-form
`instructions`. That text is all the AI goes on. Optional `senders` pins mail
from given addresses to a tab, overriding the AI; `"me"` matches mail you send
to yourself. Set `TABMAIL_CONFIG` to use a config file somewhere else.

## Run

```sh
uv run tabmail.py
```

[uv](https://docs.astral.sh/uv/) installs the dependencies on the first run.

| Key | Action |
|---|---|
| `↑/↓` | move between emails (nothing is loaded until you press `Enter` or `s`) |
| `←/→` or `h/l` | switch tabs |
| `Enter` | show the email text in a side panel |
| `PgDn/Space`, `PgUp` | scroll the side panel |
| `o` | open the email in Gmail |
| `Shift+↑/↓` | select several conversations (■) |
| `D` or `Delete` | move the selected conversations, or the current one, to Trash (needs `allow_changes = true`) |
| `u` | undo the last move to Trash (the whole batch) |
| `s` | AI summary of the current email, or one combined summary of a selection (up to 10) |
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
| `~/.config/tabmail/config.toml` | your tabs and instructions |
| `~/.config/tabmail/credentials.json` | your Google OAuth client (never commit it) |
| `~/.config/tabmail/token.json` | your Gmail sign-in token |
| `~/.config/tabmail/corrections.json` | your manual moves and notes for the AI |
| `~/.cache/tabmail/ai_tabs.json` | cached AI sorting results |

## Tests

```sh
uv run --with pytest --with textual --with google-api-python-client \
  --with google-auth-oauthlib --with anthropic pytest -q tests
```

The tests run offline and don't call Gmail or any AI.

## License

MIT, see [LICENSE](LICENSE).
