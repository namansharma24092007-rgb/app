"""Striker United Football Academy - FastAPI backend.
Run:  python app.py   (or: uvicorn app:app --host 0.0.0.0 --port 8000)
Single-file build: backend + all pages are inside this file.
Admin key (for viewing registrations): set env ADMIN_KEY, default 'change-me'.
"""
import os, re, sqlite3
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, EmailStr, field_validator

DB = os.getenv("DB_PATH", "academy.db")
ADMIN_KEY = os.getenv("ADMIN_KEY", "change-me")
app = FastAPI(title="Striker United Football Academy")


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def next_saturdays(n=4):
    d = date.today() + timedelta(days=1)
    out = []
    while len(out) < n:
        if d.weekday() == 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def init():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS registrations(
            id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT, email TEXT, phone TEXT,
            dob TEXT, position TEXT, foot TEXT, experience TEXT, trial_date TEXT,
            message TEXT, status TEXT DEFAULT 'pending', created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS matches(
            id INTEGER PRIMARY KEY AUTOINCREMENT, age_group TEXT, opponent TEXT,
            venue TEXT, kickoff TEXT, home INTEGER, score TEXT)""")
        if c.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 0:
            now = datetime.now().replace(minute=0, second=0, microsecond=0)
            seed = [
                ("U12", "Rapid FC Juniors", "Academy Ground A", now + timedelta(days=-9, hours=2), 1, "3 - 1"),
                ("U15", "City Blues Academy", "City Stadium", now + timedelta(days=-5), 0, "1 - 1"),
                ("U17", "Eagles Youth", "Academy Ground B", now + timedelta(days=-2), 1, "2 - 0"),
                ("U12", "Red Star Kids", "Academy Ground A", now + timedelta(days=2, hours=1), 1, None),
                ("U15", "Northside FC", "Northside Park", now + timedelta(days=4, hours=3), 0, None),
                ("U17", "Valley United", "Academy Ground B", now + timedelta(days=6, hours=4), 1, None),
                ("U15", "Eagles Youth", "Academy Ground A", now + timedelta(days=11), 1, None),
            ]
            c.executemany("INSERT INTO matches(age_group,opponent,venue,kickoff,home,score) VALUES(?,?,?,?,?,?)",
                          [(a, o, v, k.isoformat(), h, s) for a, o, v, k, h, s in seed])


class Registration(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    dob: date
    position: str
    foot: str
    experience: str
    trial_date: str
    message: Optional[str] = ""

    @field_validator("full_name")
    @classmethod
    def _name(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Enter your full name")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        digits = re.sub(r"\D", "", v)
        if not 10 <= len(digits) <= 13:
            raise ValueError("Enter a valid phone number")
        return v.strip()

    @field_validator("dob")
    @classmethod
    def _dob(cls, v):
        age = (date.today() - v).days // 365
        if not 6 <= age <= 25:
            raise ValueError("Players must be between 6 and 25 years old")
        return v

    @field_validator("position")
    @classmethod
    def _pos(cls, v):
        if v not in {"Goalkeeper", "Defender", "Midfielder", "Forward"}:
            raise ValueError("Choose a position")
        return v


@app.post("/api/register", status_code=201)
def register(r: Registration):
    if r.trial_date not in next_saturdays():
        raise HTTPException(400, "Pick one of the available trial dates")
    with db() as c:
        if c.execute("SELECT 1 FROM registrations WHERE email=? AND trial_date=?",
                     (r.email, r.trial_date)).fetchone():
            raise HTTPException(409, "This email is already registered for that trial date")
        cur = c.execute(
            """INSERT INTO registrations(full_name,email,phone,dob,position,foot,experience,
               trial_date,message,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (r.full_name, r.email, r.phone, r.dob.isoformat(), r.position, r.foot,
             r.experience, r.trial_date, r.message, datetime.now().isoformat()))
    return {"id": cur.lastrowid, "message": f"You're booked for the trial on {r.trial_date}. Check your email soon."}


@app.get("/api/trial-dates")
def trial_dates():
    return next_saturdays()


@app.get("/api/matches")
def matches(age_group: Optional[str] = None):
    q, args = "SELECT * FROM matches", []
    if age_group:
        q += " WHERE age_group=?"
        args.append(age_group)
    with db() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY kickoff", args)]


@app.get("/api/gallery")
def gallery():
    cats = ["Matches", "Training", "Events", "Trophies"]
    return [{"id": i, "category": cats[i % 4], "title": f"{cats[i % 4]} moment {i // 4 + 1}",
             "src": f"https://picsum.photos/seed/striker{i}/800/{600 + (i % 3) * 120}"}
            for i in range(12)]  # replace src with your own photos in /static/img


@app.get("/api/news")
def news():
    return [
        {"date": "Oct 2026", "title": "U17 squad wins district league opener", "text": "A 2-0 win at Academy Ground B puts the U17s top of the table."},
        {"date": "Oct 2026", "title": "Weekend trials now open", "text": "Book a Saturday slot below. Bring boots, shin guards and water."},
        {"date": "Sep 2026", "title": "Two players selected for state camp", "text": "Congratulations to our U15 midfielders on their state selection."},
    ]


@app.get("/api/admin/registrations")
def admin_regs(x_admin_key: str = Header(default="")):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(401, "Invalid admin key")
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM registrations ORDER BY id DESC")]



# ---------------- Frontend (HTML + Tailwind via CDN) ----------------
PAGES = {
    "index.html": r"""<!doctype html><html lang="en"><head><title>Striker United Football Academy</title><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Barlow:wght@400;500;600&display=swap" rel="stylesheet">
<script>tailwind.config={theme:{extend:{colors:{pitch:"#0e3b2c",turf:"#17573f",chalk:"#f4f6ef",flood:"#f0d23c",ink:"#14201b"},fontFamily:{display:["Barlow Condensed","sans-serif"],sans:["Barlow","sans-serif"]}}}}</script>
<style>html{scroll-behavior:smooth}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}:focus-visible{outline:2px solid #f0d23c;outline-offset:2px}</style></head>
<body class="bg-chalk text-ink font-sans"><div id="nav"></div>

<section class="bg-pitch text-chalk relative overflow-hidden">
  <svg class="absolute inset-0 w-full h-full opacity-20" viewBox="0 0 800 400" preserveAspectRatio="xMidYMid slice" fill="none" stroke="#f4f6ef" stroke-width="3" aria-hidden="true">
    <rect x="20" y="20" width="760" height="360"/><line x1="400" y1="20" x2="400" y2="380"/><circle cx="400" cy="200" r="60"/><rect x="20" y="110" width="110" height="180"/><rect x="670" y="110" width="110" height="180"/></svg>
  <div class="relative max-w-6xl mx-auto px-5 py-20 md:py-28 grid md:grid-cols-5 gap-10 items-end">
    <div class="md:col-span-3">
      <h1 class="font-display text-6xl md:text-8xl leading-[0.9] font-bold">Your next season starts with one trial.</h1>
      <p class="mt-6 text-lg max-w-md text-chalk/85">Professional coaching for players aged 6 to 25. Book a Saturday trial and train with our coaches.</p>
      <a href="#register" class="mt-8 inline-block bg-flood text-ink font-semibold px-7 py-3 rounded-full hover:bg-white transition">Book a trial</a>
    </div>
    <div class="md:col-span-2 bg-chalk text-ink rounded-xl p-5">
      <p class="font-semibold">Next match</p>
      <div id="nextMatch" class="mt-3 text-sm">Loading…</div>
      <a href="/matches.html" class="mt-4 inline-block text-sm font-semibold underline decoration-flood decoration-2 underline-offset-4">See all fixtures</a>
    </div>
  </div>
</section>

<section class="max-w-6xl mx-auto px-5 mt-20 grid md:grid-cols-3 gap-10">
  <div><h2 class="font-display text-4xl font-bold">Programs</h2><p class="mt-3 text-ink/75">Groups are split by age so every player trains at the right level.</p></div>
  <div class="md:col-span-2 grid sm:grid-cols-3 gap-4" id="programs"></div>
</section>

<section class="max-w-6xl mx-auto px-5 mt-20">
  <h2 class="font-display text-4xl font-bold">Weekly training timetable</h2>
  <div class="mt-6 overflow-x-auto"><table class="w-full min-w-[520px] text-sm text-left">
    <thead><tr class="border-b-2 border-ink"><th class="py-2">Group</th><th>Mon / Wed / Fri</th><th>Saturday</th></tr></thead>
    <tbody class="divide-y divide-ink/15">
      <tr><td class="py-3 font-semibold">U12</td><td>4:30 - 6:00 PM</td><td>7:00 - 9:00 AM</td></tr>
      <tr><td class="py-3 font-semibold">U15</td><td>5:00 - 6:30 PM</td><td>9:00 - 11:00 AM</td></tr>
      <tr><td class="py-3 font-semibold">U17 / Senior</td><td>6:00 - 8:00 AM</td><td>Match day</td></tr></tbody></table></div>
</section>

<section class="max-w-6xl mx-auto px-5 mt-20 grid md:grid-cols-3 gap-10">
  <div><h2 class="font-display text-4xl font-bold">Coaches</h2></div>
  <div class="md:col-span-2 grid sm:grid-cols-3 gap-6 text-sm">
    <div><p class="font-semibold text-base">Rohit Malik</p><p class="text-ink/70">Head coach, AFC B Licence</p></div>
    <div><p class="font-semibold text-base">Sandeep Yadav</p><p class="text-ink/70">Goalkeeping coach</p></div>
    <div><p class="font-semibold text-base">Neha Chauhan</p><p class="text-ink/70">Fitness &amp; conditioning</p></div></div>
</section>

<section class="max-w-6xl mx-auto px-5 mt-20">
  <h2 class="font-display text-4xl font-bold">Academy news</h2>
  <div id="news" class="mt-6 grid md:grid-cols-3 gap-8"></div>
</section>

<section id="register" class="bg-turf text-chalk mt-24 scroll-mt-16">
  <div class="max-w-6xl mx-auto px-5 py-16 grid md:grid-cols-5 gap-10">
    <div class="md:col-span-2">
      <h2 class="font-display text-5xl font-bold">Register for trials</h2>
      <p class="mt-4 text-chalk/85">Trials run on Saturdays. Bring boots, shin guards and water. We confirm your slot by email.</p>
    </div>
    <form id="regForm" class="md:col-span-3 grid sm:grid-cols-2 gap-4 text-ink" novalidate>
      <label class="text-chalk text-sm">Full name<input name="full_name" required class="mt-1 w-full rounded-md px-3 py-2 text-ink"></label>
      <label class="text-chalk text-sm">Email<input name="email" type="email" required class="mt-1 w-full rounded-md px-3 py-2 text-ink"></label>
      <label class="text-chalk text-sm">Phone<input name="phone" type="tel" required class="mt-1 w-full rounded-md px-3 py-2 text-ink"></label>
      <label class="text-chalk text-sm">Date of birth<input name="dob" type="date" required class="mt-1 w-full rounded-md px-3 py-2 text-ink"></label>
      <label class="text-chalk text-sm">Position<select name="position" required class="mt-1 w-full rounded-md px-3 py-2"><option value="">Choose</option><option>Goalkeeper</option><option>Defender</option><option>Midfielder</option><option>Forward</option></select></label>
      <label class="text-chalk text-sm">Preferred foot<select name="foot" class="mt-1 w-full rounded-md px-3 py-2"><option>Right</option><option>Left</option><option>Both</option></select></label>
      <label class="text-chalk text-sm">Experience<select name="experience" class="mt-1 w-full rounded-md px-3 py-2"><option>Beginner</option><option>School team</option><option>Club level</option><option>District / State</option></select></label>
      <label class="text-chalk text-sm">Trial date<select name="trial_date" id="trialDate" required class="mt-1 w-full rounded-md px-3 py-2"></select></label>
      <label class="text-chalk text-sm sm:col-span-2">Anything we should know? (optional)<textarea name="message" rows="2" class="mt-1 w-full rounded-md px-3 py-2"></textarea></label>
      <div class="sm:col-span-2 flex items-center gap-4">
        <button class="bg-flood text-ink font-semibold px-7 py-3 rounded-full hover:bg-white transition disabled:opacity-60">Register for trial</button>
        <p id="formMsg" role="status" class="text-sm"></p></div>
    </form>
  </div>
</section>

<div id="foot"></div><script src="/static/app.js"></script>
<script>
const get = u => fetch(u).then(r => r.json());
get("/api/matches").then(ms => {
  const n = ms.find(m => new Date(m.kickoff) > new Date());
  document.getElementById("nextMatch").innerHTML = n ? `<p class="font-display text-3xl font-bold">${n.age_group} vs ${n.opponent}</p><p>${fmtDate(n.kickoff)}, ${fmtTime(n.kickoff)}</p><p class="text-ink/70">${n.venue} (${n.home ? "Home" : "Away"})</p>` : "No matches scheduled.";
});
get("/api/news").then(n => document.getElementById("news").innerHTML = n.map(i => `<article><p class="text-sm text-ink/60">${i.date}</p><h3 class="font-semibold text-lg mt-1">${i.title}</h3><p class="mt-2 text-ink/75">${i.text}</p></article>`).join(""));
document.getElementById("programs").innerHTML = [["U12","Ages 6-12","Ball mastery, small-sided games"],["U15","Ages 13-15","Tactics, passing patterns, fitness"],["U17 / Senior","Ages 16-25","Match prep, scouting exposure"]].map(([a,b,c]) => `<div class="border-t-4 border-pitch pt-3"><p class="font-display text-2xl font-bold">${a}</p><p class="text-sm font-semibold">${b}</p><p class="text-sm text-ink/70 mt-1">${c}</p></div>`).join("");
get("/api/trial-dates").then(d => document.getElementById("trialDate").innerHTML = d.map(x => `<option value="${x}">${fmtDate(x)}, 8:00 AM</option>`).join(""));
document.getElementById("regForm").onsubmit = async e => {
  e.preventDefault();
  const f = e.target, msg = document.getElementById("formMsg"), btn = f.querySelector("button");
  btn.disabled = true; msg.textContent = "Sending…"; msg.className = "text-sm";
  try {
    const res = await fetch("/api/register", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(Object.fromEntries(new FormData(f))) });
    const data = await res.json();
    if (res.ok) { msg.textContent = data.message; msg.className = "text-sm text-flood font-semibold"; f.reset(); }
    else { msg.textContent = Array.isArray(data.detail) ? data.detail.map(d => d.msg.replace("Value error, ", "")).join(". ") : data.detail; msg.className = "text-sm text-red-200 font-semibold"; }
  } catch { msg.textContent = "Could not reach the server. Try again."; }
  btn.disabled = false;
};
</script></body></html>
""",
    "matches.html": r"""<!doctype html><html lang="en"><head><title>Matches - Striker United</title><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Barlow:wght@400;500;600&display=swap" rel="stylesheet">
<script>tailwind.config={theme:{extend:{colors:{pitch:"#0e3b2c",turf:"#17573f",chalk:"#f4f6ef",flood:"#f0d23c",ink:"#14201b"},fontFamily:{display:["Barlow Condensed","sans-serif"],sans:["Barlow","sans-serif"]}}}}</script>
<style>html{scroll-behavior:smooth}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}:focus-visible{outline:2px solid #f0d23c;outline-offset:2px}</style></head>
<body class="bg-chalk text-ink font-sans"><div id="nav"></div>
<main class="max-w-4xl mx-auto px-5 mt-14">
  <h1 class="font-display text-6xl font-bold">Matches &amp; timings</h1>
  <div class="mt-6 flex flex-wrap gap-2" id="filters"></div>
  <h2 class="font-display text-3xl font-bold mt-10">Upcoming</h2><div id="upcoming" class="mt-3 divide-y divide-ink/15 border-y border-ink/15"></div>
  <h2 class="font-display text-3xl font-bold mt-12">Results</h2><div id="results" class="mt-3 divide-y divide-ink/15 border-y border-ink/15"></div>
</main><div id="foot"></div><script src="/static/app.js"></script>
<script>
let group = "";
const row = m => { const d = new Date(m.kickoff), up = d > new Date(); return `<div class="py-4 grid grid-cols-[84px_1fr_auto] gap-4 items-center">
  <div><p class="font-display text-3xl leading-none font-bold">${d.getDate()}</p><p class="text-sm">${d.toLocaleDateString("en-IN",{month:"short",weekday:"short"})}</p></div>
  <div><p class="font-semibold">${m.age_group} ${m.home ? "vs" : "at"} ${m.opponent}</p><p class="text-sm text-ink/70">${m.venue} · ${m.home ? "Home" : "Away"}</p></div>
  <div class="text-right">${up ? `<p class="font-semibold">${fmtTime(m.kickoff)}</p><p class="text-xs text-ink/60">Kick-off</p>` : `<p class="font-display text-3xl font-bold">${m.score}</p>`}</div></div>`; };
async function load() {
  const ms = await (await fetch("/api/matches" + (group ? "?age_group=" + group : ""))).json();
  const now = new Date(), up = ms.filter(m => new Date(m.kickoff) > now), past = ms.filter(m => new Date(m.kickoff) <= now).reverse();
  document.getElementById("upcoming").innerHTML = up.map(row).join("") || '<p class="py-4 text-ink/60">No upcoming matches for this group.</p>';
  document.getElementById("results").innerHTML = past.map(row).join("") || '<p class="py-4 text-ink/60">No results yet.</p>';
  document.getElementById("filters").innerHTML = ["", "U12", "U15", "U17"].map(g => `<button data-g="${g}" class="px-4 py-1.5 rounded-full border text-sm font-medium ${g === group ? "bg-pitch text-chalk border-pitch" : "border-ink/30 hover:border-ink"}">${g || "All groups"}</button>`).join("");
  document.querySelectorAll("#filters button").forEach(b => b.onclick = () => { group = b.dataset.g; load(); });
}
load();
</script></body></html>
""",
    "gallery.html": r"""<!doctype html><html lang="en"><head><title>Gallery - Striker United</title><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Barlow:wght@400;500;600&display=swap" rel="stylesheet">
<script>tailwind.config={theme:{extend:{colors:{pitch:"#0e3b2c",turf:"#17573f",chalk:"#f4f6ef",flood:"#f0d23c",ink:"#14201b"},fontFamily:{display:["Barlow Condensed","sans-serif"],sans:["Barlow","sans-serif"]}}}}</script>
<style>html{scroll-behavior:smooth}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}:focus-visible{outline:2px solid #f0d23c;outline-offset:2px}</style></head>
<body class="bg-chalk text-ink font-sans"><div id="nav"></div>
<main class="max-w-6xl mx-auto px-5 mt-14">
  <h1 class="font-display text-6xl font-bold">Gallery</h1>
  <div class="mt-6 flex flex-wrap gap-2" id="filters"></div>
  <div id="grid" class="mt-8 columns-2 md:columns-3 gap-4"></div>
</main>
<div id="lb" class="hidden fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4" role="dialog" aria-label="Photo viewer">
  <button id="lbClose" class="absolute top-4 right-5 text-chalk text-3xl" aria-label="Close">×</button>
  <figure class="max-w-3xl"><img id="lbImg" class="max-h-[80vh] rounded" alt=""><figcaption id="lbCap" class="text-chalk mt-3 text-center"></figcaption></figure></div>
<div id="foot"></div><script src="/static/app.js"></script>
<script>
let all = [], cat = "All";
function render() {
  const items = all.filter(i => cat === "All" || i.category === cat);
  document.getElementById("grid").innerHTML = items.map(i => `<button data-id="${i.id}" class="block w-full mb-4 break-inside-avoid overflow-hidden rounded-lg"><img src="${i.src}" alt="${i.title}" loading="lazy" class="w-full hover:scale-105 transition duration-300"></button>`).join("");
  document.querySelectorAll("#grid button").forEach(b => b.onclick = () => { const i = all.find(x => x.id == b.dataset.id); lbImg.src = i.src; lbImg.alt = i.title; lbCap.textContent = i.title; lb.classList.remove("hidden"); });
  document.getElementById("filters").innerHTML = ["All", "Matches", "Training", "Events", "Trophies"].map(c => `<button data-c="${c}" class="px-4 py-1.5 rounded-full border text-sm font-medium ${c === cat ? "bg-pitch text-chalk border-pitch" : "border-ink/30 hover:border-ink"}">${c}</button>`).join("");
  document.querySelectorAll("#filters button").forEach(b => b.onclick = () => { cat = b.dataset.c; render(); });
}
lbClose.onclick = () => lb.classList.add("hidden");
lb.onclick = e => { if (e.target === lb) lb.classList.add("hidden"); };
document.onkeydown = e => { if (e.key === "Escape") lb.classList.add("hidden"); };
fetch("/api/gallery").then(r => r.json()).then(d => { all = d; render(); });
</script></body></html>
""",
}
APP_JS = r"""// Shared: Tailwind-friendly nav + footer, helpers
const NAV = [["/", "Home"], ["/matches.html", "Matches"], ["/gallery.html", "Gallery"], ["/#register", "Join trials"]];
const path = location.pathname === "/" ? "/" : location.pathname;
document.getElementById("nav").innerHTML = `
<header class="sticky top-0 z-40 bg-pitch/95 backdrop-blur text-chalk border-b border-chalk/15">
  <div class="max-w-6xl mx-auto px-5 h-16 flex items-center justify-between">
    <a href="/" class="font-display text-2xl tracking-wide flex items-center gap-2"><span class="inline-block w-5 h-5 rounded-full border-2 border-flood"></span>Striker United</a>
    <button id="menuBtn" class="md:hidden p-2 focus-visible:outline outline-2 outline-flood" aria-label="Menu">☰</button>
    <nav id="menu" class="hidden md:flex gap-7 text-sm font-medium">
      ${NAV.map(([h, t]) => `<a href="${h}" class="py-1 border-b-2 ${h === path ? "border-flood" : "border-transparent hover:border-chalk/50"}">${t}</a>`).join("")}
    </nav>
  </div>
  <nav id="mmenu" class="hidden md:hidden px-5 pb-4 flex flex-col gap-3 text-sm">${NAV.map(([h, t]) => `<a href="${h}">${t}</a>`).join("")}</nav>
</header>`;
document.getElementById("menuBtn").onclick = () => document.getElementById("mmenu").classList.toggle("hidden");
document.getElementById("foot").innerHTML = `
<footer class="bg-pitch text-chalk/80 mt-24"><div class="max-w-6xl mx-auto px-5 py-10 grid gap-6 md:grid-cols-3 text-sm">
  <div><p class="font-display text-2xl text-chalk">Striker United</p><p class="mt-2">Football academy for ages 6-25. Training since 2012.</p></div>
  <div><p class="font-semibold text-chalk">Visit</p><p class="mt-2">Academy Ground, Sector 4, Bahadurgarh, Haryana</p><p>Mon-Sat, 6:00-8:30 AM &amp; 4:30-7:00 PM</p></div>
  <div><p class="font-semibold text-chalk">Contact</p><p class="mt-2">info@strikerunited.example</p><p>+91 98765 43210</p></div>
</div></footer>`;
window.fmtDate = (iso) => new Date(iso).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
window.fmtTime = (iso) => new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
"""

init()


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGES["index.html"]


@app.get("/{name}.html", response_class=HTMLResponse)
def page(name: str):
    html = PAGES.get(f"{name}.html")
    if html is None:
        raise HTTPException(404, "Page not found")
    return html


@app.get("/static/app.js")
def app_js():
    return Response(APP_JS, media_type="application/javascript")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
