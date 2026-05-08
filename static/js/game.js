/**
 * Rıfkı (King) - Game Client
 * Real-time card game client using Socket.IO
 */

const ROOM_ID = window.location.pathname.split('/').pop();
const socket = io();

const SUIT_SYMBOLS = { hearts: '♥', diamonds: '♦', clubs: '♣', spades: '♠' };
const CONTRACT_INFO = {
    trump:     { icon: '👑', name: 'Trump (Koz)', desc: 'Win tricks', score: '+50/trick', cls: 'positive' },
    rifki:     { icon: '💀', name: 'Rıfkı', desc: 'Avoid K♥', score: '-320', cls: '' },
    girls:     { icon: '👸', name: 'Girls (Kız)', desc: 'Avoid Queens', score: '-100 each', cls: '' },
    boys:      { icon: '🤴', name: 'Boys (Erkek)', desc: 'Avoid K & J', score: '-60 each', cls: '' },
    hearts:    { icon: '♥️', name: 'Hearts (Kupa)', desc: 'Avoid Hearts', score: '-30 each', cls: '' },
    last_two:  { icon: '⏳', name: 'Last Two (Son İki)', desc: 'Avoid last 2 tricks', score: '-180 each', cls: '' },
    no_tricks: { icon: '🚫', name: 'No Tricks (El Almaz)', desc: 'Avoid all tricks', score: '-50/trick', cls: '' }
};

let mySeat = -1;
let gameState = null;
let trickPauseActive = false;
let lastCompletedTrick = null;
let trickHistory = [];

// ─── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const playerName = sessionStorage.getItem('rifki_player_name') || 'Player';
    socket.emit('join_game', { room_id: ROOM_ID, name: playerName });
    setupUI();
});

function setupUI() {
    document.getElementById('btn-scoreboard').addEventListener('click', () => {
        document.getElementById('scoreboard-modal').style.display = 'flex';
        socket.emit('get_scoreboard', { room_id: ROOM_ID });
    });
    document.getElementById('btn-close-scoreboard').addEventListener('click', () => {
        document.getElementById('scoreboard-modal').style.display = 'none';
    });
    document.getElementById('btn-next-round').addEventListener('click', () => {
        document.getElementById('round-end-modal').style.display = 'none';
        socket.emit('next_round', { room_id: ROOM_ID });
    });
    document.querySelectorAll('.suit-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('trump-modal').style.display = 'none';
            socket.emit('set_trump_suit', { room_id: ROOM_ID, suit: btn.dataset.suit });
        });
    });
    document.getElementById('btn-last-trick').addEventListener('click', () => showLastTrickModal());
    document.getElementById('btn-close-last-trick').addEventListener('click', () => {
        document.getElementById('last-trick-modal').style.display = 'none';
    });
}

// ─── Socket Events ──────────────────────────────────────────
socket.on('joined_game', (data) => { mySeat = data.seat; });
socket.on('game_started', () => { socket.emit('get_state', { room_id: ROOM_ID }); });

socket.on('game_state', (data) => {
    if (data.your_seat !== undefined && data.your_seat !== null) mySeat = data.your_seat;
    gameState = data;
    if (!trickPauseActive) renderGameState(data);
});

socket.on('round_started', (data) => {
    hideAllModals();
    trickHistory = [];
    lastCompletedTrick = null;
    updateLastTrickButton();
    showNotification(`Round ${data.round}/20 — ${data.declarer_name} declares`);
});

socket.on('choose_contract', (data) => showContractModal(data.available));
socket.on('waiting_for_contract', (data) => showNotification(`${data.declarer_name} is choosing...`));
socket.on('need_trump_suit', () => { document.getElementById('trump-modal').style.display = 'flex'; });

socket.on('contract_selected', (data) => {
    const info = CONTRACT_INFO[data.contract] || {};
    let label = info.name || data.contract;
    if (data.trump_suit) label += ` (${SUIT_SYMBOLS[data.trump_suit]})`;
    document.getElementById('contract-badge').textContent = label;
    showNotification(`${data.declarer_name} chose: ${label}`);
    hideAllModals();
});

socket.on('card_played', () => { if (!trickPauseActive) socket.emit('get_state', { room_id: ROOM_ID }); });

socket.on('trick_complete', (data) => {
    lastCompletedTrick = data.trick;
    trickHistory.push({...data.trick, winner_name: data.winner_name});
    updateLastTrickButton();
    trickPauseActive = true;
    renderCompletedTrick(data.trick);
    showNotification(`Trick ${data.trick_number} won by ${data.winner_name}`);
    setTimeout(() => {
        trickPauseActive = false;
        clearTrickSlots();
        socket.emit('get_state', { room_id: ROOM_ID });
    }, 3000);
});

socket.on('round_ended', (data) => {
    const delay = trickPauseActive ? 3500 : 500;
    setTimeout(() => {
        trickPauseActive = false;
        data.game_over ? showGameOver(data) : showRoundEnd(data);
        updateScoreboard(data.scoreboard);
    }, delay);
});

socket.on('misdeal', (data) => showMisdeal(data.reason));
socket.on('scoreboard_data', (data) => updateScoreboard(data.scoreboard, data.players));
socket.on('error', (data) => showNotification(`⚠️ ${data.message}`));

// ─── Rendering ──────────────────────────────────────────────

function renderGameState(state) {
    document.getElementById('round-badge').textContent = `Round ${state.round_number}/20`;
    if (state.current_contract) {
        const info = CONTRACT_INFO[state.current_contract] || {};
        let label = info.name || state.current_contract;
        if (state.trump_suit) label += ` ${SUIT_SYMBOLS[state.trump_suit]}`;
        document.getElementById('contract-badge').textContent = label;
    } else {
        document.getElementById('contract-badge').textContent = '—';
    }
    renderPlayers(state);
    renderTrick(state);
    renderPenaltyCards(state);
    if (mySeat >= 0 && state.players[mySeat]) renderHand(state.players[mySeat].hand, state);
}

function getDisplaySeat(actualSeat) { return (actualSeat - mySeat + 4) % 4; }

function renderPlayers(state) {
    for (let i = 0; i < 4; i++) {
        const dp = getDisplaySeat(i);
        const player = state.players[i];
        const nameEl = document.getElementById(`name-${dp}`);
        const scoreEl = document.getElementById(`score-${dp}`);
        const avatarEl = document.getElementById(`avatar-${dp}`);
        const areaEl = document.getElementById(`player-area-${dp}`);

        if (nameEl) nameEl.textContent = player.name + (i === state.declarer ? ' ⭐' : '');
        if (scoreEl) scoreEl.textContent = player.total_score;
        if (avatarEl) avatarEl.textContent = player.is_human ? '👤' : '🤖';
        if (areaEl) areaEl.classList.toggle('is-declarer', i === state.declarer);

        const turnEl = document.getElementById(`turn-${dp}`);
        if (turnEl) turnEl.classList.toggle('active', i === state.current_player);

        if (dp !== 0) {
            const backEl = document.getElementById(`cards-back-${dp}`);
            if (backEl) {
                backEl.innerHTML = '';
                for (let j = 0; j < Math.min(player.hand_count || 0, 13); j++) {
                    const cb = document.createElement('div');
                    cb.className = 'card-back';
                    backEl.appendChild(cb);
                }
            }
        }
    }
}

function renderPenaltyCards(state) {
    if (!state.penalty_cards) return;
    for (let i = 0; i < 4; i++) {
        const dp = getDisplaySeat(i);
        const container = document.getElementById(`penalty-cards-${dp}`);
        if (!container) continue;
        container.innerHTML = '';
        const cards = state.penalty_cards[i] || [];
        if (!cards.length) { container.style.display = 'none'; continue; }
        container.style.display = 'flex';
        cards.forEach(c => {
            const el = document.createElement('div');
            const isRed = c.suit === 'hearts' || c.suit === 'diamonds';
            el.className = `penalty-mini-card ${isRed ? 'red' : ''}`;
            el.textContent = `${c.rank_name}${SUIT_SYMBOLS[c.suit]}`;
            container.appendChild(el);
        });
    }
}

function renderHand(hand, state) {
    const container = document.getElementById('player-hand');
    container.innerHTML = '';
    if (!hand) return;
    const isMyTurn = state.current_player === mySeat && state.state === 'playing' && !trickPauseActive;
    const validCards = state.valid_cards || [];
    hand.forEach(cardData => {
        const cardEl = createCardElement(cardData);
        if (isMyTurn) {
            const isValid = validCards.some(v => v.suit === cardData.suit && v.rank === cardData.rank);
            cardEl.classList.add(isValid ? 'valid-card' : 'invalid-card');
            if (isValid) cardEl.addEventListener('click', () => playCard(cardData));
        }
        container.appendChild(cardEl);
    });
}

function renderTrick(state) {
    if (trickPauseActive) return;
    clearTrickSlots();
    if (!state.current_trick || !state.current_trick.cards) return;
    state.current_trick.cards.forEach(entry => {
        const dp = getDisplaySeat(entry.player_id);
        const slot = document.getElementById(`trick-slot-${dp}`);
        if (slot) { slot.innerHTML = ''; const c = createCardElement(entry.card); c.classList.add('played'); slot.appendChild(c); }
    });
    const infoEl = document.getElementById('trick-info');
    if (infoEl && state.tricks_played_count !== undefined) infoEl.textContent = `Trick ${state.tricks_played_count + 1}`;
}

function renderCompletedTrick(trick) {
    clearTrickSlots();
    if (!trick || !trick.cards) return;
    trick.cards.forEach(entry => {
        const dp = getDisplaySeat(entry.player_id);
        const slot = document.getElementById(`trick-slot-${dp}`);
        if (slot) {
            slot.innerHTML = '';
            const c = createCardElement(entry.card);
            c.classList.add('played');
            if (entry.player_id === trick.winner) c.classList.add('winner-card');
            slot.appendChild(c);
        }
    });
    const infoEl = document.getElementById('trick-info');
    if (infoEl) {
        const wn = gameState?.players[trick.winner]?.name || 'Winner';
        infoEl.innerHTML = `<span class="trick-winner-label">Won by ${wn}</span>`;
    }
}

function clearTrickSlots() {
    for (let i = 0; i < 4; i++) { const s = document.getElementById(`trick-slot-${i}`); if (s) s.innerHTML = ''; }
    const infoEl = document.getElementById('trick-info');
    if (infoEl) infoEl.textContent = '';
}

function createCardElement(cardData) {
    const el = document.createElement('div');
    const isRed = cardData.suit === 'hearts' || cardData.suit === 'diamonds';
    el.className = `card ${isRed ? 'red' : ''}`;
    const symbol = SUIT_SYMBOLS[cardData.suit] || '';
    const rank = cardData.rank_name || '';
    el.innerHTML = `<div class="card-corner">${rank}<br>${symbol}</div><div class="card-rank">${rank}</div><div class="card-suit">${symbol}</div><div class="card-corner-br">${rank}<br>${symbol}</div>`;
    el.dataset.suit = cardData.suit;
    el.dataset.rank = cardData.rank;
    return el;
}

// ─── Actions ────────────────────────────────────────────────
function playCard(cardData) { socket.emit('play_card', { room_id: ROOM_ID, card: { suit: cardData.suit, rank: cardData.rank } }); }
function selectContract(contract) { document.getElementById('contract-modal').style.display = 'none'; socket.emit('select_contract', { room_id: ROOM_ID, contract }); }

// ─── Last Trick ─────────────────────────────────────────────
function updateLastTrickButton() {
    const btn = document.getElementById('btn-last-trick');
    btn.style.display = 'flex';
    btn.style.opacity = trickHistory.length > 0 ? '1' : '0.35';
    btn.style.pointerEvents = trickHistory.length > 0 ? 'auto' : 'none';
}

function showLastTrickModal() {
    const container = document.getElementById('last-trick-content');
    container.innerHTML = '';
    if (!trickHistory.length) return;
    [...trickHistory].reverse().forEach((trick, idx) => {
        const trickNum = trickHistory.length - idx;
        let cardsHtml = '';
        trick.cards.forEach(entry => {
            const pName = gameState?.players[entry.player_id]?.name || `P${entry.player_id+1}`;
            const isRed = entry.card.suit === 'hearts' || entry.card.suit === 'diamonds';
            const isWinner = entry.player_id === trick.winner;
            cardsHtml += `<div class="lt-card-entry ${isWinner ? 'lt-winner' : ''}"><span class="lt-player">${pName}</span><span class="lt-card ${isRed ? 'lt-red' : ''}">${entry.card.rank_name}${SUIT_SYMBOLS[entry.card.suit]}</span></div>`;
        });
        const div = document.createElement('div');
        div.className = 'lt-trick-row';
        div.innerHTML = `<div class="lt-trick-header"><span class="lt-trick-num">Trick ${trickNum}</span><span class="lt-trick-winner">Won by ${trick.winner_name||''}</span></div><div class="lt-cards-row">${cardsHtml}</div>`;
        container.appendChild(div);
    });
    document.getElementById('last-trick-modal').style.display = 'flex';
}

// ─── Modals ─────────────────────────────────────────────────
function showContractModal(available) {
    const grid = document.getElementById('contract-grid');
    grid.innerHTML = '';
    if (gameState) document.getElementById('modal-round').textContent = gameState.round_number;
    available.forEach(ct => {
        const info = CONTRACT_INFO[ct]; if (!info) return;
        const btn = document.createElement('button');
        btn.className = `contract-btn ${info.cls}`;
        btn.innerHTML = `<span class="cb-icon">${info.icon}</span><span class="cb-name">${info.name}</span><span class="cb-desc">${info.desc}</span><span class="cb-score ${ct==='trump'?'positive-score':'negative-score'}">${info.score}</span>`;
        btn.addEventListener('click', () => selectContract(ct));
        grid.appendChild(btn);
    });
    document.getElementById('contract-modal').style.display = 'flex';
}

function showRoundEnd(data) {
    const container = document.getElementById('round-scores-display');
    container.innerHTML = '';
    if (!gameState) return;
    const scores = data.round_scores || {}, totals = data.total_scores || {};
    const maxScore = Math.max(...Object.values(scores));
    for (let i = 0; i < 4; i++) {
        const s = scores[i]||0, t = totals[i]||0;
        const name = gameState.players[i]?.name || `Player ${i+1}`;
        const row = document.createElement('div');
        row.className = `round-score-row ${s===maxScore&&s>0?'winner':''}`;
        row.innerHTML = `<span class="rs-name">${name}</span><span class="rs-round ${s>=0?'positive':'negative'}">${s>=0?'+':''}${s}</span><span class="rs-total">Total: ${t}</span>`;
        container.appendChild(row);
    }
    document.getElementById('round-end-title').textContent = `Round ${gameState.round_number} Complete!`;
    document.getElementById('round-end-modal').style.display = 'flex';
}

function showGameOver(data) {
    const container = document.getElementById('final-scores');
    container.innerHTML = '';
    const totals = data.total_scores || {};
    const sorted = Object.entries(totals).map(([id, score]) => ({id:parseInt(id), score, name:gameState?.players[parseInt(id)]?.name||`Player ${parseInt(id)+1}`})).sort((a,b)=>b.score-a.score);
    const medals = ['🥇','🥈','🥉','4️⃣'];
    sorted.forEach((p, idx) => {
        const row = document.createElement('div');
        row.className = 'final-score-row';
        row.innerHTML = `<span class="fs-rank">${medals[idx]}</span><span class="fs-name">${p.name}</span><span class="fs-score">${p.score}</span>`;
        container.appendChild(row);
    });
    document.getElementById('winner-text').textContent = `${sorted[0].name} Wins!`;
    document.getElementById('game-over-modal').style.display = 'flex';
}

function showMisdeal(reason) {
    document.getElementById('misdeal-text').textContent = reason;
    const t = document.getElementById('misdeal-toast');
    t.style.display = 'flex';
    setTimeout(() => { t.style.display = 'none'; }, 4000);
}

function showNotification(msg) {
    const el = document.getElementById('game-notification');
    document.getElementById('notification-text').textContent = msg;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 3500);
}

function hideAllModals() {
    document.getElementById('contract-modal').style.display = 'none';
    document.getElementById('trump-modal').style.display = 'none';
}

// ─── Scoreboard ─────────────────────────────────────────────
function updateScoreboard(scoreboard, players) {
    const container = document.getElementById('scoreboard-content');
    if (!scoreboard || !scoreboard.length) {
        container.innerHTML = '<p style="text-align:center;color:var(--text-dim);padding:40px;font-size:18px;">No rounds played yet</p>';
        return;
    }
    const pl = players || gameState?.players || [];
    const names = pl.map(p => p.name || `P${p.id+1}`);

    // Calculate neg/pos/balance and contracts used per player
    let negTotals = [0,0,0,0], posTotals = [0,0,0,0];
    // Track which contracts each player declared
    let playerContracts = [{},{},{},{}];
    const ALL_CONTRACTS = ['rifki','girls','boys','hearts','last_two','no_tricks','trump'];
    const CONTRACT_SHORT = {trump:'Koz', rifki:'Rıfkı', girls:'Kız', boys:'Erkek', hearts:'Kupa', last_two:'Son İki', no_tricks:'El Almaz'};

    scoreboard.forEach(r => {
        for (let i = 0; i < 4; i++) {
            const s = r.scores[i] || 0;
            if (s > 0) posTotals[i] += s; else negTotals[i] += s;
        }
        // Track contract used by declarer
        const decId = r.declarer_id;
        if (decId !== undefined) {
            if (!playerContracts[decId][r.contract]) playerContracts[decId][r.contract] = 0;
            playerContracts[decId][r.contract]++;
        }
    });

    let html = '<table class="sb-table"><thead><tr><th>RND</th><th>CONTRACT</th>';
    names.forEach(n => { html += `<th>${n}</th>`; });
    html += '</tr></thead><tbody>';

    scoreboard.forEach(r => {
        html += `<tr><td class="sb-round-num">${r.round}</td>`;
        html += `<td class="sb-contract-cell">${r.contract_display||r.contract}</td>`;
        for (let i = 0; i < 4; i++) {
            const s = r.scores[i]||0, isDec = r.declarer_id===i;
            const cls = s>0?'sb-positive':s<0?'sb-negative':'sb-zero';
            html += `<td class="${cls} ${isDec?'sb-declarer':''}">${s>0?'+':''}${s}</td>`;
        }
        html += '</tr>';
    });

    // Negative total row
    html += '<tr class="sb-summary-row sb-neg-row"><td colspan="2">− Negatives</td>';
    for (let i = 0; i < 4; i++) html += `<td class="sb-negative">${negTotals[i]}</td>`;
    html += '</tr>';

    // Positive total row
    html += '<tr class="sb-summary-row sb-pos-row"><td colspan="2">+ Positives</td>';
    for (let i = 0; i < 4; i++) html += `<td class="sb-positive">+${posTotals[i]}</td>`;
    html += '</tr>';

    // Balance (total) row
    const lastRound = scoreboard[scoreboard.length-1];
    html += '<tr class="sb-totals"><td colspan="2">BALANCE</td>';
    for (let i = 0; i < 4; i++) {
        const t = lastRound.totals[i]||0;
        html += `<td class="${t>0?'sb-positive':t<0?'sb-negative':'sb-zero'}">${t>0?'+':''}${t}</td>`;
    }
    html += '</tr>';

    // Contracts played/remaining section
    html += '<tr><td colspan="' + (2 + 4) + '" style="padding:16px 0 6px;font-size:14px;font-weight:700;color:var(--accent);text-align:left;border-top:2px solid var(--border-glass);">CONTRACTS PLAYED / REMAINING</td></tr>';
    ALL_CONTRACTS.forEach(ct => {
        const maxUses = ct === 'trump' ? 2 : 2;
        html += `<tr><td></td><td class="sb-contract-cell" style="font-size:14px;">${CONTRACT_SHORT[ct]||ct}</td>`;
        for (let i = 0; i < 4; i++) {
            const used = playerContracts[i][ct] || 0;
            if (ct === 'trump') {
                const remaining = 2 - used;
                html += `<td style="font-size:14px;font-weight:700;">${used > 0 ? '<span style="color:var(--green)">'+used+'✓</span>' : ''} ${remaining > 0 ? '<span style="color:var(--text-dim)">'+remaining+' left</span>' : ''}</td>`;
            } else {
                html += `<td style="font-size:14px;font-weight:700;">${used > 0 ? '<span style="color:var(--green)">✓</span>' : '<span style="color:var(--text-dim)">—</span>'}</td>`;
            }
        }
        html += '</tr>';
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}
