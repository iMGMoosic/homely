<script lang="ts">
  import { api } from '../../api/client';
  import type { TransitChoice } from '../../api/types';

  let { provider, onpick }: { provider: string; onpick: (stopId: number, label: string) => void } =
    $props();

  let open = $state(false);
  let routes = $state<TransitChoice[]>([]);
  let directions = $state<TransitChoice[]>([]);
  let stops = $state<TransitChoice[]>([]);
  let route = $state('');
  let direction = $state('');
  let place = $state('');
  let busy = $state(false);
  let error = $state<string | null>(null);

  async function load<T>(fn: () => Promise<T>): Promise<T | null> {
    busy = true;
    error = null;
    try {
      return await fn();
    } catch (e: any) {
      error = e.message;
      return null;
    } finally {
      busy = false;
    }
  }

  async function toggle() {
    open = !open;
    if (open && !routes.length) routes = (await load(() => api.transitRoutes(provider))) ?? [];
  }

  async function pickRoute() {
    direction = '';
    place = '';
    directions = [];
    stops = [];
    if (route) directions = (await load(() => api.transitDirections(provider, route))) ?? [];
  }

  async function pickDirection() {
    place = '';
    stops = [];
    if (direction) stops = (await load(() => api.transitStops(provider, route, direction))) ?? [];
  }

  async function pickPlace() {
    if (!place) return;
    const stop = await load(() => api.transitStop(provider, route, direction, place));
    if (stop) {
      onpick(Number(stop.id), stop.label);
      open = false;
    }
  }
</script>

<div class="picker">
  <button type="button" class="btn sm" onclick={toggle}>
    {open ? 'Cancel' : 'Find by route'}
  </button>
  {#if busy}<span class="spin"></span>{/if}
  {#if open}
    <div class="steps">
      <select class="input" bind:value={route} onchange={pickRoute} aria-label="Route">
        <option value="">Route…</option>
        {#each routes as r (r.id)}<option value={r.id}>{r.label}</option>{/each}
      </select>
      {#if directions.length}
        <select
          class="input"
          bind:value={direction}
          onchange={pickDirection}
          aria-label="Direction"
        >
          <option value="">Direction…</option>
          {#each directions as d (d.id)}<option value={d.id}>{d.label}</option>{/each}
        </select>
      {/if}
      {#if stops.length}
        <select class="input" bind:value={place} onchange={pickPlace} aria-label="Stop">
          <option value="">Stop…</option>
          {#each stops as s (s.id)}<option value={s.id}>{s.label}</option>{/each}
        </select>
      {/if}
    </div>
  {/if}
  {#if error}<div class="error">{error}</div>{/if}
</div>

<style>
  .picker {
    margin-top: 0.4rem;
  }
  .steps {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    margin-top: 0.5rem;
  }
</style>
