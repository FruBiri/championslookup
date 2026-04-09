const DATA_PATH = './data/pokemon.json';
const LEVEL = 50;
const FIXED_IV = 31;
const MAX_STAT_POINTS_PER_STAT = 32;

const els = {
  search: document.getElementById('pokemon-search'),
  clear: document.getElementById('clear-button'),
  suggestions: document.getElementById('suggestions'),
  resultPanel: document.getElementById('result-panel'),
  emptyState: document.getElementById('empty-state'),
  pokemonName: document.getElementById('pokemon-name'),
  pokemonMeta: document.getElementById('pokemon-meta'),
  abilityList: document.getElementById('ability-list'),
  statGrid: document.getElementById('stat-grid'),
  megaToggle: document.getElementById('mega-toggle'),
  megaToggleWrapper: document.getElementById('mega-toggle-wrapper'),
  dataStatus: document.getElementById('data-status')
};

let pokemonData = [];
let activePokemon = null;

function normalizeName(value) {
  return value
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

function calculateStatRange(baseStat, statName) {
  const isHp = statName === 'hp';

  if (isHp) {
    const min = Math.floor(((2 * baseStat + FIXED_IV) * LEVEL) / 100) + LEVEL + 10;
    return { min, max: min + MAX_STAT_POINTS_PER_STAT };
  }

  const baseAt50 = Math.floor(((2 * baseStat + FIXED_IV) * LEVEL) / 100) + 5;
  const lowest = Math.floor((baseAt50 + 0) * 0.9);
  const highest = Math.floor((baseAt50 + MAX_STAT_POINTS_PER_STAT) * 1.1);
  return { min: lowest, max: highest };
}

function getDisplayedForm(pokemon) {
  const wantsMega = els.megaToggle.checked;
  if (wantsMega && pokemon.hasMegaEvolution && pokemon.megaForm) {
    return pokemon.megaForm;
  }
  return pokemon.baseForm;
}

function renderSuggestions(matches) {
  els.suggestions.innerHTML = '';
  matches.slice(0, 8).forEach((pokemon) => {
    const button = document.createElement('button');
    button.className = 'suggestion-chip';
    button.type = 'button';
    button.textContent = pokemon.displayName;
    button.addEventListener('click', () => {
      els.search.value = pokemon.displayName;
      activePokemon = pokemon;
      renderPokemon();
      els.suggestions.innerHTML = '';
    });
    els.suggestions.appendChild(button);
  });
}

function renderPokemon() {
  if (!activePokemon) {
    els.resultPanel.classList.add('hidden');
    els.emptyState.classList.remove('hidden');
    return;
  }

  const form = getDisplayedForm(activePokemon);

  els.emptyState.classList.add('hidden');
  els.resultPanel.classList.remove('hidden');
  els.pokemonName.textContent = form.displayName;
  els.pokemonMeta.textContent = `${form.types.join(' / ')} • ${activePokemon.availableInChampions ? 'Available in Champions' : 'Not currently available in Champions'}`;

  if (activePokemon.hasMegaEvolution && activePokemon.megaForm) {
    els.megaToggleWrapper.classList.remove('hidden');
  } else {
    els.megaToggleWrapper.classList.add('hidden');
    els.megaToggle.checked = false;
  }

  els.abilityList.innerHTML = '';
  form.abilities.forEach((ability) => {
    const li = document.createElement('li');
    li.textContent = ability;
    els.abilityList.appendChild(li);
  });

  els.statGrid.innerHTML = '';
  const labels = {
    hp: 'HP', atk: 'Attack', def: 'Defense', spa: 'Sp. Atk', spd: 'Sp. Def', spe: 'Speed'
  };

  Object.entries(form.baseStats).forEach(([statKey, baseStat]) => {
    const range = calculateStatRange(baseStat, statKey);
    const card = document.createElement('div');
    card.className = 'stat-card';
    card.innerHTML = `
      <div class="stat-label">${labels[statKey]}</div>
      <div class="stat-range">${range.min}–${range.max}</div>
      <div class="stat-base">Base stat: ${baseStat}</div>
    `;
    els.statGrid.appendChild(card);
  });

  const verification = form.verification || activePokemon.verification || {};
  els.dataStatus.innerHTML = `
    <p class="status-line"><strong>${verification.label || 'Prototype dataset'}</strong></p>
    <p class="status-line">Source set: ${verification.sourceSet || 'Manual Champions-aligned entry'}</p>
    <p class="status-line">Notes: ${verification.notes || 'Use Champions-specific sources only.'}</p>
  `;
}

function findMatches(query) {
  const normalized = normalizeName(query);
  if (!normalized) return [];

  return pokemonData.filter((pokemon) => {
    const haystacks = [
      pokemon.displayName,
      pokemon.baseForm.displayName,
      ...(pokemon.aliases || [])
    ].map(normalizeName);

    return haystacks.some((value) => value.includes(normalized));
  });
}

function handleSearchInput() {
  const query = els.search.value.trim();
  if (!query) {
    activePokemon = null;
    els.suggestions.innerHTML = '';
    renderPokemon();
    return;
  }

  const matches = findMatches(query);
  renderSuggestions(matches);

  const exact = matches.find((pokemon) => normalizeName(pokemon.displayName) === normalizeName(query));
  if (exact) {
    activePokemon = exact;
    renderPokemon();
  }
}

async function init() {
  const response = await fetch(DATA_PATH);
  pokemonData = await response.json();

  els.search.addEventListener('input', handleSearchInput);
  els.clear.addEventListener('click', () => {
    els.search.value = '';
    activePokemon = null;
    els.megaToggle.checked = false;
    els.suggestions.innerHTML = '';
    renderPokemon();
  });
  els.megaToggle.addEventListener('change', renderPokemon);

  renderPokemon();
}

init().catch((error) => {
  console.error(error);
  els.emptyState.innerHTML = `
    <h2>Unable to load data</h2>
    <p>Check that <code>data/pokemon.json</code> is present and GitHub Pages is serving it.</p>
  `;
});
