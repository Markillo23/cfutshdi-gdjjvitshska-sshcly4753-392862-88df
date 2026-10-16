import json
import os
import re
import urllib.request
import urllib.parse
from datetime import date

DATA_FILE = "data/games.json"
MAX_NEW_PER_RUN = 15
TODAY = date.today().isoformat()

# Patrones para detectar consola (orden importante)
CONSOLE_PATTERNS = [
    (r"\bwii\s*u\b", "Wii U"),
    (r"\bwii\b", "Wii"),
    (r"\bn64\b|nintendo\s*64|mario\s*64|zelda\s*64|ocarina|majora", "N64"),
    (r"gamecube|game\s*cube|wind\s*waker|twilight\s*princess|metroid\s*prime", "GameCube"),
    (r"\b3ds\b", "3DS"),
    (r"\bgba\b|game\s*boy\s*advance", "Game Boy Advance"),
    (r"\bswitch\b", "Switch"),
    (r"\bpsx\b|\bps1\b|playstation\s*1", "PS1"),
    (r"\bps2\b|playstation\s*2", "PS2"),
    (r"\bps3\b|playstation\s*3", "PS3"),
    (r"\bpsp\b", "PSP"),
    (r"ps\s*vita|\bvita\b", "PS Vita"),
    (r"xbox\s*360", "Xbox 360"),
    (r"\bxbox\b", "Xbox"),
]

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
    has_decomp = ("decomp" in t) or ("decompil" in t)
    has_recomp = ("recomp" in t) or ("recompil" in t)
    return has_decomp, has_recomp

def pretty_title(repo_name):
    name = re.sub(r"[-_]+", " ", repo_name)
    return name.strip().title()

def clean_repo_url(url):
    m = re.match(r"(https://github\.com/[^/\s]+/[^/\s]+)", url)
    return m.group(1).rstrip("/.") if m else None

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

def search_github(token, known, new_entries):
    headers = {
        "User-Agent": "game-ports-tracker/1.0",
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for term in ("decomp", "recomp"):
        q = urllib.parse.quote(f"{term} in:name,description,topics")
        url = f"https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page=50"
        try:
            data = http_get_json(url, headers)
        except Exception as e:
            print(f"[GitHub] Error buscando '{term}': {e}")
            continue
        for repo in data.get("items", []):
            if len(new_entries) >= MAX_NEW_PER_RUN:
                return
            text = f"{repo['name']} {repo.get('description') or ''} {' '.join(repo.get('topics', []))}"
            console = guess_console(text)
            if not console:
                continue
            has_d, has_r = guess_types(text)
            if not (has_d or has_r):
                continue
            repo_url = repo["html_url"].rstrip("/")
            if repo_url.lower() in known:
                continue
            known.add(repo_url.lower())
            new_entries.append(make_entry(pretty_title(repo["name"]), console, has_d, has_r, repo_url, ["github"]))

def search_reddit(known, new_entries):
    for sub in ("emulation", "EmuDev"):
        if len(new_entries) >= MAX_NEW_PER_RUN:
            return
        url = (f"https://www.reddit.com/r/{sub}/search.json?"
               f"q=decomp+OR+recomp&restrict_sr=on&sort=new&t=month&limit=50")
        try:
            data = http_get_json(url)
        except Exception as e:
            print(f"[Reddit] Error en r/{sub}: {e}")
            continue
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            text = f"{post.get('title', '')} {post.get('selftext', '')}"
            links = re.findall(r"https://github\.com/[^/\s]+/[^/\s]+", text + " " + post.get("url", ""))
            for link in links:
                if len(new_entries) >= MAX_NEW_PER_RUN:
                    return
                repo_url = clean_repo_url(link)
                if not repo_url or repo_url.lower() in known:
                    continue
                console = guess_console(text)
                has_d, has_r = guess_types(text)
                if not console or not (has_d or has_r):
                    continue
                known.add(repo_url.lower())
                new_entries.append(make_entry(pretty_title(repo_url.split("/")[-1]), console, has_d, has_r, repo_url, ["reddit", sub]))

def main():
    games = load_games()
    known = known_urls(games)
    new_entries = []

    token = os.environ.get("GITHUB_TOKEN", "")
    search_github(token, known, new_entries)
    search_reddit(known, new_entries)

    if new_entries:
        games.extend(new_entries)
        save_games(games)
        print(f"✅ {len(new_entries)} ports nuevos añadidos:")
        for e in new_entries:
            print(f"   - {e['title']} ({e['original_console']})")
    else:
        print("ℹ️ Sin novedades esta vez.")

if __name__ == "__main__":
    main()
