#!/usr/bin/env python3
"""
Generates self-hosted profile cards (stats, languages, projects) as SVG files
using only the Python standard library and the GitHub GraphQL API.

Usage (in GitHub Actions):  python .github/scripts/generate_stats.py
Local preview:              python .github/scripts/generate_stats.py --mock
Placeholders (first setup): python .github/scripts/generate_stats.py --placeholder
"""
import html, json, os, re, sys, urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
README = ROOT / "README.md"
FONT = "'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
GREEN, BLUE, BG, BORDER, TEXT, MUTED = "#3DDC84", "#4C8DF6", "#0d1117", "#262f45", "#e6edf3", "#9aa7c0"

QUERY = """
query($login:String!){
  user(login:$login){
    name login
    followers{totalCount}
    pullRequests{totalCount}
    issues{totalCount}
    contributionsCollection{
      totalCommitContributions
      contributionCalendar{totalContributions weeks{contributionDays{contributionCount date}}}
    }
    repositories(ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC, first:100,
                 orderBy:{field:PUSHED_AT,direction:DESC}){
      totalCount
      nodes{
        name description url stargazerCount forkCount isArchived
        primaryLanguage{name color}
        languages(first:10, orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}
      }
    }
    pinnedItems(first:6, types:REPOSITORY){
      nodes{... on Repository{
        name description url stargazerCount forkCount isArchived
        primaryLanguage{name color}
      }}
    }
  }
}
"""

def esc(s): return html.escape(str(s or ""), quote=True)

def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise SystemExit(f"GitHub API error: {payload['errors']}")
    return payload["data"]["user"]

def mock_user():
    days = [{"date": str(date.today() - timedelta(days=i)), "contributionCount": (i % 4 != 0) * 2}
            for i in range(365)]
    langs = lambda *a: {"edges": [{"size": s, "node": {"name": n, "color": c}} for n, s, c in a]}
    repo = lambda n, d, st, f, l, c: {"name": n, "description": d, "url": f"https://github.com/x/{n}",
        "stargazerCount": st, "forkCount": f, "isArchived": False, "primaryLanguage": {"name": l, "color": c},
        "languages": langs((l, 1000, c))}
    return {"name": "Izhar Malik", "login": "Izhamalik", "followers": {"totalCount": 42},
        "pullRequests": {"totalCount": 87}, "issues": {"totalCount": 19},
        "contributionsCollection": {"totalCommitContributions": 912,
            "contributionCalendar": {"totalContributions": 1010, "weeks": [{"contributionDays": days}]}},
        "repositories": {"totalCount": 31, "nodes": [
            {**repo("Sample-Compose-App", "A Jetpack Compose sample app showing MVVM, Hilt and Retrofit in a clean architecture.", 14, 3, "Kotlin", "#A97BFF"),
             "languages": langs(("Kotlin", 52000, "#A97BFF"), ("Java", 21000, "#b07219"), ("HTML", 6000, "#e34c26"), ("CSS", 4000, "#563d7c"), ("Shell", 2500, "#89e051"), ("Python", 1800, "#3572A5"), ("C", 700, "#555555"))}]},
        "pinnedItems": {"nodes": [
            repo("Sample-Compose-App", "A Jetpack Compose sample app showing MVVM, Hilt and Retrofit in a clean architecture.", 14, 3, "Kotlin", "#A97BFF"),
            repo("Legacy-Java-Utils", "Utility library used across older Android projects.", 3, 1, "Java", "#b07219"),
            repo("Portfolio", None, 0, 0, "HTML", "#e34c26"),
            repo("Firebase-Chat", "Realtime chat app built on Firebase.", 6, 2, "Kotlin", "#A97BFF")]}}

def card(w, h, inner, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">'
            f'<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="{GREEN}"/><stop offset="1" stop-color="{BLUE}"/></linearGradient></defs>'
            f'<style>text{{font-family:{FONT}}}</style>'
            f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="16" fill="{BG}" stroke="{BORDER}"/>{inner}</svg>')

def title(text):
    return (f'<text x="28" y="40" font-size="19" font-weight="700" fill="{TEXT}">{esc(text)}</text>'
            f'<rect x="28" y="51" width="36" height="3" rx="1.5" fill="url(#g)"/>')

def streaks(days):
    days = sorted(days, key=lambda d: d["date"])
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    cur, seq = 0, days[::-1]
    if seq and seq[0]["contributionCount"] == 0:
        seq = seq[1:]  # today may not have contributions yet
    for d in seq:
        if d["contributionCount"] > 0: cur += 1
        else: break
    return cur, longest

def fmt(n): return f"{n:,}"

def stats_svg(u):
    repos = u["repositories"]["nodes"]
    stars = sum(r["stargazerCount"] for r in repos)
    cc = u["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    cur, longest = streaks(days)
    rows = [("Stars earned", stars), ("Commits, last year", cc["totalCommitContributions"]),
            ("Pull requests", u["pullRequests"]["totalCount"]), ("Issues opened", u["issues"]["totalCount"]),
            ("Public repositories", u["repositories"]["totalCount"])]
    body = title(f"{(u['name'] or u['login']).split()[0]}'s GitHub stats")
    for i, (label, val) in enumerate(rows):
        y = 84 + i * 27
        body += (f'<circle cx="32" cy="{y-5}" r="3.5" fill="{GREEN if i % 2 == 0 else BLUE}"/>'
                 f'<text x="44" y="{y}" font-size="14" fill="{MUTED}">{esc(label)}</text>'
                 f'<text x="300" y="{y}" font-size="15" font-weight="700" fill="{TEXT}" text-anchor="end">{fmt(val)}</text>')
    r, circ = 44, 2 * 3.14159 * 44
    off = circ * (1 - min(cur, 30) / 30)
    body += (f'<circle cx="405" cy="108" r="{r}" fill="none" stroke="{BORDER}" stroke-width="8"/>'
             f'<circle cx="405" cy="108" r="{r}" fill="none" stroke="url(#g)" stroke-width="8" stroke-linecap="round" '
             f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{off:.1f}" transform="rotate(-90 405 108)"/>'
             f'<text x="405" y="116" font-size="28" font-weight="800" fill="{TEXT}" text-anchor="middle">{cur}</text>'
             f'<text x="405" y="176" font-size="13" fill="{MUTED}" text-anchor="middle">day streak</text>'
             f'<text x="405" y="194" font-size="12" fill="#6b7a99" text-anchor="middle">longest: {longest} days</text>')
    return card(495, 210, body, "GitHub stats")

def languages_svg(u):
    totals = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]
            t = totals.setdefault(n["name"], [0, n["color"] or "#8b949e"])
            t[0] += e["size"]
    total = sum(v[0] for v in totals.values()) or 1
    top = sorted(totals.items(), key=lambda kv: -kv[1][0])[:6]
    body = title("Most used languages")
    body += '<clipPath id="c"><rect x="28" y="70" width="439" height="12" rx="6"/></clipPath><g clip-path="url(#c)">'
    x = 28.0
    for name, (size, color) in top:
        w = 439 * size / total
        body += f'<rect x="{x:.1f}" y="70" width="{w:.1f}" height="12" fill="{color}"/>'
        x += w
    body += f'<rect x="{x:.1f}" y="70" width="{max(28+439-x,0):.1f}" height="12" fill="{BORDER}"/></g>'
    for i, (name, (size, color)) in enumerate(top):
        cx, cy = 28 + (i % 2) * 230, 114 + (i // 2) * 30
        body += (f'<circle cx="{cx+5}" cy="{cy-5}" r="5" fill="{color}"/>'
                 f'<text x="{cx+18}" y="{cy}" font-size="14" fill="{TEXT}">{esc(name)}</text>'
                 f'<text x="{cx+195}" y="{cy}" font-size="14" fill="{MUTED}" text-anchor="end">{100*size/total:.1f}%</text>')
    return card(495, 210, body, "Most used languages")

def wrap(text, width, lines):
    words, out, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width: cur = f"{cur} {w}".strip()
        else: out.append(cur); cur = w
    out.append(cur)
    if len(out) > lines:
        out = out[:lines]; out[-1] = out[-1][: width - 1].rstrip() + "…"
    return out

def project_svg(repo):
    name = repo["name"] if len(repo["name"]) <= 32 else repo["name"][:31] + "…"
    desc = repo["description"] or "No description yet."
    body = f'<text x="24" y="42" font-size="18" font-weight="700" fill="{BLUE}">{esc(name)}</text>'
    for i, line in enumerate(wrap(desc, 58, 2)):
        body += f'<text x="24" y="{72 + i*22}" font-size="14" fill="{MUTED}">{esc(line)}</text>'
    x = 24
    lang = repo.get("primaryLanguage")
    if lang:
        body += (f'<circle cx="{x+5}" cy="126" r="5" fill="{lang["color"] or "#8b949e"}"/>'
                 f'<text x="{x+16}" y="131" font-size="13" fill="{TEXT}">{esc(lang["name"])}</text>')
        x += 40 + 7 * len(lang["name"])
    body += (f'<text x="{x}" y="131" font-size="13" fill="{MUTED}">Stars {repo["stargazerCount"]}</text>'
             f'<text x="{x+70}" y="131" font-size="13" fill="{MUTED}">Forks {repo["forkCount"]}</text>')
    return card(480, 150, body, f"{repo['name']} repository")

def placeholder(text, w, h):
    return card(w, h, f'<text x="{w/2}" y="{h/2}" font-size="15" fill="{MUTED}" text-anchor="middle">{esc(text)}</text>'
                      f'<text x="{w/2}" y="{h/2+24}" font-size="12" fill="#6b7a99" text-anchor="middle">Run the "Update profile stats" workflow once</text>', text)

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def update_readme(block):
    text = README.read_text(encoding="utf-8")
    new = re.sub(r"(<!--PROJECTS:START-->).*?(<!--PROJECTS:END-->)", lambda m: f"{m.group(1)}\n{block}\n{m.group(2)}", text, flags=re.S)
    README.write_text(new, encoding="utf-8")

def main():
    if "--placeholder" in sys.argv:
        write(ASSETS / "stats.svg", placeholder("GitHub stats will appear here", 495, 210))
        write(ASSETS / "languages.svg", placeholder("Top languages will appear here", 495, 210))
        write(ASSETS / "projects" / "placeholder.svg", placeholder("Your projects will appear here", 480, 150))
        return
    if "--mock" in sys.argv:
        user = mock_user()
    else:
        user = fetch(os.environ.get("GH_LOGIN") or os.environ["GITHUB_REPOSITORY_OWNER"], os.environ["GITHUB_TOKEN"])
    write(ASSETS / "stats.svg", stats_svg(user))
    write(ASSETS / "languages.svg", languages_svg(user))

    repos = [r for r in user["pinnedItems"]["nodes"] if r and not r["isArchived"]]
    if not repos:  # fall back to the most-starred public repos
        repos = sorted([r for r in user["repositories"]["nodes"] if not r["isArchived"]], key=lambda r: -r["stargazerCount"])[:4]
    repos = repos[:4]
    for old in (ASSETS / "projects").glob("*.svg"): old.unlink()
    tags = []
    for r in repos:
        write(ASSETS / "projects" / f"{r['name']}.svg", project_svg(r))
        tags.append(f'<a href="{esc(r["url"])}"><img src="./assets/projects/{esc(r["name"])}.svg" width="49%" alt="{esc(r["name"])}"/></a>')
    if tags and "--mock" not in sys.argv:
        update_readme("\n".join(tags))

if __name__ == "__main__":
    main()
