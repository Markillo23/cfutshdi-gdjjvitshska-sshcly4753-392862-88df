import json
import os
import urllib.request

DATA_FILE = "data/games.json"
MIN_STARS = 100
MAX_TOTAL_PORTS = 5  # <-- NUEVO: límite máximo de ports por juego

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
        return None

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

        # 1. Rellenar estrellas si faltan
        for p in ports:
            stars = p.get("stars")
            if not isinstance(stars, int) or stars <= 0:
                stars = get_stars(p["repo"], token)
                if stars is not None:
                    p["stars"] = stars

        # 2. Filtrar los que no llegan al mínimo de estrellas
        valid_ports = [p for p in ports if p.get("stars") is not None and p["stars"] >= MIN_STARS]
        
        # Contar cuántos se eliminan por no llegar a las estrellas
        removed_by_stars = len(ports) - len(valid_ports)
        removed_total += removed_by_stars

        # 3. Ordenar de mayor a menor estrellas y cortar a los 5 mejores
        valid_ports.sort(key=lambda x: x.get("stars", 0), reverse=True)
        final_ports = valid_ports[:MAX_TOTAL_PORTS]
        
        # Contar cuántos se eliminan por el límite de 5
        removed_by_limit = len(valid_ports) - len(final_ports)
        removed_total += removed_by_limit

        # Imprimir qué se borra para tener control
        for p in ports:
            if p not in final_ports:
                print(f"   🗑️ {game['title']} -> {p['name']} ({p.get('stars', 0)}⭐) eliminado")

        game["ports"] = final_ports
        kept_total += len(final_ports)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=4)

    print(f"\n✅ Limpieza terminada: {removed_total} ports eliminados, {kept_total} conservados.")

if __name__ == "__main__":
    main()
