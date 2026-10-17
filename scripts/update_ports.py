import json
import os
import re
import urllib.request
import urllib.parse
from datetime import date

DATA_FILE = "data/games.json"
MAX_TOTAL_PORTS = 5          # tope duro por juego
MIN_STARS = 100              # solo ports con al menos 100 estrellas
TODAY = date.today().isoformat()

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
    req = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": "game-ports-tracker/1.0"},
    )
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
    h = {
        "User-Agent": "game-ports-tracker/1.0",
        "Accept": "application/vnd.github+json",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h

def get_aliases(game_title):
    for known in KNOWN_GAMES:
        if known["title"].lower() == game_title.lower():
            return known["aliases"]
    aliases = [game_title.lower()]
    words = re.findall(r"\w+", game_title)
    if len(words) > 1:
        abbr = "".join(w[0] for w in words if len(w) > 2).lower()
        if len(abbr) >= 2:
            aliases.append(abbr)
    return aliases

def detect_based_on(repo):
    text = (
        repo["name"]
        + " "
        + (repo.get("description") or "")
        + " "
        + " ".join(repo.get("topics", []))
    ).lower()
    if "recomp" in text or "static recompilation" in text:
        return "recomp"
    if "decomp" in text:
        return "decomp"
    return ""

def looks_like_port(repo, alias):
    name = repo["name"].lower()
    desc = (repo.get("description") or "").lower()

    if re.search(SKIP_RE, name + " " + desc, re.IGNORECASE):
        return False

    if "port" not in name and "port" not in desc:
        return False

    if alias not in name and alias not in desc:
        return False

    return True

def get_existing_stars(port, token):
    """Si el port ya tiene 'stars', lo usa. Si no, lo consulta en GitHub."""
    if isinstance(port.get("stars"), int) and port["stars"] > 0:
        return port["stars"]
    repo_url = port.get("repo", "")
    if not repo_url:
        return 0
    try:
        # Convertir https://github.com/owner/repo -> owner/repo
        parts = repo_url.rstrip("/").split("/")
        owner_repo = f"{parts[-2]}/{parts[-1]}"
        data = http_get_json(f"https://api.github.com/repos/{owner_repo}", gh_headers(token))
        return data.get("stargazers_count", 0)
    except Exception:
        return 0

def make_port(repo):
    stars = repo.get("stargazers_count", 0)
    status = "playable" if stars > 500 else "in-development"
    return {
        "name": repo["name"],
        "repo": repo["html_url"].rstrip("/"),
        "based_on": detect_based_on(repo),
        "based_on_repo": "",
        "status": status,
        "stars": stars,
        "last_updated": TODAY,
    }

def add_or_replace_port(game, new_port, token):
    """Añade el port si hay espacio, o sustituye el de menos estrellas si el nuevo es mejor."""
    ports = game.setdefault("ports", [])

    # 1. Si ya existe (misma URL), no hacer nada
    existing_urls = {p["repo"].lower().rstrip("/") for p in ports}
    if new_port["repo"].lower().rstrip("/") in existing_urls:
        return False

    # 2. Si hay espacio, añadir
    if len(ports) < MAX_TOTAL_PORTS:
        ports.append(new_port)
        return True

    # 3. Si está lleno, buscar el de menos estrellas
    lowest = None
    lowest_stars = None
    for p in ports:
        s = get_existing_stars(p, token)
        if lowest_stars is None or s < lowest_stars:
            lowest = p
            lowest_stars = s

    # 4. Si el nuevo tiene más estrellas que el mínimo, sustituir
    if new_port["stars"] > lowest_stars:
        ports.remove(lowest)
        ports.append(new_port)
        return True

    return False

def search_ports_for_game(game, token):
    added = 0
    aliases = get_aliases(game["title"])

    for alias in aliases:
        q = urllib.parse.quote(f"{alias} port")
        url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=20"
        try:
            data = http_get_json(url, gh_headers(token))
        except Exception as e:
            print(f"[GitHub] Error buscando '{alias} port': {e}")
            continue

        for repo in data.get("items", []):
            # Filtro de estrellas mínimo
            if repo.get("stargazers_count", 0) < MIN_STARS:
                continue

            if not looks_like_port(repo, alias):
                continue

            new_port = make_port(repo)
            if add_or_replace_port(game, new_port, token):
                added += 1
                action = "añadido" if len(game["ports"]) < MAX_TOTAL_PORTS else "sustituido"
                print(f"   + {new_port['name']} ({new_port['stars']}⭐) [{new_port['based_on'] or '?'}] -> {new_port['repo']}")

    return added

def main():
    games = load_games()
    token = os.environ.get("GITHUB_TOKEN", "")
    total = 0

    for game in games:
        print(f"🔍 {game['title']}...")
        added = search_ports_for_game(game, token)
        if added == 0:
            print("   Sin novedades (ya tiene los mejores o no hay candidatos con 100+⭐)")
        total += added

    if total > 0:
        save_games(games)
        print(f"\n✅ TOTAL: {total} ports añadidos/sustituidos")
    else:
        print("\nℹ️ Sin novedades esta vez.")

if __name__ == "__main__":
    main()
