import json
import os
import re
import urllib.request
import urllib.parse
from datetime import date

DATA_FILE = "data/games.json"
MAX_NEW_PORTS_PER_GAME = 5
TODAY = date.today().isoformat()

# Aliases por juego (para buscar ports en GitHub)
KNOWN_GAMES = [
    {"title": "Super Mario 64", "aliases": ["sm64", "mario 64", "super mario 64"]},
    {"title": "The Legend of Zelda: Ocarina of Time", "aliases": ["oot", "ocarina of time", "zelda oot"]},
    {"title": "The Legend of Zelda: Majora's Mask", "aliases": ["mm", "majora", "zelda majora"]},
    {"title": "Perfect Dark", "aliases": ["perfect dark"]},
    {"title": "Super Smash Bros. Melee", "aliases": ["melee", "ssbm", "smash melee"]},
    {"title": "Doom 64", "aliases": ["doom 64", "doom64"]},
    {"title": "Star Fox 64", "aliases": ["sf64", "star fox 64", "starfox 64"]},
    {"title": "Mario Kart 64", "aliases": ["mk64", "mario kart 64"]},
    {"title": "Paper Mario", "aliases": ["paper mario", "papermario"]},
    {"title": "Banjo-Kazooie", "aliases": ["banjo", "banjo kazooie"]},
    {"title": "Diddy Kong Racing", "aliases": ["dkr", "diddy kong racing"]},
    {"title": "GoldenEye 007", "aliases": ["goldeneye", "goldeneye 007"]},
]

SKIP_RE = r"(utils?\b|tools?\b|sdk\b|extractor\b|viewer\b|editor\b|scripts?\b|assets?\b|docs?\b|website\b|tests?\b|libs?\b|emulator\b|rom\s*hack\b|texture\s*pack\b)"

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

def gh_headers(token):
    h = {"User-Agent": "game-ports-tracker/1.0", "Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h

def get_aliases(game_title):
    for known in KNOWN_GAMES:
        if known["title"].lower() == game_title.lower():
            return known["aliases"]
    # Fallback: usar el título y su abreviatura
    aliases = [game_title.lower()]
    words = re.findall(r"\w+", game_title)
    if len(words) > 1:
        abbr = "".join(w[0] for w in words if len(w) > 2).lower()
        if len(abbr) >= 2:
            aliases.append(abbr)
    return aliases

def detect_based_on(repo):
    text = (repo["name"] + " " + (repo.get("description") or "") + " " + " ".join(repo.get("topics", []))).lower()
    if "recomp" in text or "static recompilation" in text:
        return "recomp"
    if "decomp" in text:
        return "decomp"
    return ""

def looks_like_port(repo, alias):
    name = repo["name"].lower()
    desc = (repo.get("description") or "").lower()

    # Excluir herramientas/emuladores
    if re.search(SKIP_RE, name + " " + desc, re.IGNORECASE):
        return False

    # Debe mencionar "port" en nombre o descripción
    if "port" not in name and "port" not in desc:
        return False

    # El alias debe aparecer en nombre o descripción (confirmar que es del juego correcto)
    if alias not in name and alias not in desc:
        return False

    return True

def make_port(repo):
    stars = repo.get("stargazers_count", 0)
    status = "playable" if stars > 100 else "in-development"
    return {
        "name": repo["name"],
        "repo": repo["html_url"].rstrip("/"),
        "based_on": detect_based_on(repo),
        "based_on_repo": "",
        "status": status,
        "last_updated": TODAY,
    }

def search_ports_for_game(game, token):
    known_repos = {p["repo"].lower().rstrip("/") for p in game.get("ports", [])}
    new_ports = []
    aliases = get_aliases(game["title"])

    for alias in aliases:
        q = urllib.parse.quote(f"{alias} port")
        url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=15"
        try:
            data = http_get_json(url, gh_headers(token))
        except Exception as e:
            print(f"[GitHub] Error buscando '{alias} port': {e}")
            continue

        for repo in data.get("items", []):
            if len(new_ports) >= MAX_NEW_PORTS_PER_GAME:
                break

            repo_url = repo["html_url"].rstrip("/").lower()
            if repo_url in known_repos:
                continue

            # Filtrar ruido: mínimo de estrellas
            if repo.get("stargazers_count", 0) < 5:
                continue

            if not looks_like_port(repo, alias):
                continue

            known_repos.add(repo_url)
            new_ports.append(make_port(repo))

    return new_ports

def main():
    games = load_games()
    token = os.environ.get("GITHUB_TOKEN", "")
    total_new = 0

    for game in games:
        new_ports = search_ports_for_game(game, token)
        if new_ports:
            if "ports" not in game:
                game["ports"] = []
            game["ports"].extend(new_ports)
            total_new += len(new_ports)
            print(f"✅ {game['title']}: +{len(new_ports)} port(s) nuevo(s)")
            for p in new_ports:
                print(f"   - {p['name']} [{p['based_on'] or 'origen desconocido'}] -> {p['repo']}")

    if total_new > 0:
        save_games(games)
        print(f"\nTOTAL: {total_new} ports nuevos añadidos")
    else:
        print("Sin novedades esta vez.")

if __name__ == "__main__":
    main()
