# tabmail

Is your inbox out of control? Try tabmail: a dead-simple email viewer,
sorted by common sense and a small AI.

> For those who are comfortable with CLIs only! Built for people who'd rather
> press keys than click. Tested with the Claude Code CLI.

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

- **Changes nothing unless you ask.** By default tabmail only reads. Set
  `allow_changes = true` to have opening an email mark it read, and `D` move
  it to Trash (`u` undoes it). Mail is never deleted permanently or sent.
- **For sorting, only sender and subject go to the AI**, never email bodies.
  Email text is passed as data, and the `claude` CLI runs with no tools.
- **Summaries on demand.** Press `s` for a short AI summary of the email you're
  on (or of a selection), with any action and deadline first. Only then is that
  email's text sent to the AI; set `summaries = false` to turn this off.
- **Each email is sorted once.** Results are cached per conversation, so a
  refresh only sends new mail. Edit your config and everything is re-sorted.

## Quick start

You need [uv](https://docs.astral.sh/uv/) and
[Claude Code](https://claude.com/claude-code) logged in. No Google Cloud
project is needed.

1. Create a Gmail [app password](https://myaccount.google.com/apppasswords)
   named "tabmail". This needs [2-Step Verification](https://myaccount.google.com/signinoptions/twosv)
   turned on.
2. Get tabmail and start it:

   ```sh
   git clone https://github.com/alexcpn/tabmail
   cd tabmail
   uv run tabmail.py
   ```

3. When asked, enter your Gmail address and the app password. tabmail checks
   them and saves them in your system keyring, so you only do this once.

Your inbox opens, sorted into tabs. To make the tabs your own, copy
`config.example.toml` to `~/.config/tabmail/config.toml` and edit the
descriptions (see [Your config](#3-your-config)). To start tabmail with the
Super key or Spotlight, run `./install-launcher.sh`.

## Setup

### 1. Sign in to Gmail (pick one)

**Easy: an app password (about 2 minutes, no Google Cloud project).**

1. Turn on [2-Step Verification](https://myaccount.google.com/signinoptions/twosv)
   for your Google account, if it isn't on already.
2. Create an [app password](https://myaccount.google.com/apppasswords) named
   "tabmail".
3. Run `uv run tabmail.py`. It asks for your Gmail address and the app password,
   checks them, and saves them in your system keyring (GNOME Keyring, KWallet or
   the macOS Keychain).

tabmail then reads your mail over IMAP. An app password gives full access to
your mailbox (it can't be limited to read-only), but tabmail only changes
anything when `allow_changes = true` and you press the keys for it. To change
or remove the saved password, run `uv run tabmail.py --setup-imap` or
`uv run tabmail.py --forget-imap`. Some work or school accounts don't allow app
passwords; use the option below for those.

**Read-only: your own Google Cloud project (about 15 minutes).**

This uses the Gmail API with read-only access (`gmail.readonly`) unless you
turn on `allow_changes`.

1. In [Google Cloud Console](https://console.cloud.google.com/), create or pick a project.
2. **APIs & Services → Library**: enable the **Gmail API**.
3. **Google Auth Platform → Branding**: fill in the app name, a home page and
   a privacy policy link (this repository and its `PRIVACY.md` work), and add
   the domain under **Authorized domains**.
4. **Google Auth Platform → Data Access**: add the scope
   `.../auth/gmail.readonly` (plus `.../auth/gmail.modify` if you'll use
   `allow_changes`).
5. **Google Auth Platform → Clients → Create client**: choose **Desktop app**
   and download the JSON file. Save it as `~/.config/tabmail/credentials.json`.
6. **Google Auth Platform → Audience**: click **Publish app**. In "Testing"
   mode, Google signs you out every 7 days.

On the first run a browser window opens so you can sign in. Google warns that
it "hasn't verified this app": that's expected for your own project. Click
**Advanced → Go to tabmail (unsafe)**. The token is saved to
`~/.config/tabmail/token.json` (mode 600).

tabmail picks the method automatically: a saved app password first, then a
Google Cloud client if `credentials.json` exists, otherwise it asks for an app
password. Set `auth = "imap"` or `auth = "google-api"` in your config to choose.

### 2. An AI backend

**If you use [Claude Code](https://claude.com/claude-code) with a Claude
subscription, there's nothing to do.** tabmail runs the `claude` CLI in headless
mode (`claude -p`), so sorting and summaries use your existing login.

| `ai =` | What it uses |
|---|---|
| `auto` (default) | the `claude` CLI, if it's installed |
| `claude-cli` | the `claude` CLI, always |
| `off` | no AI; a simple fallback using Gmail's own labels |

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

| Command | What it does |
|---|---|
| `uv run tabmail.py` | start tabmail |
| `uv run tabmail.py --setup-imap` | sign in with a Gmail app password, replacing any saved one |
| `uv run tabmail.py --forget-imap` | remove the saved app password from your keyring |
| `uv run tabmail.py --help` | list these options |

### Start it from your app launcher

```sh
./install-launcher.sh
```

- **Linux:** adds tabmail to the app launcher. Press Super and type `tabmail`
  or `mail`, and it opens in your default terminal.
- **macOS:** creates `~/Applications/tabmail.app`, which opens Terminal running
  tabmail. Press Cmd+Space and type `tabmail`; typing just `mail` finds Apple
  Mail first.

`./install-launcher.sh --uninstall` removes it. Re-run the installer if you
move the tabmail folder.

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
| system keyring, entry "tabmail" | your Gmail address and app password (IMAP sign-in) |
| `~/.config/tabmail/credentials.json` | your Google OAuth client, if you use one (never commit it) |
| `~/.config/tabmail/token.json` | your Gmail sign-in token |
| `~/.config/tabmail/corrections.json` | your manual moves and notes for the AI |
| `~/.cache/tabmail/ai_tabs.json` | cached AI sorting results |

## Tests

```sh
uv run --with pytest --with textual --with google-api-python-client \
  --with google-auth-oauthlib --with anthropic --with keyring pytest -q tests
```

The tests run offline and don't call Gmail or any AI.

## License

MIT, see [LICENSE](LICENSE).
