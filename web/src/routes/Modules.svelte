<script lang="ts">
  import { onMount } from 'svelte';
  import ModuleCard from '../lib/modules/ModuleCard.svelte';
  import { rotation, loadRotation, addInstance } from '../stores/rotation.svelte';
  import { status } from '../stores/status.svelte';
  import { toast } from '../lib/ui/toast.svelte';
  import { navigate } from '../router.svelte';

  let adding = $state(false);
  let lastSeen = 0;

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
  Modules take turns on the display in this order. Toggle to enable, tap to configure.
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

{#each rotation.items as item, i (item.instance_id)}
  <ModuleCard {item} first={i === 0} last={i === rotation.items.length - 1} />
{/each}
