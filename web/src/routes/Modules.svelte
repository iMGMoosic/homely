<script lang="ts">
  import { onMount } from 'svelte';
  import ModuleCard from '../lib/modules/ModuleCard.svelte';
  import { rotation, loadRotation, addInstance } from '../stores/rotation.svelte';
  import { status } from '../stores/status.svelte';
  import { toast } from '../lib/ui/toast.svelte';
  import { navigate } from '../router.svelte';
  import { dragHandleZone } from 'svelte-dnd-action';
  import { api } from '../api/client';
  import type { RotationItem } from '../api/types';

  let adding = $state(false);
  let lastSeen = 0;
  // svelte-dnd-action wants an `id` on each item; wrap the rotation items.
  let dragItems = $state<Array<{ id: string; item: RotationItem }>>([]);
  let dragging = false;

  $effect(() => {
    if (!dragging) dragItems = rotation.items.map((item) => ({ id: item.instance_id, item }));
  });

  function consider(e: CustomEvent<{ items: Array<{ id: string; item: RotationItem }> }>) {
    dragging = true;
    dragItems = e.detail.items;
  }

  async function finalize(e: CustomEvent<{ items: Array<{ id: string; item: RotationItem }> }>) {
    dragItems = e.detail.items;
    dragging = false;
    const order = dragItems.map((d) => d.id);
    if (order.join() === rotation.items.map((i) => i.instance_id).join()) return;
    try {
      rotation.items = await api.reorder(order);
    } catch (err: any) {
      toast(err.message, 'bad');
      dragItems = rotation.items.map((item) => ({ id: item.instance_id, item }));
    }
  }

  const addable = $derived(
    rotation.catalog.filter(
      (c) =>
        c.supports_current_size &&
        (c.allow_multiple || !rotation.items.some((i) => i.module === c.id)),
    ),
  );

  onMount(loadRotation);
  $effect(() => {
    if (status.lastConfigChange && status.lastConfigChange !== lastSeen) {
      lastSeen = status.lastConfigChange;
      loadRotation();
    }
  });

  async function add(id: string) {
    try {
      const item = await addInstance(id);
      adding = false;
      navigate(`/modules/${encodeURIComponent(item.instance_id)}`);
    } catch (e: any) {
      toast(e.message, 'bad');
    }
  }
</script>

<div class="row between" style="margin-bottom:0.75rem">
  <h1 style="margin:0">Modules</h1>
  <button class="btn primary" onclick={() => (adding = !adding)}
    >{adding ? 'Cancel' : '+ Add'}</button
  >
</div>
<p class="muted small" style="margin-bottom:1rem">
  Modules take turns on the display in this order. Drag the grip (or use the arrows) to reorder,
  toggle to enable, tap to configure.
</p>

{#if adding}
  <div class="card">
    <h2>Add a module</h2>
    {#if addable.length === 0}
      <p class="muted">Every available module is already in the rotation.</p>
    {/if}
    <div class="list">
      {#each addable as c (c.id)}
        <button
          class="btn"
          style="justify-content:flex-start;text-align:left"
          onclick={() => add(c.id)}
        >
          <div>
            <div><strong>{c.name}</strong> <span class="chip">{c.tier}</span></div>
            <div class="muted small">{c.description}</div>
          </div>
        </button>
      {/each}
    </div>
  </div>
{/if}

{#if rotation.error}
  <div class="banner bad">{rotation.error}</div>
{:else if !rotation.loaded}
  <p class="muted"><span class="spin"></span> Loading…</p>
{:else if rotation.items.length === 0}
  <div class="card"><p class="muted">No modules yet. Add one above.</p></div>
{/if}

<div
  use:dragHandleZone={{ items: dragItems, flipDurationMs: 150, dropTargetStyle: {} }}
  onconsider={consider}
  onfinalize={finalize}
>
  {#each dragItems as d, i (d.id)}
    <div>
      <ModuleCard item={d.item} first={i === 0} last={i === dragItems.length - 1} />
    </div>
  {/each}
</div>
