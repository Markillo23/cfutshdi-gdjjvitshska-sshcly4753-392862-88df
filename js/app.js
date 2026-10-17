// ===== CONFIGURACIÓN =====
const PASSWORD = "miconsola2026";
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
            '<p style="text-align:center; grid-column:1/-1;">Error al cargar los datos.</p>';
    }
}

// ===== FILTRAR =====
function filterGames() {
    const search = document.getElementById('search').value.toLowerCase();
    const consoleFilter = document.getElementById('filter-console').value;
    const typeFilter = document.getElementById('filter-type').value;
    const statusFilter = document.getElementById('filter-status').value;

    const filtered = allGames.filter(game => {
        const matchSearch =
            game.title.toLowerCase().includes(search) ||
            game.original_console.toLowerCase().includes(search) ||
            (game.ports || []).some(p => p.name.toLowerCase().includes(search));

        const matchConsole = !consoleFilter || game.original_console === consoleFilter;

        let matchType = true;
        if (typeFilter === 'decomp') matchType = (game.ports || []).some(p => p.based_on === 'decomp');
        else if (typeFilter === 'recomp') matchType = (game.ports || []).some(p => p.based_on === 'recomp');
        else if (typeFilter === 'both') {
            const hasD = (game.ports || []).some(p => p.based_on === 'decomp');
            const hasR = (game.ports || []).some(p => p.based_on === 'recomp');
            matchType = hasD && hasR;
        }

        const matchStatus = !statusFilter || (game.ports || []).some(p => p.status === statusFilter);

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
        grid.innerHTML = '<p style="text-align:center; grid-column:1/-1; color:#666; padding:40px;">No se encontraron juegos. 🎮</p>';
        return;
    }

    grid.innerHTML = games.map(game => {
        const consoleClass = getConsoleClass(game.original_console);
        const portCount = (game.ports || []).length;

        return `
            <div class="game-card" onclick="toggleExpand(this)">
                <div class="card-header">
                    <h3>${game.title}</h3>
                    <span class="console-badge ${consoleClass}">${game.original_console}</span>
                </div>
                <div class="port-summary">
                    <span class="port-count">${portCount} port${portCount !== 1 ? 's' : ''}</span>
                    ${getPortTypeSummary(game.ports || [])}
                    <span class="expand-hint">▾</span>
                </div>
                <div class="ports-list" onclick="event.stopPropagation()">
                    ${portCount === 0
                        ? '<p class="no-ports">Sin ports disponibles todavía.</p>'
                        : game.ports.map(p => renderPort(p)).join('')
                    }
                </div>
            </div>
        `;
    }).join('');
}

function renderPort(port) {
    let basedOn = '';
    if (port.based_on === 'decomp') {
        basedOn = `<span class="based-on decomp">🔧 Decompilación</span>`;
        if (port.based_on_repo) {
            basedOn += ` <a href="${port.based_on_repo}" target="_blank" class="based-on-link">${truncateUrl(port.based_on_repo)}</a>`;
        }
    } else if (port.based_on === 'recomp') {
        basedOn = `<span class="based-on recomp">⚡ Recompilación</span>`;
        if (port.based_on_repo) {
            basedOn += ` <a href="${port.based_on_repo}" target="_blank" class="based-on-link">${truncateUrl(port.based_on_repo)}</a>`;
        }
    } else {
        basedOn = `<span class="based-on unknown">❓ Origen desconocido</span>`;
    }

    return `
        <div class="port-item">
            <div class="port-header">
                <strong>${port.name}</strong>
                <span class="status-badge ${getStatusClass(port.status)}">${getStatusText(port.status)}</span>
            </div>
            <div class="port-meta">${basedOn}</div>
            <a href="${port.repo}" target="_blank" class="repo-link">📦 ${truncateUrl(port.repo)}</a>
        </div>
    `;
}

// ===== EXPANDIR / COLAPSAR =====
function toggleExpand(card) {
    card.classList.toggle('expanded');
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

function getPortTypeSummary(ports) {
    const hasD = ports.some(p => p.based_on === 'decomp');
    const hasR = ports.some(p => p.based_on === 'recomp');
    let html = '';
    if (hasD) html += '<span class="mini-badge decomp">DECOMP</span>';
    if (hasR) html += '<span class="mini-badge recomp">RECOMP</span>';
    return html;
}

function truncateUrl(url) {
    try {
        const parts = url.replace('https://github.com/', '').replace('https://gitlab.com/', '').split('/');
        return parts.length >= 2 ? `${parts[0]}/${parts[1]}` : url;
    } catch {
        return url;
    }
}
