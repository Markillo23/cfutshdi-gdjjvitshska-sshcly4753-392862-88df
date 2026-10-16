// ===== CONFIGURACIÓN =====
const PASSWORD = "miconsola2026"; // ← Cambia esta contraseña por la que quieras

let allGames = [];

// ===== LOGIN =====
function checkPassword() {
    const input = document.getElementById('password-input').value;
    if (input === PASSWORD) {
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('main-content').classList.remove('hidden');
        loadGames();
    } else {
        document.getElementById('login-error').classList.remove('hidden');
        document.getElementById('password-input').value = '';
    }
}

// Permitir Enter para login
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('password-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') checkPassword();
    });
});

// ===== CARGAR DATOS =====
async function loadGames() {
    try {
        const response = await fetch('data/games.json');
        allGames = await response.json();
        renderGames(allGames);
    } catch (error) {
        console.error('Error cargando datos:', error);
        document.getElementById('games-grid').innerHTML = 
            '<p style="text-align:center; grid-column:1/-1;">Error al cargar los datos. Asegúrate de que el archivo data/games.json exista.</p>';
    }
}

// ===== FILTRAR =====
function filterGames() {
    const search = document.getElementById('search').value.toLowerCase();
    const consoleFilter = document.getElementById('filter-console').value;
    const typeFilter = document.getElementById('filter-type').value;
    const statusFilter = document.getElementById('filter-status').value;

    let filtered = allGames.filter(game => {
        const matchSearch = game.title.toLowerCase().includes(search) || 
                           game.original_console.toLowerCase().includes(search);
        const matchConsole = !consoleFilter || game.original_console === consoleFilter;
        const matchStatus = !statusFilter || game.status === statusFilter;

        let matchType = true;
        if (typeFilter === 'decomp') matchType = game.has_decompilation && !game.has_recompilation;
        else if (typeFilter === 'recomp') matchType = game.has_recompilation && !game.has_decompilation;
        else if (typeFilter === 'both') matchType = game.has_decompilation && game.has_recompilation;

        return matchSearch && matchConsole && matchType && matchStatus;
    });

    renderGames(filtered);
}

// ===== RENDERIZAR =====
function renderGames(games) {
    const grid = document.getElementById('games-grid');
    const count = document.getElementById('game-count');
    count.textContent = `${games.length} juego${games.length !== 1 ? 's' : ''} encontrado${games.length !== 1 ? 's' : ''}`;

    if (games.length === 0) {
        grid.innerHTML = '<p style="text-align:center; grid-column:1/-1; color:#666; padding:40px;">No se encontraron juegos con esos filtros. 🎮</p>';
        return;
    }

    grid.innerHTML = games.map(game => {
        const consoleClass = getConsoleClass(game.original_console);
        const statusClass = getStatusClass(game.status);
        const statusText = getStatusText(game.status);

        let repoLinks = '';
        if (game.has_decompilation && game.decomp_repo) {
            repoLinks += `
                <a href="${game.decomp_repo}" target="_blank" class="repo-link">
                    <span class="repo-type type-decomp">DECOMP</span>
                    <span>${truncateUrl(game.decomp_repo)}</span>
                </a>`;
        }
        if (game.has_recompilation && game.recomp_repo) {
            repoLinks += `
                <a href="${game.recomp_repo}" target="_blank" class="repo-link">
                    <span class="repo-type type-recomp">RECOMP</span>
                    <span>${truncateUrl(game.recomp_repo)}</span>
                </a>`;
        }

        return `
            <div class="game-card">
                <div class="card-header">
                    <h3>${game.title}</h3>
                    <span class="console-badge ${consoleClass}">${game.original_console}</span>
                </div>
                <span class="status-badge ${statusClass}">${statusText}</span>
                <div class="repo-links">
                    ${repoLinks || '<span style="color:#666; font-size:13px;">Sin enlaces aún</span>'}
                </div>
                <div class="last-updated">📅 Actualizado: ${game.last_updated || 'N/A'}</div>
            </div>
        `;
    }).join('');
}

// ===== HELPERS =====
function getConsoleClass(console) {
    if (console.startsWith('PS') || console === 'PSP' || console === 'PS Vita') return 'badge-playstation';
    if (['Xbox', 'Xbox 360', 'Xbox One'].includes(console)) return 'badge-xbox';
    return 'badge-nintendo';
}

function getStatusClass(status) {
    if (status === 'complete') return 'status-complete';
    if (status === 'playable') return 'status-playable';
    return 'status-in-development';
}

function getStatusText(status) {
    if (status === 'complete') return '✅ Completo';
    if (status === 'playable') return '🟡 Jugable';
    return '🔴 En Desarrollo';
}

function truncateUrl(url) {
    try {
        const parts = url.replace('https://github.com/', '').split('/');
        return parts.length >= 2 ? `${parts[0]}/${parts[1]}` : url;
    } catch {
        return url;
    }
}
