# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "textual>=0.80", "google-api-python-client>=2.100", "google-auth-oauthlib>=1.2",
#   "anthropic>=0.70", "keyring>=24", "cairosvg>=2.7", "pillow>=10",
# ]
# ///
"""Render docs/demo.gif: a short tour of the tabs, from made-up demo mail
(no real data, no Gmail or AI calls).  Run from the repo root:

    uv run docs/make_demo_gif.py
"""
import asyncio
import io
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
os.environ["TABMAIL_CONFIG"] = str(ROOT / "config.example.toml")
sys.path.insert(0, str(ROOT))
import tabmail as g  # noqa: E402

WIDTH = 1200          # GIF width in pixels
SIZE = (140, 18)      # terminal columns x rows

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
    ("Notifications", "Daily Grind Cafe", "hello@dailygrind.example", "Your daily update: 3 new menu items", 60 * 5, False),
    ("Notifications", "Metro Transit", "updates@metro.example", "Your monthly pass renews on 1 Dec", 60 * 22, False),
    ("Jobs", "JobBoard", "alerts@jobboard.example", "Staff Engineer roles near you", 80, True),
    ("Jobs", "JobBoard", "alerts@jobboard.example", "5 new matches for 'AI architect'", 60 * 26, False),
    ("Jobs", "Lena (Northwind)", "lena@northwind.example", "Quick chat about a platform role?", 60 * 40, True),
    ("News", "The Morning Brief", "news@brief.example", "Markets steady ahead of rate decision", 35, False),
    ("News", "Dev Weekly", "hello@devweekly.example", "Issue 214: terminal UIs are back", 60 * 7, False),
    ("Other", "City Library", "library@city.example", "Survey: how was your last visit?", 60 * 8, False),
    ("Other", "Neighbourhood Group", "group@neighbours.example", "Lost cat on Elm Street", 60 * 30, True),
]
mails, tabs = [], {}
for n, (tab, name, addr, subj, mins, unread) in enumerate(demo):
    tid = f"demo{n:02d}"
    labels = {"INBOX"} | ({"UNREAD"} if unread else set())
    mails.append(g.Mail(tid, name, addr, subj, now - timedelta(minutes=mins), labels))
    tabs[tid] = tab
mails.sort(key=lambda m: m.when, reverse=True)


class Demo(g.TabMail):
    def action_refresh(self):
        self.svc, self.me = object(), "me@example.com"
        self.ai_tabs = dict(tabs)
        self.backend = "claude-cli"   # header shows the AI backend; no AI is called
        self.fill(mails)


def frame(svg: str, caption: str) -> Image.Image:
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=WIDTH)
    shot = Image.open(io.BytesIO(png)).convert("RGB")
    bar = 56
    out = Image.new("RGB", (shot.width, shot.height + bar), (24, 24, 27))
    out.paste(shot, (0, 0))
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
    except OSError:
        font = ImageFont.load_default(26)
    w = draw.textlength(caption, font=font)
    draw.text(((out.width - w) / 2, shot.height + (bar - 30) / 2), caption,
              fill=(245, 245, 245), font=font)
    return out


async def main() -> None:
    app = Demo()
    shots: list[tuple[Image.Image, int]] = []  # (frame, milliseconds)
    async with app.run_test(size=SIZE) as pilot:
        async def snap(caption: str, ms: int) -> None:
            await pilot.pause(0.3)
            shots.append((frame(app.export_screenshot(), caption), ms))

        await snap("Important: mail from real people, or that needs you to act", 2600)
        for caption in ("Notifications: orders, bank alerts, sign-ins, daily updates",
                        "Jobs: job alerts and recruiters",
                        "News: newsletters and promotions",
                        "Other: everything else"):
            await pilot.press("right")
            await snap(caption, 2400)
        await pilot.press("right")  # back round to Important
        await snap("Each tab is one sentence of plain English; Claude Haiku does the sorting", 3200)

    out = ROOT / "docs" / "demo.gif"
    frames = [f for f, _ in shots]
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=[ms for _, ms in shots], loop=0, optimize=True)
    print(f"{out}  {len(frames)} frames  {out.stat().st_size // 1024} KB")


asyncio.run(main())
