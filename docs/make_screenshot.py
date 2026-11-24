# /// script
# requires-python = ">=3.11"
# dependencies = ["textual>=0.80", "google-api-python-client>=2.100", "google-auth-oauthlib>=1.2", "anthropic>=0.70", "keyring>=24"]
# ///
"""Render docs/screenshot.svg from made-up demo mail (no real data, no Gmail
or AI calls).  Run from the repo root:  uv run docs/make_screenshot.py"""
import sys, asyncio, os
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["TABMAIL_CONFIG"] = str(ROOT / "config.example.toml")
sys.path.insert(0, str(ROOT))
import tabmail as g  # noqa: E402

now = datetime.now().replace(second=0, microsecond=0)
demo = [  # (tab, name, address, subject, minutes ago, unread)
    ("Important", "Priya Raman", "priya.raman@example.com", "Dinner on Saturday?", 25, True),
    ("Important", "City Power", "billing@citypower.example", "Your bill of $84.20 is due on 28 Nov", 140, True),
    ("Important", "Dan Okafor", "dan@example.org", "Re: draft slides for Thursday", 300, False),
    ("Important", "Acme Recruiting", "talent@acme.example", "Interview slot: please confirm a time", 60 * 20, False),
    ("Important", "Mom", "mom@example.net", "Photos from the trip", 60 * 30, False),
    ("Notifications", "ShopMart", "orders@shopmart.example", "Your order has shipped", 50, True),
    ("Notifications", "Bank Alerts", "alerts@bank.example", "Card transaction of $12.40", 95, False),
    ("Notifications", "CloudDrive", "no-reply@clouddrive.example", "New sign-in on Linux", 200, False),
    ("Jobs", "JobBoard", "alerts@jobboard.example", "Staff Engineer roles near you", 80, True),
    ("Jobs", "JobBoard", "alerts@jobboard.example", "5 new matches for 'AI architect'", 60 * 26, False),
    ("News", "The Morning Brief", "news@brief.example", "Markets steady ahead of rate decision", 35, False),
    ("News", "Dev Weekly", "hello@devweekly.example", "Issue 214: terminal UIs are back", 60 * 7, False),
    ("News", "Gadget Store", "deals@gadgets.example", "Black Friday: 40% off headphones", 60 * 9, False),
]
mails, tabs = [], {}
for n, (tab, name, addr, subj, mins, unread) in enumerate(demo):
    tid = f"demo{n:02d}"
    labels = {"INBOX"} | ({"UNREAD"} if unread else set())
    mails.append(g.Mail(tid, name, addr, subj, now - timedelta(minutes=mins), labels))
    tabs[tid] = tab
mails.sort(key=lambda m: m.when, reverse=True)

summary = ("Action: pay $84.20 by 28 Nov to avoid a $5 late fee.\n"
           "- Bill for October from City Power, account 55-1093.\n"
           "- 412 kWh used, up from 380 kWh last month.\n"
           "- Pay online, by autopay, or by phone.\n"
           "- Late payments after 28 Nov add a $5 fee.")

class Demo(g.TabMail):
    def action_refresh(self):
        self.svc, self.me = object(), "me@example.com"
        self.ai_tabs = dict(tabs)
        self.backend = "claude-cli"          # shows "AI: claude-cli (haiku)"; no AI is called
        self.fill(mails)

async def main():
    app = Demo()
    async with app.run_test(size=(150, 18)) as p:
        await p.pause()
        await p.press("down")                # cursor on the bill
        await p.pause()
        app.summaries["sum:demo01"] = summary
        await p.press("s")                   # summary panel (pre-filled, no AI call)
        await p.pause(0.5)
        app.save_screenshot(filename="screenshot.svg", path=str(ROOT / "docs"))
        print("tabs:", [str(app.query_one(g.TabbedContent).get_tab(f"tab{i}").label) for i in range(len(app.tabs))])
        print("panel head:", app.query_one("#preview-head", g.Static).render())
asyncio.run(main())
