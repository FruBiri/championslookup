const POKEMON_DATA_PATH = './data/pokemon.json';
const ABILITY_DATA_PATH = './data/abilities.json';

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
  dataStatus: document.getElementById('data-status'),
  abilityHelp: document.getElementById('ability-help')
};

let pokemonData = [];
let pokemonByFormId = {};
let abilityData = {};
let activePokemon = null;

function normalizeName(value) {
  return String(value || '')
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

function slugify(value) {
  return normalizeName(value).replace(/\s+/g, '-');
}

function setAbilityHelp(content) {
  els.abilityHelp.innerHTML =
    content ||
    '<p class="helper-text">Tap, click, or hover an Ability to see its effect.</p>';
}

function getDisplayedForm(pokemon) {
  if (!pokemon) return null;

  const wantsMega = els.megaToggle.checked;
  if (wantsMega && pokemon.hasMegaEvolution && pokemon.megaEvolution) {
    return pokemonByFormId[pokemon.megaEvolution] || pokemon;
  }

  return pokemon;
}

function renderSuggestions(matches) {
  els.suggestions.innerHTML = '';

  matches.slice(0, 8).forEach((pokemon) => {
    const button = document.createElement('button');
    button.className = 'suggestion-chip';
    button.type = 'button';
    button.textContent = pokemon.name;
    button.addEventListener('click', () => {
      els.search.value = pokemon.name;
      activePokemon = pokemon;
      els.megaToggle.checked = false;
      renderPokemon();
      els.suggestions.innerHTML = '';
    });
    els.suggestions.appendChild(button);
  });
}

function renderAbilityItem(abilityName) {
  const key = slugify(abilityName);
  const ability = abilityData[key] || {
    name: abilityName,
    shortEffect: 'Ability reference has not been added to the local dataset yet.',
    effect: 'Ability reference has not been added to the local dataset yet.',
    source: `https://bulbapedia.bulbagarden.net/wiki/${encodeURIComponent(abilityName)}_(Ability)`
  };

  const li = document.createElement('li');
  li.className = 'ability-pill';

  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'ability-trigger';
  trigger.textContent = ability.name;
  trigger.setAttribute('aria-expanded', 'false');

  const showAbilityHelp = () => {
    trigger.setAttribute('aria-expanded', 'true');
    setAbilityHelp(`
      <p class="status-line"><strong>${ability.name}</strong></p>
      <p class="status-line">${ability.shortEffect || ability.effect}</p>
      <p class="status-line">
        <a href="${ability.source}" target="_blank" rel="noreferrer">Open wiki</a>
      </p>
    `);
  };

  const clearExpanded = () => {
    trigger.setAttribute('aria-expanded', 'false');
  };

  trigger.addEventListener('mouseenter', showAbilityHelp);
  trigger.addEventListener('focus', showAbilityHelp);
  trigger.addEventListener('click', showAbilityHelp);
  trigger.addEventListener('mouseleave', clearExpanded);
  trigger.addEventListener('blur', clearExpanded);

  const link = document.createElement('a');
  link.className = 'ability-link';
  link.href = ability.source;
  link.target = '_blank';
  link.rel = 'noreferrer';
  link.textContent = 'Wiki';
  link.setAttribute('aria-label', `Open ${ability.name} wiki page`);

  li.appendChild(trigger);
  li.appendChild(link);

  return li;
}

function renderPokemon() {
  const displayed = getDisplayedForm(activePokemon);

  if (!displayed) {
    els.resultPanel.classList.add('hidden');
    els.emptyState.classList.remove('hidden');
    els.megaToggleWrapper.classList.add('hidden');
    setAbilityHelp('');
    return;
  }

  els.emptyState.classList.add('hidden');
  els.resultPanel.classList.remove('hidden');

  els.pokemonName.textContent = displayed.name;
  els.pokemonMeta.textContent =
    `${(displayed.types || []).join(' / ')} • ${displayed.availableInChampions ? 'Available in Champions' : 'Not currently available in Champions'}`;

  if (activePokemon && activePokemon.hasMegaEvolution && activePokemon.megaEvolution) {
    els.megaToggleWrapper.classList.remove('hidden');
  } else {
    els.megaToggleWrapper.classList.add('hidden');
    els.megaToggle.checked = false;
  }

  els.abilityList.innerHTML = '';
  (displayed.abilities || []).forEach((ability) => {
    els.abilityList.appendChild(renderAbilityItem(ability));
  });
  setAbilityHelp('');

  els.statGrid.innerHTML = '';
  const labels = {
    hp: 'HP',
    atk: 'Attack',
    def: 'Defense',
    spa: 'Sp. Atk',
    spd: 'Sp. Def',
    spe: 'Speed'
  };

  const statRanges = displayed.statRanges || {};
  const baseStats = displayed.baseStats || {};

  ['hp', 'atk', 'def', 'spa', 'spd', 'spe'].forEach((statKey) => {
    const range = statRanges[statKey];
    if (!range) return;

    const baseStat = baseStats[statKey] ?? '—';
    const card = document.createElement('div');
    card.className = 'stat-card';
    card.innerHTML = `
      <div class="stat-label">${labels[statKey]}</div>
      <div class="stat-range">${range.min}–${range.max}</div>
      <div class="stat-base">Base stat: ${baseStat}</div>
    `;
    els.statGrid.appendChild(card);
  });

  els.dataStatus.innerHTML = `
    <p class="status-line"><strong>${displayed.enriched ? 'Champions roster + enriched data' : 'Partial dataset'}</strong></p>
    <p class="status-line">Form ID: ${displayed.formId || 'Unknown'}</p>
    <p class="status-line">Dex #: ${displayed.nationalDex || 'Unknown'}</p>
  `;
}

function findMatches(query) {
  const normalized = normalizeName(query);
  if (!normalized) return [];

  return pokemonData.filter((pokemon) => {
    const haystacks = [
      pokemon.name,
      pokemon.baseName,
      pokemon.formId,
      pokemon.lookupName
    ].map(normalizeName);

    return haystacks.some((value) => value.includes(normalized));
  });
}

function handleSearchInput() {
  const query = els.search.value.trim();

  if (!query) {
    activePokemon = null;
    els.suggestions.innerHTML = '';
    els.megaToggle.checked = false;
    renderPokemon();
    return;
  }

  const matches = findMatches(query);
  renderSuggestions(matches);

  const exact = matches.find(
    (pokemon) =>
      normalizeName(pokemon.name) === normalizeName(query) ||
      normalizeName(pokemon.baseName) === normalizeName(query)
  );

  if (exact) {
    activePokemon = exact;
    renderPokemon();
  }
}

async function init() {
  const [pokemonResponse, abilityResponse] = await Promise.all([
    fetch(POKEMON_DATA_PATH),
    fetch(ABILITY_DATA_PATH)
  ]);

  const pokemonPayload = await pokemonResponse.json();
  const abilityPayload = await abilityResponse.json();

  pokemonData = Array.isArray(pokemonPayload)
    ? pokemonPayload
    : (pokemonPayload.pokemon || []);

  abilityData =
    Array.isArray(abilityPayload)
      ? Object.fromEntries(abilityPayload.map((entry) => [slugify(entry.name), entry]))
      : (abilityPayload.abilities || {});

  pokemonByFormId = Object.fromEntries(
    pokemonData.map((pokemon) => [pokemon.formId, pokemon])
  );

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
    <p>Check the browser console and verify that <code>data/pokemon.json</code> and <code>data/abilities.json</code> are being served correctly.</p>
  `;
});