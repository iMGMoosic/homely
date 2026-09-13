<script lang="ts">
  import type { RotationItem } from '../../api/types';
  import Toggle from '../ui/Toggle.svelte';
  import { navigate } from '../../router.svelte';
  import { setEnabled, setDuration, move } from '../../stores/rotation.svelte';
  import { toast } from '../ui/toast.svelte';
  import { dragHandle } from 'svelte-dnd-action';

  let { item, first, last }: { item: RotationItem; first: boolean; last: boolean } = $props();

  async function run(fn: () => Promise<unknown>) {
    try {
      await fn();
    } catch (e: any) {
      toast(e.message, 'bad');
    }
  }
  function bump(delta: number) {
    const cur = item.duration_s ?? item.effective_duration_s;
    const next = Math.max(1, Math.min(600, Math.round(cur + delta)));
    run(() => setDuration(item.instance_id, next));
  }
</script>

<div class="card mod" class:disabled={!item.enabled}>
  <div class="row">
    <div class="grip" use:dragHandle aria-label="Drag to reorder" title="Drag to reorder">⋮⋮</div>
    <div class="order">
      <button
        class="btn sm icon"
        disabled={first}
        aria-label="Move up"
        onclick={() => run(() => move(item.instance_id, -1))}>▲</button
      >
      <button
        class="btn sm icon"
        disabled={last}
        aria-label="Move down"
        onclick={() => run(() => move(item.instance_id, 1))}>▼</button
      >
    </div>
    <button
      class="grow title"
      onclick={() => navigate(`/modules/${encodeURIComponent(item.instance_id)}`)}
    >
      <div class="row" style="gap:0.5rem">
        <strong>{item.name}</strong>
        {#if item.instance_id !== item.module}<span class="muted small mono"
            >{item.instance_id}</span
          >{/if}
        {#if item.is_current}<span class="chip ok">on screen</span>{/if}
        {#if item.is_idle}<span class="chip">idle</span>{/if}
        {#if item.status === 'error'}<span class="chip bad">error</span>{/if}
        {#if item.status === 'unavailable'}<span class="chip warn">unavailable</span>{/if}
      </div>
      {#if item.last_error}
        <div class="small" style="color:var(--danger)">{item.last_error}</div>
      {:else}
        <div class="muted small">Tap to configure ›</div>
      {/if}
    </button>
    <Toggle
      checked={item.enabled}
      label="Enabled"
      onchange={(v) => run(() => setEnabled(item.instance_id, v))}
    />
  </div>
  <div class="row between dwell">
    <span class="muted small">Shows for</span>
    <div class="row" style="gap:0.3rem">
      <button class="btn sm icon" onclick={() => bump(-5)}>−</button>
      <span class="mono" style="min-width:3.2rem;text-align:center"
        >{Math.round(item.effective_duration_s)}s</span
      >
      <button class="btn sm icon" onclick={() => bump(5)}>+</button>
      {#if item.duration_s !== null}
        <button
          class="btn sm"
          title="Use default"
          onclick={() => run(() => setDuration(item.instance_id, null))}>reset</button
        >
      {/if}
    </div>
  </div>
</div>

<style>
  .mod {
    padding: 0.75rem 0.9rem;
    margin-bottom: 0.6rem;
  }
  .mod.disabled {
    opacity: 0.6;
  }
  .order {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }
  .grip {
    cursor: grab;
    color: var(--text-dim);
    font-size: 1.1rem;
    letter-spacing: -0.15em;
    padding: 0.2rem 0.1rem;
    user-select: none;
    touch-action: none;
  }
  .grip:active {
    cursor: grabbing;
  }
  .title {
    background: none;
    border: none;
    text-align: left;
    padding: 0;
    color: inherit;
  }
  .dwell {
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--border);
  }
</style>
