import json
import os
import re
import urllib.request
import urllib.parse
from datetime import date

DATA_FILE = "data/games.json"
MAX_NEW_PER_RUN = 25
TODAY = date.today().isoformat()

CONSOLE_PATTERNS = [
    (r"\bwii\s*u\b", "Wii U"),
    (r"\bwii\b", "Wii"),
    (r"\bn64\b|nintendo\s*64|mario\s*64|zelda\s*64|ocarina|majora|goldeneye|perfect\s*dark|banjo|mario\s*kart\s*64", "N64"),
    (r"gamecube|game\s*cube|wind\s*waker|twilight\s*princess|metroid\s*prime|sunshine|pikmin|melee", "GameCube"),
    (r"\b3ds\b", "3DS"),
    (r"\bgba\b|game\s*boy\s*advance|poke(?:mon)?\s*(emerald|ruby|sapphire|firered|leafgreen)", "Game Boy Advance"),
    (r"\bgameboy\b|game\s*boy(?! advance)|poke(?:mon)?\s*(red|blue|yellow|gold|silver|crystal)", "GB"),
    (r"\bnds\b|\bds\b|poke(?:mon)?\s*(platinum|diamond|pearl|heartgold|soulsilver)", "DS"),
    (r"\bswitch\b", "Switch"),
    (r"\bpsx\b|\bps1\b|playstation\s*1", "PS1"),
    (r"\bps2\b|playstation\s*2|metal\s*gear|silent\s*hill|god\s*of\s*war", "PS2"),
    (r"\bps3\b|playstation\s*3", "PS3"),
    (r"\bpsp\b", "PSP"),
    (r"ps\s*vita|\bvita\b", "PS Vita"),
    (r"xbox\s*360", "Xbox 360"),
    (r"\bxbox\b", "Xbox"),
]

GITHUB_ORGS = ["zeldaret", "n64decomp", "doldecomp", "pret", "HarbourMasters", "Zelda64Recomp"]
REDDIT_SUBS = ["emulation", "EmuDev", "retrogaming", "SwitchHacks", "WiiUHacks"]
REPO_URL_RE = r"https://(?:github|gitlab)\.com/[^\s/)]+/[^\s/)]+"

def http_get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "game-ports-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def load_games():
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_games(games):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=4)

def known_urls(games):
    urls = set()
    for g in games:
        for k in ("decomp_repo", "recomp_repo"):
            if g.get(k):
                urls.add(g[k].lower().rstrip("/"))
    return urls

def guess_console(text):
    for pattern, name in CONSOLE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return name
    return ""

def guess_types(text):
    t = text.lower()
    return ("decomp" in t or "decompil" in t), ("recomp" in t or "recompil" in t)

def pretty_title(repo_name):
    return re.sub(r"[-_]+", " ", repo_name).strip().title()

def clean_repo_url(url):
    m = re.match(REPO_URL_RE, url)
    return m.group(0).rstrip("/.,;:") if m else None

def make_entry(title, console, has_d, has_r, url, sources):
    return {
        "title": title,
        "original_console": console,
        "status": "in-development",
        "has_decompilation": has_d,
        "decomp_repo": url if has_d else "",
        "has_recompilation": has_r,
        "recomp_repo": url if has_r else "",
        "last_updated": TODAY,
        "sources": sources,
        "auto": True
    }

def add_repo(known, new_entries, url, text, sources, force_decomp=False):
    if len(new_entries) >= MAX_NEW_PER_RUN:
        return
    repo_url = clean_repo_url(url)
    if not repo_url or repo_url.lower() in known:
        return
    console = guess_console(text)
    if not console:
        return
    has_d, has_r = guess_types(text)
    if force_decomp and not (has_d or has_r):
        has_d = True
    if not (has_d or has_r):
        return
    known.add(repo_url.lower())
    new_entries.append(make_entry(pretty_title(repo_url.rstrip("/").split("/")[-1]), console, has_d, has_r, repo_url, sources))

def gh_headers(token):
    h = {"User-Agent": "game-ports-tracker/1.0", "Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h

def search_github_orgs(token, known, new_entries):
    for org in GITHUB_ORGS:
        try:
            repos = http_get_json(f"https://api.github.com/orgs/{org}/repos?per_page=100", gh_headers(token))
        except Exception as e:
            print(f"[Orgs] Error con {org}: {e}")
            continue
        for repo in repos:
            text = f"{repo['name']} {repo.get('description') or ''} {' '.join(repo.get('topics', []))}"
            add_repo(known, new_entries, repo["html_url"], text, ["github-org", org], force_decomp=True)

def search_github(token, known, new_entries):
    for term in ("decomp", "recomp"):
        q = urllib.parse.quote(f"{term} in:name,description,topics")
        url = f"https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page=50"
        try:
            data = http_get_json(url, gh_headers(token))
        except Exception as e:
            print(f"[GitHub] Error buscando '{term}': {e}")
            continue
        for repo in data.get("items", []):
            text = f"{repo['name']} {repo.get('description') or ''} {' '.join(repo.get('topics', []))}"
            add_repo(known, new_entries, repo["html_url"], text, ["github"])

def search_gitlab(known, new_entries):
    for term in ("decomp", "recomp"):
        url = f"https://gitlab.com/api/v4/projects?search={term}&per_page=50&order_by=last_activity_at&sort=desc"
        try:
            data = http_get_json(url)
        except Exception as e:
            print(f"[GitLab] Error: {e}")
            continue
        for proj in data:
            text = f"{proj.get('name') or ''} {proj.get('description') or ''}"
            add_repo(known, new_entries, proj.get("web_url") or "", text, ["gitlab"])

def search_reddit(known, new_entries):
    for sub in REDDIT_SUBS:
        url = (f"https://www.reddit.com/r/{sub}/search.json?"
               f"q=decomp+OR+recomp&restrict_sr=on&sort=new&t=month&limit=50")
        try:
            data = http_get_json(url)
        except Exception as e:
            print(f"[Reddit] Error en r/{sub}: {e}")
            continue
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            text = f"{post.get('title') or ''} {post.get('selftext') or ''}"
            links = re.findall(REPO_URL_RE, text + " " + (post.get("url") or ""))
            for link in links:
                add_repo(known, new_entries, link, text, ["reddit", sub])

def search_hackernews(known, new_entries):
    for q in ("decomp", "recomp"):
        url = f"https://hn.algolia.com/api/v1/search_by_date?query={q}&tags=story&hitsPerPage=50"
        try:
            data = http_get_json(url)
        except Exception as e:
            print(f"[HN] Error: {e}")
            continue
        for hit in data.get("hits", []):
            text = f"{hit.get('title') or ''} {hit.get('story_text') or ''}"
            links = re.findall(REPO_URL_RE, text + " " + (hit.get("url") or ""))
            for link in links:
                add_repo(known, new_entries, link, text, ["hackernews"])

def main():
    games = load_games()
    known = known_urls(games)
    new_entries = []

    token = os.environ.get("GITHUB_TOKEN", "")
    search_github_orgs(token, known, new_entries)
    search_github(token, known, new_entries)
    search_gitlab(known, new_entries)
    search_reddit(known, new_entries)
    search_hackernews(known, new_entries)

    if new_entries:
        games.extend(new_entries)
        save_games(games)
        print(f"OK: {len(new_entries)} ports nuevos añadidos:")
        for e in new_entries:
            print(f"   - {e['title']} ({e['original_console']}) [{', '.join(e['sources'])}]")
    else:
        print("Sin novedades esta vez.")

if __name__ == "__main__":
    main()
