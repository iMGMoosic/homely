<script lang="ts">
  import { api } from '../../api/client';
  import type { GeocodeResult } from '../../api/types';

  let { onpick }: { onpick: (r: GeocodeResult) => void } = $props();

  let q = $state('');
  let results = $state<GeocodeResult[]>([]);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let timer: ReturnType<typeof setTimeout> | null = null;

  function schedule() {
    if (timer) clearTimeout(timer);
    error = null;
    if (q.trim().length < 2) {
      results = [];
      return;
    }
    timer = setTimeout(search, 350);
  }

  async function search() {
    busy = true;
    try {
      results = await api.geocode(q.trim());
      if (!results.length) error = 'No places found';
    } catch (e: any) {
      error = e.message;
      results = [];
    } finally {
      busy = false;
    }
  }

  function pick(r: GeocodeResult) {
    onpick(r);
    results = [];
    q = r.label;
  }
</script>

<div class="search">
  <label class="label" for="place-search">Find a place</label>
  <div class="row">
    <input
      id="place-search"
      type="search"
      placeholder="City name, e.g. Minneapolis"
      bind:value={q}
      oninput={schedule}
      onkeydown={(e) => e.key === 'Enter' && (e.preventDefault(), search())}
      autocomplete="off"
    />
    {#if busy}<span class="spin"></span>{/if}
  </div>
  {#if error}<div class="help">{error}</div>{/if}
  {#if results.length}
    <ul class="results">
      {#each results as r (r.latitude + ',' + r.longitude)}
        <li>
          <button type="button" onclick={() => pick(r)}>
            <strong>{r.name}</strong>
            <span class="muted small">
              {[r.admin1, r.country].filter(Boolean).join(', ')} · {r.latitude.toFixed(2)},
              {r.longitude.toFixed(2)}{r.timezone ? ` · ${r.timezone}` : ''}
            </span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
  <div class="help">
    Picking a result fills in latitude, longitude, place name and timezone below.
  </div>
</div>

<style>
  .search {
    margin-bottom: 1rem;
  }
  .label {
    display: block;
    font-weight: 600;
    margin-bottom: 0.3rem;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  input {
    flex: 1;
  }
  .results {
    list-style: none;
    margin: 0.4rem 0 0;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }
  .results li + li {
    border-top: 1px solid var(--border);
  }
  .results button {
    all: unset;
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    width: 100%;
    padding: 0.5rem 0.7rem;
    cursor: pointer;
    box-sizing: border-box;
  }
  .results button:hover,
  .results button:focus-visible {
    background: var(--surface-2, rgba(255, 255, 255, 0.06));
  }
</style>
