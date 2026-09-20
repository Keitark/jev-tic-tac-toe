let csrf = '';
let state = null;

const $ = (id) => document.getElementById(id);
const percent = (value) => `${(100 * (value || 0)).toFixed(1)}%`;

async function api(path, data) {
  const res = await fetch(path, {
    method: data === undefined ? 'GET' : 'POST',
    headers: data === undefined ? {} : {'Content-Type': 'application/json', 'X-TTT-Token': csrf},
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body;
}

function configPayload() {
  return {
    controllers: {X: $('controller-x').value, O: $('controller-o').value},
    prompt_mode: $('prompt-mode').value,
    seed: Number($('seed').value),
    interval: Number($('interval').value),
  };
}

function renderBoard(s) {
  const board = $('board');
  board.innerHTML = '';
  const last = s.last_decision;
  const probs = last?.probabilities || {};
  const oracle = new Set(s.game.analysis.optimal_moves || []);
  s.game.actions.forEach((action, i) => {
    const button = document.createElement('button');
    button.className = 'cell';
    if (oracle.has(action.id)) button.classList.add('optimal');
    if (last?.choice === action.id) {
      button.classList.add('chosen');
      if (last.move && !last.move.legal) button.classList.add('illegal');
    }
    button.dataset.action = action.id;
    button.innerHTML = `<span class="coord">${action.row + 1},${action.col + 1}</span><span class="mark">${s.game.board[i] === '.' ? '' : s.game.board[i]}</span><span class="prob">${probs[action.id] === undefined ? '' : percent(probs[action.id])}</span>`;
    button.disabled = s.busy || s.playing || s.game.result !== null || s.controllers[s.game.turn] !== 'human';
    button.addEventListener('click', () => move(action.id));
    board.appendChild(button);
  });
}

function render(s) {
  state = s;
  $('controller-x').value = s.controllers.X;
  $('controller-o').value = s.controllers.O;
  $('prompt-mode').value = s.prompt_mode;
  $('seed').value = s.seed;
  $('interval').value = s.interval;
  $('turn').textContent = `Turn: ${s.game.turn}`;
  $('result').textContent = s.game.result ? (s.game.result === 'DRAW' ? 'Draw' : `${s.game.result} wins`) : (s.playing ? 'Playing…' : 'In progress');
  $('error').textContent = s.error || '';

  $('m-decisions').textContent = s.stats.ai_decisions;
  $('m-illegal').textContent = s.stats.illegal;
  $('m-illegal-rate').textContent = percent(s.stats.illegal_rate);
  $('m-optimal-rate').textContent = percent(s.stats.optimal_rate_legal);

  renderBoard(s);

  const last = s.last_decision;
  if (!last) {
    $('last').textContent = 'No AI decision yet.';
  } else if (last.source === 'human') {
    $('last').textContent = `Human chose ${last.choice}.`;
  } else {
    const legality = last.move?.legal ? '<span class="good">LEGAL</span>' : '<span class="bad">ILLEGAL</span>';
    const optimal = last.move?.optimal === true ? ' · optimal' : last.move?.optimal === false ? ' · suboptimal' : '';
    $('last').innerHTML = `<strong>${last.player} / ${last.source}</strong><br>${last.choice} · ${percent(last.probabilities?.[last.choice])} · ${legality}${optimal}<br><span class="dim">latency ${Number(last.latency_ms || 0).toFixed(0)} ms</span>`;
  }

  const values = s.game.analysis.action_values || {};
  $('oracle').innerHTML = s.game.actions.map(a => {
    const v = values[a.id];
    const label = v === null ? 'occupied' : v === 1 ? 'win' : v === 0 ? 'draw' : 'loss';
    const cls = v === 1 ? 'good' : v === null ? 'dim' : v === -1 ? 'bad' : '';
    return `<div class="oracle-row"><span>${a.row + 1},${a.col + 1}</span><span>${a.id}</span><span class="${cls}">${label}</span></div>`;
  }).join('');

  const history = [...s.game.history].reverse().slice(0, 14);
  $('history').innerHTML = history.length ? history.map(h => `<div class="history-row"><span>#${h.attempt}</span><span>${h.player} → ${h.row + 1},${h.col + 1}</span><span class="${h.legal ? 'good' : 'bad'}">${h.legal ? (h.optimal ? 'legal · optimal' : 'legal') : 'illegal'}</span></div>`).join('') : '<span class="dim">No moves yet.</span>';

  $('step').disabled = s.busy || s.playing || !!s.game.result || s.controllers[s.game.turn] === 'human';
  $('play').disabled = s.busy || s.playing || !!s.game.result || s.controllers[s.game.turn] === 'human';
  $('pause').disabled = !s.busy && !s.playing;
}

async function refresh() {
  try {
    render(await api('/api/state'));
  } catch (e) {
    $('error').textContent = e.message;
  }
}

async function move(action) {
  try {
    render(await api('/api/move', {action}));
    if (!state.game.result && state.controllers[state.game.turn] !== 'human') {
      render(await api('/api/play', {}));
    }
  } catch (e) { $('error').textContent = e.message; }
}

$('new').addEventListener('click', async () => {
  try { render(await api('/api/new', configPayload())); }
  catch (e) { $('error').textContent = e.message; }
});
$('step').addEventListener('click', async () => {
  try { render(await api('/api/step', {})); }
  catch (e) { $('error').textContent = e.message; }
});
$('play').addEventListener('click', async () => {
  try { render(await api('/api/play', {})); }
  catch (e) { $('error').textContent = e.message; }
});
$('pause').addEventListener('click', async () => {
  try { render(await api('/api/pause', {})); }
  catch (e) { $('error').textContent = e.message; }
});

(async () => {
  try {
    const initial = await api('/api/status');
    csrf = initial.csrf;
    $('keys').textContent = `Jev key: ${initial.keys.jev ? 'ready' : 'missing'} · OpenRouter: ${initial.keys.openrouter ? 'ready' : 'missing'}`;
    render(initial);
    setInterval(() => { if (state?.playing || state?.busy) refresh(); }, 250);
  } catch (e) {
    $('error').textContent = e.message;
  }
})();
