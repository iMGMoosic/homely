<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api, ApiRequestError } from '../api/client';
  import type { RotationItem } from '../api/types';
  import SchemaForm from '../lib/form/SchemaForm.svelte';
  import LivePreview from '../lib/preview/LivePreview.svelte';
  import { rotation, loadRotation, catalogFor, removeInstance } from '../stores/rotation.svelte';
  import { navigate } from '../router.svelte';
  import { toast } from '../lib/ui/toast.svelte';
  import { clone } from '../lib/clone';

  let { id }: { id: string } = $props();

  let item = $state<RotationItem | null>(null);
  let value = $state<Record<string, any>>({});
  let errors = $state<Record<string, string>>({});
  let dirty = $state(false);
  let saving = $state(false);
  let pinned = $state(false);
  let loadError = $state<string | null>(null);

  const catalog = $derived(item ? catalogFor(item.module) : undefined);

  async function load() {
    try {
      if (!rotation.loaded) await loadRotation();
      item = await api.instance(id);
      value = clone(item.settings);
      dirty = false;
      errors = {};
    } catch (e: any) {
      loadError = e.message;
    }
  }

  async function save() {
    if (!item) return;
    saving = true;
    errors = {};
    try {
      item = await api.saveSettings(item.instance_id, value);
      value = clone(item.settings);
      dirty = false;
      toast('Saved', 'ok');
      loadRotation();
    } catch (e: any) {
      if (e instanceof ApiRequestError && e.status === 422) errors = e.errors;
      else toast(e.message, 'bad');
    } finally {
      saving = false;
    }
  }

  function reset() {
    if (!catalog) return;
    value = clone(catalog.defaults);
    dirty = true;
  }

  async function togglePin() {
    if (!item) return;
    pinned = !pinned;
    try {
      await api.pin(item.instance_id, pinned);
    } catch (e: any) {
      toast(e.message, 'bad');
    }
  }

  async function remove() {
    if (!item || !confirm(`Remove ${item.name} from the rotation?`)) return;
    try {
      await removeInstance(item.instance_id);
      navigate('/modules');
    } catch (e: any) {
      toast(e.message, 'bad');
    }
  }

  onMount(load);
  onDestroy(() => {
    if (pinned && item) api.pin(item.instance_id, false).catch(() => {});
  });
</script>

<div class="row" style="margin-bottom:0.75rem">
  <button class="btn icon" aria-label="Back" onclick={() => navigate('/modules')}>‹</button>
  <div class="grow">
    <h1 style="margin:0">{item?.name ?? '…'}</h1>
    {#if catalog}<div class="muted small">{catalog.description}</div>{/if}
  </div>
</div>

{#if loadError}
  <div class="banner bad">{loadError}</div>
{:else if item && catalog}
  <div class="card">
    <div class="row between">
      <span class="muted small">Preview {pinned ? '(showing this module)' : ''}</span>
      <button class="btn sm" class:primary={pinned} onclick={togglePin}
        >{pinned ? 'Unpin' : 'Show this module now'}</button
      >
    </div>
    <div style="margin-top:0.6rem"><LivePreview maxWidth={320} /></div>
  </div>

  {#if item.last_error}<div class="banner bad">{item.last_error}</div>{/if}

  <div class="card">
    <SchemaForm schema={catalog.schema} bind:value {errors} onchange={() => (dirty = true)} />
    {#if Object.keys(catalog.schema.properties ?? {}).length === 0}
      <p class="muted">This module has no settings.</p>
    {/if}
  </div>

  <div class="savebar">
    <button class="btn danger sm" onclick={remove}>Remove</button>
    <span class="grow"></span>
    <button class="btn" onclick={reset}>Defaults</button>
    <button class="btn primary" disabled={!dirty || saving} onclick={save}>
      {#if saving}<span class="spin"></span>{/if} Save
    </button>
  </div>
{:else}
  <p class="muted"><span class="spin"></span> Loading…</p>
{/if}
