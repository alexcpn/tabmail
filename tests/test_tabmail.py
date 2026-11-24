"""Offline tests: no Gmail, no AI calls.  Run:  uv run --with pytest pytest -q"""

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tabmail as g  # noqa: E402

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.toml"


def mail(tid, addr, subject="s", labels=(), bulk=False):
    return g.Mail(tid, addr.split("@")[0], addr, subject, None, set(labels), bulk)


@pytest.fixture
def cfg():
    return g.load_config(EXAMPLE)


def test_example_config_loads(cfg):
    assert [t.name for t in cfg.tabs] == ["Important", "Notifications", "Jobs", "News", "Other"]
    assert all(t.description for t in cfg.tabs)
    assert "real person" in cfg.instructions
    assert cfg.fallback_tab == "Other"


def test_pins_beat_everything(cfg, tmp_path):
    p = tmp_path / "c.toml"
    p.write_text(EXAMPLE.read_text().replace(
        'name = "News"', 'name = "News"\nsenders = ["substack.com"]'
    ).replace('name = "Important"', 'name = "Important"\nsenders = ["me"]'))
    c = g.load_config(p)
    assert g.pinned_tab(mail("1", "x@substack.com"), c, "me@x.com") == "News"
    assert g.pinned_tab(mail("2", "ME@x.com"), c, "me@x.com") == "Important"
    assert g.pinned_tab(mail("3", "a@b.com"), c, "me@x.com") is None


def test_fallback_without_ai(cfg):
    assert g.fallback_classify(mail("1", "friend@gmail.com", labels={"IMPORTANT"}), cfg) == "Important"
    assert g.fallback_classify(mail("2", "x@shop.com", labels={"IMPORTANT"}, bulk=True), cfg) == "Other"
    assert g.fallback_classify(mail("3", "a@b.com"), cfg) == "Other"


def test_is_bulk():
    assert g.is_bulk({"list-unsubscribe": "<x>"}, "a@b.com")
    assert g.is_bulk({"precedence": "bulk"}, "a@b.com")
    assert g.is_bulk({}, "no-reply@shop.com")
    assert not g.is_bulk({}, "priya@gmail.com")


def test_prompt_is_built_from_text(cfg):
    p = g.ai_prompt(cfg)
    for t in cfg.tabs:
        assert f"- {t.name}: {t.description}" in p
    assert cfg.instructions in p
    assert "untrusted data" in p


def test_ai_lines_sanitise_and_hint():
    m = mail("t", "a@b.com", "x | y\nz", labels={"IMPORTANT", "CATEGORY_PROMOTIONS"}, bulk=True)
    line = g.ai_lines([m])
    assert line.count("|") == 3 and "\n" not in line
    assert "bulk" in line and "gmail:important" in line and "gmail:promotions" in line


def test_ai_classify_maps_ids_and_drops_bad_answers(cfg, monkeypatch):
    monkeypatch.setattr(g, "AI_CHUNK", 2)
    mails = [mail(f"t{i}", f"p{i}@x.com") for i in range(5)]
    calls = []

    def runner(system, schema, lines, model):
        calls.append(lines)
        n = len(lines.splitlines())
        labels = [{"id": str(i), "tab": "News"} for i in range(n)]
        labels.append({"id": "0", "tab": "Not a tab"})   # ignored
        labels.append({"id": "99", "tab": "Jobs"})       # ignored
        return {"labels": labels}

    seen = []
    got, errors = g.ai_classify(mails, cfg, "claude-cli", runner=runner, on_chunk=seen.append)
    assert len(calls) == 3                               # chunked 2 + 2 + 1
    assert got == {f"t{i}": "News" for i in range(5)} and errors == []
    assert len(seen) == 3                                # progress per chunk


def test_ai_classify_keeps_good_chunks_when_one_fails(cfg, monkeypatch):
    monkeypatch.setattr(g, "AI_CHUNK", 2)
    mails = [mail(f"t{i}", f"p{i}@x.com") for i in range(4)]

    def runner(system, schema, lines, model):
        if "p0@" in lines:
            raise RuntimeError("boom")
        return {"labels": [{"id": str(i), "tab": "Jobs"} for i in range(len(lines.splitlines()))]}

    got, errors = g.ai_classify(mails, cfg, "claude-cli", runner=runner)
    assert got == {"t2": "Jobs", "t3": "Jobs"}
    assert errors == ["boom"]


def test_ai_cache_resets_when_config_changes(cfg, tmp_path, monkeypatch):
    monkeypatch.setattr(g, "AI_CACHE", tmp_path / "cache.json")
    g.save_ai_cache(cfg, {"t1": "News"})
    assert g.load_ai_cache(cfg) == {"t1": "News"}
    cfg.source += "\n# edited"
    assert g.load_ai_cache(cfg) == {}


def test_pick_backend(cfg, monkeypatch):
    cfg.ai = "off"
    assert g.pick_backend(cfg) is None
    cfg.ai = "anthropic-api"
    assert g.pick_backend(cfg) == "anthropic-api"
    cfg.ai = "auto"
    monkeypatch.setattr(g.shutil, "which", lambda _: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert g.pick_backend(cfg) is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert g.pick_backend(cfg) == "anthropic-api"


class _FakeSvc:
    def __init__(self, msg):
        self.msg = msg

    def users(self):
        return self

    def threads(self):
        return self

    def get(self, **_):
        return self

    def execute(self):
        return {"messages": [self.msg]}


def _b64(s):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def test_html_body_to_text():
    html = "<html><style>.x{}</style><p>Hello <b>[bold]Sam[/]</b></p><p>A &amp; B</p></html>"
    msg = {"payload": {"mimeType": "text/html", "headers": [], "body": {"data": _b64(html)}}}
    _, body = g.fetch_body(_FakeSvc(msg), "t")
    assert body == "Hello [bold]Sam[/]\n\nA & B"


def test_huge_body_is_truncated():
    html = "<table>" + "<tr><td>NIFTY</td><td>25,800</td></tr>" * 40000 + "</table>"
    msg = {"payload": {"mimeType": "text/html", "headers": [], "body": {"data": _b64(html)}}}
    _, body = g.fetch_body(_FakeSvc(msg), "t")
    assert len(body) < g.MAX_BODY_CHARS + 100
    assert body.endswith("open in Gmail)")


# ---------------------------------------------------------------- UI (headless)

import asyncio  # noqa: E402
from datetime import datetime  # noqa: E402


def _ui_app(monkeypatch, tmp_path, allow_changes):
    cfg_file = tmp_path / "c.toml"
    cfg_file.write_text(EXAMPLE.read_text().replace(
        "allow_changes = false", f"allow_changes = {str(allow_changes).lower()}"))
    monkeypatch.setenv("TABMAIL_CONFIG", str(cfg_file))
    monkeypatch.setattr(g, "AI_CACHE", tmp_path / "cache.json")
    calls = []
    monkeypatch.setattr(g, "fetch_body", lambda svc, tid: ("From: x", "body " + tid))
    def batch(kind):
        def f(svc, ids):
            calls.extend((kind, i) for i in ids)
            return []
        return f
    monkeypatch.setattr(g, "trash_threads", batch("trash"))
    monkeypatch.setattr(g, "untrash_threads", batch("untrash"))
    monkeypatch.setattr(g, "mark_thread_read", lambda svc, tid: calls.append(("read", tid)))
    mails = [g.Mail(f"t{i}", f"P{i}", f"p{i}@gmail.com", f"S{i}", datetime(2026, 11, 20 - i),
                    {"IMPORTANT", "UNREAD"}) for i in range(5)]

    class T(g.TabMail):
        def action_refresh(self):
            self.svc = object()
            self.backend = None
            self.fill(list(mails))

    return T(), calls


def _rows(app):
    t = app.query_one("#table0", g.DataTable)
    return [t.coordinate_to_cell_key((r, 0)).row_key.value for r in range(t.row_count)]


def test_trash_undo_and_mark_read(monkeypatch, tmp_path):
    app, calls = _ui_app(monkeypatch, tmp_path, allow_changes=True)

    async def run():
        async with app.run_test(size=(140, 30)) as p:
            await p.pause()
            await p.press("enter"); await p.pause(0.3)
            assert ("read", "t0") in calls                       # opening marks read
            assert not next(m for m in app.mails if m.thread_id == "t0").unread
            await p.press("down"); await p.pause(0.3)
            await p.press("D"); await p.pause(0.3)
            assert ("trash", "t1") in calls and _rows(app) == ["t0", "t2", "t3", "t4"]
            assert app.query_one("#table0", g.DataTable).cursor_row == 1   # place kept
            await p.press("u"); await p.pause(0.3)
            assert ("untrash", "t1") in calls and _rows(app) == ["t0", "t1", "t2", "t3", "t4"]

    asyncio.run(run())


def test_read_only_mode_changes_nothing(monkeypatch, tmp_path):
    app, calls = _ui_app(monkeypatch, tmp_path, allow_changes=False)

    async def run():
        async with app.run_test(size=(140, 30)) as p:
            await p.pause()
            await p.press("enter"); await p.pause(0.3)
            await p.press("D"); await p.pause(0.3)
            assert calls == [] and _rows(app) == ["t0", "t1", "t2", "t3", "t4"]

    asyncio.run(run())


def test_scope_choice(monkeypatch, tmp_path):
    # a read-only token is not enough once allow_changes is on
    monkeypatch.setattr(g, "TOKEN_FILE", tmp_path / "token.json")
    monkeypatch.setattr(g, "CLIENT_SECRET", tmp_path / "missing.json")
    (tmp_path / "token.json").write_text(
        '{"token": "x", "refresh_token": "r", "client_id": "c", "client_secret": "s", '
        '"scopes": ["https://www.googleapis.com/auth/gmail.readonly"], "expiry": "2999-01-01T00:00:00Z"}')
    assert g.gmail_creds(allow_changes=False).token == "x"
    with pytest.raises(SystemExit):          # needs a new sign-in -> no client secret here
        g.gmail_creds(allow_changes=True)


def test_shift_select_and_bulk_trash(monkeypatch, tmp_path):
    app, calls = _ui_app(monkeypatch, tmp_path, allow_changes=True)

    async def run():
        async with app.run_test(size=(140, 30)) as p:
            await p.pause()
            await p.press("enter"); await p.pause(0.3)          # panel open on t0
            await p.press("down"); await p.pause(0.3)           # t1 (marked read)
            calls.clear()
            await p.press("shift+down", "shift+down"); await p.pause(0.3)
            assert app.selected == {"t1", "t2", "t3"}
            assert not any(c[0] == "read" for c in calls)       # selecting doesn't open/mark read
            await p.press("shift+up"); await p.pause()
            assert app.selected == {"t1", "t2"}                 # shrinks back toward the anchor
            await p.press("escape"); await p.pause()
            assert app.selected == set()                        # Esc clears selection first
            await p.press("shift+down", "shift+down"); await p.pause()
            assert app.selected == {"t2", "t3", "t4"}
            await p.press("D"); await p.pause(0.3)
            assert sorted(c[1] for c in calls if c[0] == "trash") == ["t2", "t3", "t4"]
            assert _rows(app) == ["t0", "t1"] and app.selected == set()
            await p.press("u"); await p.pause(0.3)               # undo restores the whole batch
            assert _rows(app) == ["t0", "t1", "t2", "t3", "t4"]

    asyncio.run(run())


def test_batch_helper_reports_failures():
    class Req:
        def __init__(self, tid): self.tid = tid

    class Batch:
        def __init__(self, callback): self.cb, self.items = callback, []
        def add(self, req, request_id): self.items.append((request_id, req))
        def execute(self):
            for rid, req in self.items:
                self.cb(rid, {}, RuntimeError("x") if req.tid == "bad" else None)

    class Svc:
        batches = 0
        def new_batch_http_request(self, callback):
            Svc.batches += 1
            return Batch(callback)
        def users(self): return self
        def threads(self): return self
        def trash(self, userId, id): return Req(id)

    ids = [f"t{i}" for i in range(120)] + ["bad"]
    assert g.trash_threads(Svc(), ids) == ["bad"]
    assert Svc.batches == 3                                     # 50 + 50 + 21


def test_prompt_includes_corrections(cfg):
    ex = [{"from": "Cafe <hi@cafe.com>", "subject": "Your daily update", "tab": "Notifications",
           "note": "daily updates from this cafe"},
          {"from": "x <x@y.com>", "subject": "s", "tab": "Deleted tab", "note": ""}]
    p = g.ai_prompt(cfg, ex)
    assert "hi@cafe.com" in p and "-> Notifications" in p and "daily updates from this cafe" in p
    assert "Deleted tab" not in p                        # examples for removed tabs are skipped


def test_add_tab_appends_valid_toml(tmp_path, monkeypatch):
    c = tmp_path / "config.toml"
    c.write_text(EXAMPLE.read_text())
    monkeypatch.setenv("TABMAIL_CONFIG", str(c))
    g.add_tab_to_config('Shop "pings"', "Orders, deliveries & offers\nfrom shops")
    cfg = g.load_config(c)
    assert cfg.tabs[-1].name == 'Shop "pings"'
    assert cfg.tabs[-1].description == "Orders, deliveries & offers\nfrom shops"
    assert "# tabmail configuration" in c.read_text()   # comments kept


def test_move_dialog_teaches_ai_and_new_tab(monkeypatch, tmp_path):
    app, calls = _ui_app(monkeypatch, tmp_path, allow_changes=False)
    monkeypatch.setattr(g, "CORRECTIONS", tmp_path / "corrections.json")
    app.corrections = g.load_corrections()

    def tab_of(tid):
        return app.tab_for(next(m for m in app.mails if m.thread_id == tid))

    async def run():
        async with app.run_test(size=(140, 34)) as p:
            await p.pause()
            # move t0 to Jobs with a note
            await p.press("c"); await p.pause()
            dlg = app.screen
            assert isinstance(dlg, g.MoveDialog) and "Important" not in dlg.tabs
            ol = dlg.query_one(g.OptionList)
            ol.highlighted = dlg.tabs.index("Jobs"); await p.press("enter"); await p.pause()
            await p.press(*"recruiter"); await p.press("enter"); await p.pause(0.3)
            assert tab_of("t0") == "Jobs"
            saved = g.load_corrections()
            assert saved["overrides"]["t0"] == "Jobs" and saved["examples"][-1]["note"] == "recruiter"
            # select two and send them to a brand-new tab
            await p.press("shift+down"); await p.pause()
            await p.press("c"); await p.pause()
            dlg = app.screen
            ol = dlg.query_one(g.OptionList)
            ol.highlighted = ol.option_count - 1; await p.press("enter"); await p.pause()
            await p.press(*"Shop"); await p.press("enter"); await p.pause()
            await p.press(*"orders"); await p.press("enter"); await p.pause()
            await p.press("enter"); await p.pause(0.5)       # no note
            assert app.tabs[-1].name == "Shop"
            assert tab_of("t1") == "Shop" and tab_of("t2") == "Shop"
            tc = app.query_one(g.TabbedContent)
            assert str(tc.get_tab(f"tab{len(app.tabs) - 1}").label).startswith("Shop (2")

    asyncio.run(run())


def test_summary_prompt_and_input_limits(monkeypatch):
    assert "Action:" in g.summary_prompt(1) and "untrusted" in g.summary_prompt(1)
    assert "these 3 emails" in g.summary_prompt(3)
    one = g.summary_input([("From: a", "x" * (g.SUMMARY_CHARS_ONE + 50))])
    assert one.endswith("[…truncated]") and one.count("x") == g.SUMMARY_CHARS_ONE
    many = g.summary_input([("h", "y" * 5000), ("h", "short")])
    assert many.count("y") == g.SUMMARY_CHARS_EACH and "=== Email 2 ===" in many


def test_summarize_key(monkeypatch, tmp_path):
    app, calls = _ui_app(monkeypatch, tmp_path, allow_changes=True)
    seen = []

    def fake_runner(system, schema, text, model):
        seen.append(text)
        return {"summary": "Action: reply by Friday\n- point " + str(text.count("=== Email"))}

    monkeypatch.setattr(g, "_run_claude_cli", fake_runner)

    class T(type(app)):
        def action_refresh(self):
            super().action_refresh()
            self.backend = "claude-cli"

    app = T()
    body = lambda: str(app.query_one("#preview-body", g.Static).render())

    async def run():
        async with app.run_test(size=(140, 30)) as p:
            await p.pause()
            await p.press("s"); await p.pause(0.3)
            assert body() == "Action: reply by Friday\n- point 1"
            assert "body t0" in seen[0]
            assert not any(c[0] == "read" for c in calls)        # summarizing doesn't mark read
            await p.press("s"); await p.pause(0.3)
            assert len(seen) == 1                                # second press: remembered
            await p.press("shift+down", "shift+down"); await p.pause()
            await p.press("s"); await p.pause(0.3)
            assert body().endswith("point 3") and len(seen) == 2  # one call for the selection

    asyncio.run(run())


def test_summaries_can_be_turned_off(monkeypatch, tmp_path):
    app, _ = _ui_app(monkeypatch, tmp_path, allow_changes=False)
    app.cfg.summaries = False
    monkeypatch.setattr(g, "ai_summarize", lambda *a, **k: pytest.fail("AI called"))

    async def run():
        async with app.run_test(size=(140, 30)) as p:
            await p.pause()
            app.backend = "claude-cli"
            await p.press("s"); await p.pause(0.3)
            assert not app.query_one("#preview-pane").has_class("open")

    asyncio.run(run())


def test_arrows_do_not_load_mail(monkeypatch, tmp_path):
    app, calls = _ui_app(monkeypatch, tmp_path, allow_changes=True)
    fetched = []
    monkeypatch.setattr(g, "fetch_body", lambda svc, tid: fetched.append(tid) or ("h", "body " + tid))

    async def run():
        async with app.run_test(size=(140, 30)) as p:
            await p.pause()
            await p.press("enter"); await p.pause(0.3)
            assert fetched == ["t0"]
            await p.press("down", "down", "down", "up"); await p.pause(0.3)
            assert fetched == ["t0"] and [c for c in calls if c[0] == "read"] == [("read", "t0")]
            await p.press("enter"); await p.pause(0.3)
            assert fetched == ["t0", "t2"]                     # loads only on Enter

    asyncio.run(run())


# ---------------------------------------------------------------- IMAP (fake server)

import email.utils as _eu  # noqa: E402


class FakeImap:
    """Just enough of Gmail's IMAP (with X-GM extensions) for tabmail."""

    def __init__(self, msgs):
        self.msgs = msgs              # uid -> dict(thrid, labels, flags, date, raw, folder, cats)
        self.folder = None

    def list(self):
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"',
                      b'(\\All \\HasNoChildren) "/" "[Google Mail]/All Mail"',
                      b'(\\HasNoChildren \\Trash) "/" "[Google Mail]/Bin"']

    def select(self, name, readonly=False):
        self.folder = {'"[Google Mail]/All Mail"': "all", '"[Google Mail]/Bin"': "trash"}[name]
        return "OK", [b"1"]

    def _here(self):
        return {u: m for u, m in self.msgs.items() if m["folder"] == self.folder}

    def uid(self, cmd, *args):
        here = self._here()
        if cmd == "SEARCH":
            key, val = args
            if key == "X-GM-THRID":
                hits = [u for u, m in here.items() if m["thrid"] == int(val)]
            else:  # X-GM-RAW
                cat = val.split("category:")[1].strip('"') if "category:" in val else None
                hits = [u for u, m in here.items() if cat is None or cat in m["cats"]]
            return "OK", [" ".join(map(str, sorted(hits))).encode()]
        if cmd == "FETCH":
            out = []
            for u in map(int, args[0].split(",")):
                m = here[u]
                # real Gmail sends system labels as atoms (\Inbox) or quoted with
                # an escaped backslash ("\\Important"); send both forms
                labels = " ".join(
                    l if n % 2 == 0 else '"' + l.replace("\\", "\\\\") + '"'
                    for n, l in enumerate(m["labels"]))
                flags = " ".join(m["flags"])
                meta = (f'{u} (UID {u} X-GM-THRID {m["thrid"]} X-GM-LABELS ({labels}) '
                        f'FLAGS ({flags}) INTERNALDATE "{m["date"]}" BODY[] {{{len(m["raw"])}}}')
                out += [(meta.encode(), m["raw"]), b")"]
            return "OK", out
        if cmd == "STORE":
            for u in map(int, args[0].split(",")):
                self.msgs[u]["flags"].add("\\Seen")
            return "OK", [b""]
        if cmd == "MOVE":
            dest = "trash" if "Bin" in args[1] else "inbox-restored"
            for u in map(int, args[0].split(",")):
                self.msgs[u]["folder"] = "all" if dest != "trash" else "trash"
            return "OK", [b""]
        raise AssertionError(cmd)


def _raw(frm, subj, body, extra=""):
    return (f"From: {frm}\r\nSubject: {subj}\r\nDate: Mon, 24 Nov 2026 10:00:00 +0000\r\n{extra}"
            f"Content-Type: text/plain; charset=utf-8\r\n\r\n{body}\r\n").encode()


@pytest.fixture
def imap_account(monkeypatch):
    msgs = {
        1: dict(thrid=0x1A20, labels=["\\Inbox"], flags=set(), date="23-Nov-2026 09:00:00 +0000",
                raw=_raw("Priya <priya@gmail.com>", "Dinner?", "Free on Saturday?"),
                folder="all", cats=set()),
        2: dict(thrid=0x1A20, labels=["\\Inbox", "\\Important"], flags={"\\Seen"},
                date="24-Nov-2026 09:00:00 +0000",
                raw=_raw("Priya <priya@gmail.com>", "Re: Dinner?", "Great, 8pm!"),
                folder="all", cats=set()),
        3: dict(thrid=0x2B30, labels=["\\Inbox"], flags=set(), date="24-Nov-2026 08:00:00 +0000",
                raw=_raw("Shop <deals@shop.com>", "=?utf-8?q?50=25_off?=", "Sale!",
                         "List-Unsubscribe: <mailto:u@shop.com>\r\n"),
                folder="all", cats={"promotions"}),
    }
    fake = FakeImap(msgs)
    acct = g.ImapAccount("me@gmail.com", "pw")
    monkeypatch.setattr(acct, "_connect", lambda: fake)
    return acct, msgs


def test_imap_list_threads_labels_and_categories(imap_account):
    acct, _ = imap_account
    mails = g.fetch_mails(acct, "in:inbox newer_than:7d", 300)
    assert [m.thread_id for m in mails] == ["1a20", "2b30"]   # hex thread ids, newest first
    dinner, shop = mails
    assert dinner.subject == "Re: Dinner?"                     # newest message of the thread
    assert dinner.labels == {"INBOX", "IMPORTANT"}             # read, important
    assert shop.subject == "50% off"                           # RFC 2047 decoded
    assert shop.labels == {"INBOX", "UNREAD", "CATEGORY_PROMOTIONS"} and shop.bulk


def test_imap_body_mark_read_trash_undo(imap_account):
    acct, msgs = imap_account
    header, body = g.fetch_body(acct, "1a20")
    assert "Re: Dinner?" in header and "2 messages in thread" in header and body == "Great, 8pm!"
    assert "\\Seen" not in msgs[1]["flags"]                    # reading alone changes nothing
    g.mark_thread_read(acct, "1a20")
    assert "\\Seen" in msgs[1]["flags"] and "\\Seen" in msgs[2]["flags"]
    assert g.trash_threads(acct, ["2b30", "ffff"]) == ["ffff"]  # unknown thread reported
    assert msgs[3]["folder"] == "trash"
    assert [m.thread_id for m in g.fetch_mails(acct, "in:inbox", 300)] == ["1a20"]
    assert g.untrash_threads(acct, ["2b30"]) == [] and msgs[3]["folder"] == "all"


def test_imap_folder_names_are_discovered(imap_account):
    acct, _ = imap_account
    assert acct.folders(acct.conn()) == {"all": "[Google Mail]/All Mail", "trash": "[Google Mail]/Bin"}


def test_resolve_auth(cfg, monkeypatch, tmp_path):
    monkeypatch.setattr(g, "CLIENT_SECRET", tmp_path / "credentials.json")
    monkeypatch.setattr(g, "TOKEN_FILE", tmp_path / "token.json")
    monkeypatch.setattr(g, "imap_saved_login", lambda: None)
    assert g.resolve_auth(cfg) == "imap"                       # nothing set up: easy path
    (tmp_path / "credentials.json").write_text("{}")
    assert g.resolve_auth(cfg) == "google-api"
    monkeypatch.setattr(g, "imap_saved_login", lambda: ("a@gmail.com", "pw"))
    assert g.resolve_auth(cfg) == "imap"                       # a saved app password wins
    cfg.auth = "google-api"
    assert g.resolve_auth(cfg) == "google-api"                 # explicit setting wins


def test_imap_login_storage_falls_back_to_private_file(monkeypatch, tmp_path):
    import builtins
    real_import = builtins.__import__

    def no_keyring(name, *a, **k):
        if name == "keyring":
            raise ImportError("no keyring")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_keyring)
    monkeypatch.setattr(g, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(g, "IMAP_FALLBACK_FILE", tmp_path / "imap.json")
    monkeypatch.delenv("TABMAIL_IMAP_USER", raising=False)
    where = g.imap_save_login("a@gmail.com", "abcd")
    assert where.endswith("imap.json") and oct((tmp_path / "imap.json").stat().st_mode)[-3:] == "600"
    assert g.imap_saved_login() == ("a@gmail.com", "abcd")
    g.imap_forget_login()
    assert g.imap_saved_login() is None
