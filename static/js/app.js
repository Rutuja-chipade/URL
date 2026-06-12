/**
 * Shortify Pro v2.0 – Client-Side Application
 * Handles auth, URL shortening, dashboard, analytics,
 * + Advanced: WebSockets, password protection, geo-targeting
 */

const API_BASE = '';

// ─── State ───
let authToken = localStorage.getItem('shortify_token');
let currentUser = JSON.parse(localStorage.getItem('shortify_user') || 'null');
let dashboardWs = null;
let analyticsWs = null;

// ─── DOM Ready ───
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    updateNavAuth();
    
    // Initialize password validation if fields exist
    initPasswordValidation('regPassword');
    initPasswordValidation('newPassword');
});

/**
 * Live Password Validation
 */
function initPasswordValidation(fieldId) {
    const passwordInput = document.getElementById(fieldId);
    if (!passwordInput) return;

    const rules = {
        length: document.getElementById('rule-length'),
        upper: document.getElementById('rule-upper'),
        symbol: document.getElementById('rule-symbol')
    };

    passwordInput.addEventListener('input', () => {
        const val = passwordInput.value;
        
        // Length check
        const isLongEnough = val.length >= 6;
        rules.length.classList.toggle('valid', isLongEnough);
        rules.length.classList.toggle('invalid', !isLongEnough);

        // Uppercase check
        const hasUpper = /[A-Z]/.test(val);
        rules.upper.classList.toggle('valid', hasUpper);
        rules.upper.classList.toggle('invalid', !hasUpper);

        // Symbol check
        const hasSymbol = /[!@#$%^&*(),.?":{}|<>]/.test(val);
        rules.symbol.classList.toggle('valid', hasSymbol);
        rules.symbol.classList.toggle('invalid', !hasSymbol);
    });
}

// ═══════════════════════════════
//  THEME
// ═══════════════════════════════

function initTheme() {
    const saved = localStorage.getItem('shortify_theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeIcon(saved);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('shortify_theme', next);
    updateThemeIcon(next);
}

function updateThemeIcon(theme) {
    const btn = document.getElementById('themeToggle');
    if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
}

function togglePasswordVisibility(id) {
    const el = document.getElementById(id);
    if (el) {
        el.type = el.type === 'password' ? 'text' : 'password';
    }
}

// ═══════════════════════════════
//  AUTH
// ═══════════════════════════════

function updateNavAuth() {
    const authNav = document.getElementById('authNav');
    if (!authNav) return;

    if (authToken && currentUser) {
        const adminLink = currentUser.is_admin ? '<a href="/admin" class="nav-link" style="color:var(--danger)">👑 Admin</a>' : '';
        authNav.innerHTML = `
            ${adminLink}
            <a href="/shortener" class="nav-link">➕ Create Link</a>
            <a href="/dashboard" class="nav-link">📊 Dashboard</a>
            <span class="nav-link" style="cursor:default;">Hi, ${escapeHtml(currentUser.name)}</span>
            <button onclick="logout()" class="btn btn-secondary btn-sm">Logout</button>
        `;
    } else {
        authNav.innerHTML = `
            <a href="/admin-login" class="nav-link" style="color:var(--text-tertiary); font-size: 0.9rem;">👑 Admin Login</a>
            <a href="/login" class="nav-link">👤 User Login</a>
            <a href="/register" class="btn btn-primary btn-sm">Sign Up</a>
        `;
    }
}

function logout() {
    localStorage.removeItem('shortify_token');
    localStorage.removeItem('shortify_user');
    authToken = null;
    currentUser = null;
    if (dashboardWs) dashboardWs.close();
    window.location.href = '/';
}

async function handleRegister(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    setLoading(btn, true);

    const isAdmin = document.getElementById('regIsAdminToggle')?.checked;
    
    const data = {
        name: document.getElementById('regName').value.trim(),
        email: document.getElementById('regEmail').value.trim(),
        password: document.getElementById('regPassword').value,
    };

    if (isAdmin) {
        data.admin_secret = document.getElementById('regAdminSecret').value;
    }

    try {
        const endpoint = isAdmin ? '/api/auth/register-admin' : '/api/auth/register';
        const res = await apiPost(endpoint, data);
        
        if (!isAdmin) {
            localStorage.setItem('shortify_token', res.access_token);
            localStorage.setItem('shortify_user', JSON.stringify(res.user));
            authToken = res.access_token;
            currentUser = res.user;
            showToast('Account created successfully!', 'success');
            setTimeout(() => window.location.href = '/dashboard', 500);
        } else {
            showToast('Admin account created successfully! Please log in.', 'success');
            setTimeout(() => window.location.href = '/admin-login', 1500);
        }
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading(btn, false);
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    setLoading(btn, true);

    const data = {
        email: document.getElementById('loginEmail').value.trim(),
        password: document.getElementById('loginPassword').value,
    };

    try {
        const res = await apiPost('/api/auth/login', data);
        localStorage.setItem('shortify_token', res.access_token);
        localStorage.setItem('shortify_user', JSON.stringify(res.user));
        authToken = res.access_token;
        currentUser = res.user;
        showToast('Welcome back!', 'success');
        setTimeout(() => window.location.href = '/dashboard', 500);
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading(btn, false);
    }
}

async function handleAdminLogin(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    setLoading(btn, true);

    const data = {
        email: document.getElementById('loginEmail').value.trim(),
        password: document.getElementById('loginPassword').value,
    };

    try {
        const res = await apiPost('/api/auth/login', data);
        if (!res.user.is_admin) {
            throw new Error("Access Denied: You do not have administrator privileges.");
        }
        localStorage.setItem('shortify_token', res.access_token);
        localStorage.setItem('shortify_user', JSON.stringify(res.user));
        authToken = res.access_token;
        currentUser = res.user;
        showToast('Admin access granted!', 'success');
        setTimeout(() => window.location.href = '/admin', 500);
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading(btn, false);
    }
}


// ═══════════════════════════════
//  URL SHORTENING (with advanced options)
// ═══════════════════════════════

function toggleAdvancedOptions() {
    const panel = document.getElementById('advancedOptions');
    const btn = document.getElementById('advancedToggle');
    if (!panel) return;

    const visible = panel.style.display !== 'none';
    panel.style.display = visible ? 'none' : 'block';
    btn.innerHTML = visible
        ? '🛡️ Advanced Options ▾'
        : '🛡️ Advanced Options ▴';
}

function togglePasswordField() {
    const checked = document.getElementById('enablePassword')?.checked;
    const field = document.getElementById('passwordField');
    if (field) field.style.display = checked ? 'block' : 'none';
}

function toggleGeoFields() {
    const checked = document.getElementById('enableGeo')?.checked;
    const field = document.getElementById('geoFields');
    if (field) field.style.display = checked ? 'block' : 'none';
}

let geoCounter = 0;

function addGeoTarget() {
    geoCounter++;
    const container = document.getElementById('geoTargetsList');
    if (!container) return;

    const row = document.createElement('div');
    row.className = 'geo-target-row';
    row.id = `geoRow${geoCounter}`;
    row.innerHTML = `
        <input type="text" placeholder="Country (e.g. US)" class="geo-country" maxlength="2" style="width:80px; padding:8px 10px; border:2px solid var(--border-light); border-radius:var(--radius-sm); font-family:var(--font-sans); font-size:0.85rem; text-transform:uppercase; color:var(--text-primary); background:var(--bg-primary); outline:none;">
        <input type="url" placeholder="Redirect URL for this country" class="geo-url" style="flex:1; padding:8px 10px; border:2px solid var(--border-light); border-radius:var(--radius-sm); font-family:var(--font-sans); font-size:0.85rem; color:var(--text-primary); background:var(--bg-primary); outline:none;">
        <button type="button" onclick="document.getElementById('geoRow${geoCounter}').remove()" style="width:32px;height:32px;border:1px solid var(--border-light);background:var(--bg-secondary);border-radius:var(--radius-sm);cursor:pointer;font-size:0.85rem;color:var(--danger);display:flex;align-items:center;justify-content:center;">✕</button>
    `;
    container.appendChild(row);
}

function collectGeoTargets() {
    const rows = document.querySelectorAll('.geo-target-row');
    if (!rows.length) return null;

    const targets = {};
    let hasAny = false;
    rows.forEach(row => {
        const country = row.querySelector('.geo-country')?.value.trim().toUpperCase();
        const url = row.querySelector('.geo-url')?.value.trim();
        if (country && url) {
            targets[country] = url;
            hasAny = true;
        }
    });
    return hasAny ? targets : null;
}

async function handleShorten(e) {
    e.preventDefault();
    const btn = document.getElementById('shortenBtn');
    setLoading(btn, true);

    const data = {
        original_url: document.getElementById('urlInput').value.trim(),
    };

    const alias = document.getElementById('aliasInput')?.value.trim();
    if (alias) data.custom_alias = alias;

    const expiry = document.getElementById('expiryInput')?.value;
    if (expiry) data.expiry_days = parseInt(expiry);

    // Password protection
    const enablePw = document.getElementById('enablePassword')?.checked;
    if (enablePw) {
        const pw = document.getElementById('linkPassword')?.value;
        if (pw) data.password = pw;
    }

    // Tags
    const tagsVal = document.getElementById('tagsInput')?.value.trim();
    if (tagsVal) {
        data.tags = tagsVal.split(',').map(t => t.trim()).filter(t => t.length > 0);
    }

    // Geo-targeting
    const enableGeo = document.getElementById('enableGeo')?.checked;
    if (enableGeo) {
        const geoTargets = collectGeoTargets();
        if (geoTargets) data.geo_targets = geoTargets;
    }

    try {
        const res = await apiPost('/api/shorten', data);
        showResult(res);
        showToast('URL shortened successfully!', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading(btn, false);
    }
}

function showResult(data) {
    const card = document.getElementById('resultCard');
    if (!card) return;

    const urlText = document.getElementById('shortUrlText');
    if (urlText) {
        urlText.textContent = data.short_url;
        urlText.href = data.short_url;
    }

    // QR Code – show big and allow download
    const qrImg = document.getElementById('qrCode');
    const qrLabel = document.getElementById('qrLabel');
    const qrDownloadBtn = document.getElementById('qrDownloadBtn');
    if (qrImg && data.qr_code_url) {
        qrImg.src = data.qr_code_url;
        qrImg.style.display = 'block';
        if (qrLabel) qrLabel.style.display = 'block';
        if (qrDownloadBtn) {
            qrDownloadBtn.href = data.qr_code_url;
            qrDownloadBtn.style.display = 'inline-block';
        }
    }

    // Feature badges
    const pwBadge = document.getElementById('resultBadgePassword');
    const geoBadge = document.getElementById('resultBadgeGeo');
    if (pwBadge) pwBadge.style.display = data.is_password_protected ? 'inline-block' : 'none';
    if (geoBadge) geoBadge.style.display = data.has_geo_targets ? 'inline-block' : 'none';

    // Config buttons (shortener page only)
    const configPwBtn = document.getElementById('configPasswordBtn');
    const configGeoBtn = document.getElementById('configGeoBtn');
    if (configPwBtn) configPwBtn.href = `/url/settings/password/${data.short_code}`;
    if (configGeoBtn) configGeoBtn.href = `/url/settings/geo/${data.short_code}`;

    card.classList.add('visible');
    // On index page, the resultCard might be a hidden div instead of using CSS classes
    card.style.display = 'block';
    if (card.scrollIntoView) card.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function copyShortUrl() {
    const url = document.getElementById('shortUrlText').textContent;
    navigator.clipboard.writeText(url).then(() => {
        const btn = document.getElementById('copyBtn');
        btn.textContent = '✓ Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.textContent = '📋 Copy';
            btn.classList.remove('copied');
        }, 2000);
    });
}

// ═══════════════════════════════
//  DASHBOARD
// ═══════════════════════════════

async function loadDashboard(tag = null) {
    if (!authToken) {
        window.location.href = '/login';
        return;
    }

    try {
        const endpoint = tag ? `/api/user/urls?tag=${encodeURIComponent(tag)}` : '/api/user/urls';
        const res = await apiGet(endpoint);
        renderUrlTable(res.urls);
        renderStats(res.urls);
        if (!tag) populateTagFilter(res.urls);
    } catch (err) {
        if (err.message.includes('401') || err.message.includes('Authentication')) {
            logout();
            return;
        }
        showToast('Failed to load dashboard', 'error');
    }
}

function renderStats(urls) {
    const totalUrls = urls.length;
    const totalClicks = urls.reduce((sum, u) => sum + (u.total_clicks || 0), 0);
    const activeUrls = urls.filter(u => !u.expiry_date || new Date(u.expiry_date) > new Date()).length;

    animateCounter('statTotalUrls', totalUrls);
    animateCounter('statTotalClicks', totalClicks);
    animateCounter('statActiveUrls', activeUrls);
    animateCounter('statAvgClicks', totalUrls > 0 ? Math.round(totalClicks / totalUrls) : 0);
}

function animateCounter(elementId, targetValue) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const start = parseInt(el.textContent) || 0;
    const diff = targetValue - start;
    if (diff === 0) { el.textContent = targetValue; return; }

    const duration = 600;
    const startTime = performance.now();

    function step(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        el.textContent = Math.round(start + diff * eased).toLocaleString();
        if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

function renderUrlTable(urls) {
    const tbody = document.getElementById('urlTableBody');
    if (!tbody) return;

    if (urls.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-icon">🔗</div>
                        <h3>No URLs found</h3>
                        <p>Go to the <a href="/shortener">shortener page</a> to create a new link!</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = urls.map(url => `
        <tr>
            <td>
                <div class="url-original" title="${escapeHtml(url.original_url)}">
                    ${escapeHtml(url.original_url)}
                </div>
            </td>
            <td>
                <a href="${escapeHtml(url.short_url)}" target="_blank" class="url-short">
                    ${escapeHtml(url.short_code)}
                </a>
            </td>
            <td>
                <div style="display:flex; gap:4px; flex-wrap:wrap;">
                    ${(url.tags || []).map(tag => `<span class="tag-badge">${escapeHtml(tag)}</span>`).join('')}
                    ${(!url.tags || url.tags.length === 0) ? '<span style="color:var(--text-tertiary); font-size:0.8rem;">—</span>' : ''}
                </div>
            </td>
            <td class="url-clicks">${url.total_clicks || 0}</td>
            <td>
                <div style="display:flex; gap:4px; flex-wrap:wrap;">
                    ${url.is_password_protected ? '<span class="feature-badge badge-password" title="Password Protected">🔒</span>' : ''}
                    ${url.has_geo_targets ? '<span class="feature-badge badge-geo" title="Geo-Targeted">🌍</span>' : ''}
                    ${!url.is_password_protected && !url.has_geo_targets ? '<span style="color:var(--text-tertiary); font-size:0.8rem;">—</span>' : ''}
                </div>
            </td>
            <td class="url-date">${formatDate(url.created_at)}</td>
            <td>
                <div class="table-actions">
                    <button onclick="copyToClipboard('${escapeHtml(url.short_url)}')" title="Copy">📋</button>
                    <button onclick="viewAnalytics('${url.id}')" title="Analytics">📊</button>
                    <button onclick="deleteUrl('${url.id}')" class="delete-btn" title="Delete">🗑️</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function populateTagFilter(urls) {
    const select = document.getElementById('tagListFilter');
    if (!select) return;

    const allTags = new Set();
    urls.forEach(u => {
        if (u.tags) u.tags.forEach(t => allTags.add(t));
    });

    const currentVal = select.value;
    select.innerHTML = '<option value="">All Categories</option>' + 
        Array.from(allTags).sort().map(tag => `<option value="${escapeHtml(tag)}" ${tag === currentVal ? 'selected' : ''}>${escapeHtml(tag)}</option>`).join('');
}

function filterByTag(tag) {
    loadDashboard(tag);
}

async function deleteUrl(urlId) {
    if (!confirm('Are you sure you want to delete this URL? This cannot be undone.')) return;

    try {
        await apiDelete(`/api/url/${urlId}`);
        showToast('URL deleted', 'success');
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'info');
    });
}

// ═══════════════════════════════
//  REAL-TIME WEBSOCKET (Module 5)
// ═══════════════════════════════

function connectDashboardWebSocket() {
    const wsStatus = document.getElementById('wsStatus');
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/dashboard`;

    function connect() {
        dashboardWs = new WebSocket(wsUrl);

        dashboardWs.onopen = () => {
            if (wsStatus) {
                wsStatus.textContent = '● Live';
                wsStatus.className = 'ws-status ws-connected';
            }
            const pulse = document.getElementById('livePulse');
            if (pulse) pulse.className = 'live-pulse pulse-active';
        };

        dashboardWs.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'new_click') {
                    handleLiveClick(msg);
                }
            } catch (e) {}
        };

        dashboardWs.onclose = () => {
            if (wsStatus) {
                wsStatus.textContent = '● Reconnecting...';
                wsStatus.className = 'ws-status ws-disconnected';
            }
            // Auto reconnect after 3s
            setTimeout(connect, 3000);
        };

        dashboardWs.onerror = () => {
            dashboardWs.close();
        };
    }

    connect();
}

function handleLiveClick(msg) {
    const feed = document.getElementById('liveFeed');
    if (!feed) return;

    // Clear "waiting" message
    if (feed.querySelector('.empty-state')) {
        feed.innerHTML = '';
    }

    const data = msg.data;
    const item = document.createElement('div');
    item.className = 'live-feed-item';
    item.innerHTML = `
        <span class="live-dot"></span>
        <span>🌍 ${escapeHtml(data.location || 'Unknown')}</span>
        <span>💻 ${escapeHtml(data.device || 'Unknown')}</span>
        <span>🌐 ${escapeHtml(data.browser || 'Unknown')}</span>
        <span style="color:var(--text-tertiary); font-size:0.8rem;">just now</span>
    `;

    feed.insertBefore(item, feed.firstChild);

    // Limit to 20 items
    while (feed.children.length > 20) {
        feed.removeChild(feed.lastChild);
    }

    // Flash animation
    item.style.animation = 'slideUp 0.4s ease-out';

    // Update click counter
    const clickEl = document.getElementById('statTotalClicks');
    if (clickEl) {
        const current = parseInt(clickEl.textContent.replace(/,/g, '')) || 0;
        animateCounter('statTotalClicks', current + 1);
    }
}

function connectUrlWebSocket(urlId) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/analytics/${urlId}`;

    if (analyticsWs) analyticsWs.close();

    analyticsWs = new WebSocket(wsUrl);
    analyticsWs.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'new_click') {
                // Increment analytics counter in real-time
                const el = document.getElementById('analyticsTotalClicks');
                if (el) {
                    const v = parseInt(el.textContent) || 0;
                    el.textContent = v + 1;
                }
            }
        } catch (e) {}
    };
}

// ═══════════════════════════════
//  ANALYTICS
// ═══════════════════════════════

async function viewAnalytics(urlId) {
    const modal = document.getElementById('analyticsModal');
    if (!modal) return;

    modal.classList.add('visible');

    try {
        const data = await apiGet(`/api/analytics/${urlId}`);
        renderAnalytics(data, urlId);
        // Connect WebSocket for real-time updates
        connectUrlWebSocket(urlId);
    } catch (err) {
        showToast('Failed to load analytics', 'error');
        modal.classList.remove('visible');
    }
}

function closeAnalytics() {
    const modal = document.getElementById('analyticsModal');
    if (modal) modal.classList.remove('visible');
    if (analyticsWs) {
        analyticsWs.close();
        analyticsWs = null;
    }
}

function renderAnalytics(data, urlId) {
    document.getElementById('analyticsTotalClicks').textContent = data.total_clicks;
    document.getElementById('analyticsUniqueVisitors').textContent = data.unique_visitors;
    document.getElementById('analyticsShortCode').textContent = data.short_code;
    document.getElementById('analyticsOriginalUrl').textContent = truncate(data.original_url, 60);
    document.getElementById('analyticsOriginalUrl').title = data.original_url;

    const csvBtn = document.getElementById('downloadCsvBtn');
    if (csvBtn) {
        csvBtn.onclick = () => downloadCSV(urlId);
    }

    renderClickTrendChart(data.clicks_by_day);
    renderPieChart('browserChart', data.clicks_by_browser, 'Browsers');
    renderPieChart('deviceChart', data.clicks_by_device, 'Devices');
    renderBarChart('locationChart', data.clicks_by_location, 'Locations');
    renderRecentClicks(data.recent_clicks);
}

function renderClickTrendChart(dailyData) {
    const ctx = document.getElementById('clickTrendChart');
    if (!ctx) return;
    if (ctx._chart) ctx._chart.destroy();

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
    const textColor = isDark ? '#94a3b8' : '#64748b';

    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dailyData.map(d => d.date),
            datasets: [{
                label: 'Clicks',
                data: dailyData.map(d => d.clicks),
                borderColor: '#7c3aed',
                backgroundColor: 'rgba(124,58,237,0.1)',
                borderWidth: 2.5,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#7c3aed',
                pointRadius: 4,
                pointHoverRadius: 6,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: gridColor }, ticks: { color: textColor, font: { size: 11 } } },
                y: { beginAtZero: true, grid: { color: gridColor }, ticks: { color: textColor, font: { size: 11 }, stepSize: 1 } }
            }
        }
    });
    ctx._chart = chart;
}

function renderPieChart(canvasId, items, label) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    if (ctx._chart) ctx._chart.destroy();

    const colors = ['#7c3aed', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16'];

    const chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: items.map(i => i.label),
            datasets: [{
                data: items.map(i => i.count),
                backgroundColor: colors.slice(0, items.length),
                borderWidth: 0,
                hoverOffset: 8,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 16, usePointStyle: true, pointStyle: 'circle', font: { size: 12 },
                        color: document.documentElement.getAttribute('data-theme') === 'dark' ? '#94a3b8' : '#64748b',
                    }
                }
            }
        }
    });
    ctx._chart = chart;
}

function renderBarChart(canvasId, items, label) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    if (ctx._chart) ctx._chart.destroy();

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

    const chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: items.map(i => i.label),
            datasets: [{
                label: label,
                data: items.map(i => i.count),
                backgroundColor: 'rgba(124,58,237,0.7)',
                borderRadius: 6,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false, indexAxis: 'y',
            plugins: { legend: { display: false } },
            scales: {
                x: { beginAtZero: true, grid: { color: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }, ticks: { stepSize: 1, color: isDark ? '#94a3b8' : '#64748b' } },
                y: { grid: { display: false }, ticks: { color: isDark ? '#94a3b8' : '#64748b', font: { size: 12 } } }
            }
        }
    });
    ctx._chart = chart;
}

function renderRecentClicks(clicks) {
    const list = document.getElementById('recentClicksList');
    if (!list) return;

    if (clicks.length === 0) {
        list.innerHTML = '<div class="empty-state"><p>No clicks recorded yet</p></div>';
        return;
    }

    list.innerHTML = clicks.map(c => `
        <div class="click-item">
            <span>🌍 ${escapeHtml(c.location)}</span>
            <span>💻 ${escapeHtml(c.device)}</span>
            <span>🌐 ${escapeHtml(c.browser)}</span>
            <span>🕐 ${formatDateTime(c.timestamp)}</span>
        </div>
    `).join('');
}

async function downloadCSV(urlId) {
    try {
        const response = await fetch(`/api/analytics/${urlId}/csv`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (!response.ok) throw new Error('Failed to download');
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `analytics_${urlId}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('CSV downloaded!', 'success');
    } catch (err) {
        showToast('Failed to download CSV', 'error');
    }
}

// ═══════════════════════════════
//  API HELPERS
// ═══════════════════════════════

function _extractErrorMessage(json) {
    if (json.detail) {
        if (typeof json.detail === 'string') return json.detail;
        if (Array.isArray(json.detail)) {
            return json.detail.map(err => {
                const field = err.loc ? err.loc[err.loc.length - 1] : 'field';
                return `${field}: ${err.msg}`;
            }).join(', ');
        }
        return JSON.stringify(json.detail);
    }
    return 'Request failed';
}

function isTokenExpired(token) {
    if (!token) return true;
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        const payload = JSON.parse(jsonPayload);
        if (payload.exp) {
            const now = Math.floor(Date.now() / 1000);
            return now >= payload.exp;
        }
        return false;
    } catch (e) {
        return true;
    }
}

async function apiPost(endpoint, data) {
    if (authToken && isTokenExpired(authToken)) {
        showToast('Session expired. Logging out...', 'error');
        setTimeout(logout, 1500);
        throw new Error('Session expired');
    }
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST', headers,
        body: JSON.stringify(data),
    });

    const json = await res.json();
    if (!res.ok) throw new Error(_extractErrorMessage(json));
    return json;
}

async function apiGet(endpoint) {
    if (authToken && isTokenExpired(authToken)) {
        showToast('Session expired. Logging out...', 'error');
        setTimeout(logout, 1500);
        throw new Error('Session expired');
    }
    const headers = {};
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const res = await fetch(`${API_BASE}${endpoint}`, { headers });
    const json = await res.json();
    if (!res.ok) throw new Error(_extractErrorMessage(json));
    return json;
}

async function apiDelete(endpoint) {
    if (authToken && isTokenExpired(authToken)) {
        showToast('Session expired. Logging out...', 'error');
        setTimeout(logout, 1500);
        throw new Error('Session expired');
    }
    const headers = {};
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const res = await fetch(`${API_BASE}${endpoint}`, { method: 'DELETE', headers });
    const json = await res.json();
    if (!res.ok) throw new Error(_extractErrorMessage(json));
    return json;
}

// ═══════════════════════════════
//  UI HELPERS
// ═══════════════════════════════

function setLoading(btn, loading) {
    if (!btn) return;
    if (loading) { btn.classList.add('loading'); btn.disabled = true; }
    else { btn.classList.remove('loading'); btn.disabled = false; }
}

function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${icons[type] || ''}</span><span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(80px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function truncate(text, maxLen) {
    if (!text) return '';
    return text.length > maxLen ? text.substring(0, maxLen) + '...' : text;
}

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', {
        month: 'short', day: 'numeric',
    });
}

// ═══════════════════════════════
//  ADMIN PANEL LOGIC
// ═══════════════════════════════

async function loadAdminDashboard() {
    if (!authToken || !currentUser?.is_admin) {
        window.location.href = '/dashboard';
        return;
    }
    
    try {
        const stats = await apiGet('/api/admin/stats');
        animateCounter('adminTotalUsers', stats.total_users);
        animateCounter('adminTotalUrls', stats.total_urls);
        animateCounter('adminTotalClicks', stats.total_clicks);
        
        loadAdminUsers(); // load users by default
    } catch (err) {
        showToast('Failed to load admin dashboard', 'error');
    }
}

async function loadAdminUsers() {
    try {
        const users = await apiGet('/api/admin/users');
        const list = document.getElementById('adminUsersTableBody');
        if (!list) return;
        
        if (users.length === 0) {
            list.innerHTML = '<tr><td colspan="5">No users found.</td></tr>';
            return;
        }

        list.innerHTML = users.map(u => `
            <tr>
                <td style="font-weight:600">${escapeHtml(u.name)}</td>
                <td>${escapeHtml(u.email)}</td>
                <td>${u.is_admin ? '<span class="feature-badge badge-password" style="width:auto;padding:4px 8px;font-size:0.75rem">👑 Admin</span>' : '<span style="color:var(--text-secondary);font-size:0.8rem">User</span>'}</td>
                <td class="url-date">${formatDate(u.created_at)}</td>
                <td>
                    ${!u.is_admin ? `<button onclick="adminDeleteUser('${u.id}')" class="btn btn-danger btn-sm" style="font-size:0.75rem;padding:4px 8px">🗑️ Delete User</button>` : '<span style="color:var(--text-tertiary);font-size:0.8rem">—</span>'}
                </td>
            </tr>
        `).join('');
    } catch (err) {
        showToast('Failed to fetch users', 'error');
    }
}

async function loadAdminUrls() {
    try {
        const res = await apiGet('/api/admin/urls');
        const list = document.getElementById('adminUrlsTableBody');
        if (!list) return;
        
        if (res.urls.length === 0) {
            list.innerHTML = '<tr><td colspan="5">No URLs found.</td></tr>';
            return;
        }

        list.innerHTML = res.urls.map(url => `
            <tr>
                <td style="font-size:0.8rem; color:var(--text-tertiary)" title="${escapeHtml(url.user_id || 'Anonymous')}">
                    ${escapeHtml(truncate(url.user_id || 'Anon', 10))}
                </td>
                <td>
                    <div class="url-original" title="${escapeHtml(url.original_url)}">
                        ${escapeHtml(url.original_url)}
                    </div>
                </td>
                <td><a href="${escapeHtml(url.short_url)}" target="_blank" class="url-short">${escapeHtml(url.short_code)}</a></td>
                <td class="url-clicks" style="font-size:0.9rem">${url.total_clicks || 0}</td>
                <td>
                    <button onclick="adminDeleteUrl('${url.id}')" class="btn btn-danger btn-sm" style="font-size:0.75rem;padding:4px 8px">🗑️ Delete Link</button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        showToast('Failed to fetch URLs', 'error');
    }
}

async function adminDeleteUser(userId) {
    if (!confirm('EXTREME WARNING: Do you really want to delete this user and ALL their URLs and analytics? This cannot be undone.')) return;
    try {
        await apiDelete(`/api/admin/user/${userId}`);
        showToast('User entirely deleted!', 'success');
        loadAdminDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function adminDeleteUrl(urlId) {
    if (!confirm('WARNING: Are you sure you want to delete this URL globally?')) return;
    try {
        await apiDelete(`/api/admin/url/${urlId}`);
        showToast('URL deleted!', 'success');
        loadAdminUrls();
    } catch (err) {
        showToast(err.message, 'error');
    }
}
