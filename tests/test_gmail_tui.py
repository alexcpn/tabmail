"""Offline tests: no Gmail, no AI calls.  Run:  uv run --with pytest pytest -q"""

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gmail_tui as g  # noqa: E402

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
    monkeypatch.setenv("GMAIL_TUI_CONFIG", str(cfg_file))
    monkeypatch.setattr(g, "AI_CACHE", tmp_path / "cache.json")
    calls = []
    monkeypatch.setattr(g, "fetch_body", lambda svc, tid: ("From: x", "body " + tid))
    monkeypatch.setattr(g, "trash_thread", lambda svc, tid: calls.append(("trash", tid)))
    monkeypatch.setattr(g, "untrash_thread", lambda svc, tid: calls.append(("untrash", tid)))
    monkeypatch.setattr(g, "mark_thread_read", lambda svc, tid: calls.append(("read", tid)))
    mails = [g.Mail(f"t{i}", f"P{i}", f"p{i}@gmail.com", f"S{i}", datetime(2026, 11, 20 - i),
                    {"IMPORTANT", "UNREAD"}) for i in range(3)]

    class T(g.GmailTUI):
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
            assert ("trash", "t1") in calls and _rows(app) == ["t0", "t2"]
            assert app.query_one("#table0", g.DataTable).cursor_row == 1   # place kept
            await p.press("u"); await p.pause(0.3)
            assert ("untrash", "t1") in calls and _rows(app) == ["t0", "t1", "t2"]

    asyncio.run(run())


def test_read_only_mode_changes_nothing(monkeypatch, tmp_path):
    app, calls = _ui_app(monkeypatch, tmp_path, allow_changes=False)

    async def run():
        async with app.run_test(size=(140, 30)) as p:
            await p.pause()
            await p.press("enter"); await p.pause(0.3)
            await p.press("D"); await p.pause(0.3)
            assert calls == [] and _rows(app) == ["t0", "t1", "t2"]

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
