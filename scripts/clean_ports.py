import json
import os
import urllib.request

DATA_FILE = "data/games.json"
MIN_STARS = 100

def http_get_json(url, headers=None):
    req = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": "game-ports-tracker/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def get_stars(repo_url, token):
    try:
        parts = repo_url.rstrip("/").split("/")
        owner_repo = f"{parts[-2]}/{parts[-1]}"
        h = {"User-Agent": "game-ports-tracker/1.0", "Accept": "application/vnd.github+json"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        data = http_get_json(f"https://api.github.com/repos/{owner_repo}", h)
        return data.get("stargazers_count", 0)
    except Exception as e:
        print(f"   ⚠️ No se pudo consultar {repo_url}: {e}")
        return None  # None = no se pudo determinar, se conserva

def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    with open(DATA_FILE, encoding="utf-8") as f:
        games = json.load(f)

    removed_total = 0
    kept_total = 0

    for game in games:
        ports = game.get("ports", [])
        if not ports:
            continue

        kept = []
        for p in ports:
            stars = p.get("stars")
            if not isinstance(stars, int) or stars <= 0:
                stars = get_stars(p["repo"], token)
                if stars is not None:
                    p["stars"] = stars

            if stars is not None and stars < MIN_STARS:
                print(f"   🗑️ {game['title']} -> {p['name']} ({stars}⭐) eliminado")
                removed_total += 1
            else:
                if stars is not None:
                    p["stars"] = stars
                kept.append(p)
                kept_total += 1

        game["ports"] = kept

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=4)

    print(f"\n✅ Limpieza terminada: {removed_total} ports eliminados, {kept_total} conservados.")

if __name__ == "__main__":
    main()
