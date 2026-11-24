# tabmail privacy policy

tabmail is an open-source program that runs entirely on your own computer.
Its author runs no servers and collects no data.

## What tabmail accesses

With your permission, tabmail uses the Gmail API, or Gmail's IMAP service
with an app password you create, to read the messages in your mailbox:
senders, subjects, dates, labels and, when you open or summarize an email,
its text. If you turn on `allow_changes`, it can also mark emails as
read and move them to Trash when you press the keys for that. It never sends
email or deletes anything permanently.

## Where your data goes

- **Your computer.** Your Google sign-in token, settings and corrections are
  stored in `~/.config/tabmail/`, an app password in your system keyring, and
  cached sorting results in `~/.cache/tabmail/`. Email text is not written to disk.
- **The AI you configure.** To sort mail, tabmail sends each email's sender,
  subject and a few Gmail labels to the AI backend you set up (by default the
  Claude Code CLI on your machine, which uses your own Claude account). When
  you press `s`, the text of the email you're summarizing is sent the same
  way. Set `ai = "off"` or `summaries = false` to stop this.
- **Nowhere else.** tabmail doesn't send your data to its author or to any
  other third party, and it contains no analytics or tracking.

tabmail's use of information received from Google APIs adheres to the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements.

## Removing access

Delete `~/.config/tabmail/` and `~/.cache/tabmail/`, run
`uv run tabmail.py --forget-imap`, and revoke tabmail's access at
<https://myaccount.google.com/permissions> (Google API) or delete its app
password at <https://myaccount.google.com/apppasswords> (IMAP).

## Contact

Open an issue at <https://github.com/alexcpn/tabmail/issues>.
