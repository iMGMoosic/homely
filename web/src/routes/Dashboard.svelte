<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../api/client';
  import LivePreview from '../lib/preview/LivePreview.svelte';
  import { status } from '../stores/status.svelte';
  import { rotation, loadRotation } from '../stores/rotation.svelte';
  import { navigate } from '../router.svelte';
  import { toast } from '../lib/ui/toast.svelte';

  let ledLook = $state(localStorage.getItem('homely.ledLook') === '1');
  let brightness = $state<number | null>(null);
  let brightnessTimer: ReturnType<typeof setTimeout> | null = null;

  $effect(() => {
    localStorage.setItem('homely.ledLook', ledLook ? '1' : '0');
  });
  $effect(() => {
    if (brightness === null && status.state) brightness = status.state.brightness;
  });

  const current = $derived(rotation.items.find((i) => i.instance_id === status.state?.current));
  const progress = $derived(
    status.state && status.state.slot_duration > 0
      ? Math.min(1, status.state.slot_elapsed / status.state.slot_duration)
      : 0,
  );

  function onBrightness(e: Event) {
    brightness = Number((e.target as HTMLInputElement).value);
    if (brightnessTimer) clearTimeout(brightnessTimer);
    brightnessTimer = setTimeout(async () => {
      try {
        await api.setBrightness(brightness!);
      } catch (err: any) {
        toast(err.message, 'bad');
      }
    }, 150);
  }

  async function action(name: string) {
    try {
      const r = await api.action(name);
      if (!r.ok) toast(r.message, 'bad');
    } catch (err: any) {
      toast(err.message, 'bad');
    }
  }

  onMount(() => {
    if (!rotation.loaded) loadRotation();
  });
</script>

<h1>Display</h1>
<div class="card">
  <LivePreview bind:ledLook />
  <div class="row between" style="margin-top:0.75rem">
    <div class="grow">
      {#if current}
        <div class="row" style="gap:0.5rem">
          <strong>{current.name}</strong>
          {#if status.state?.pinned}<span class="chip warn">pinned</span>{/if}
          {#if status.state?.takeover}<span class="chip">takeover</span>{/if}
        </div>
        <div class="progress"><div class="bar" style="width:{progress * 100}%"></div></div>
      {:else}
        <span class="muted">{status.state?.phase === 'blank' ? 'Nothing to show' : 'Waiting…'}</span
        >
      {/if}
    </div>
    <button class="btn icon" title="Previous" onclick={() => action('prev')}>‹</button>
    <button class="btn icon" title="Next" onclick={() => action('next')}>›</button>
  </div>
</div>

<div class="card">
  <div class="field">
    <label for="brightness">Brightness</label>
    <div class="range-row">
      <input
        id="brightness"
        type="range"
        min="0"
        max="100"
        value={brightness ?? 60}
        oninput={onBrightness}
      />
      <output>{brightness ?? '–'}%</output>
    </div>
    <div class="help">Night schedule lives under Display.</div>
  </div>
  <div class="field inline">
    <label for="ledlook">LED look in the preview</label>
    <input
      id="ledlook"
      type="checkbox"
      bind:checked={ledLook}
      style="width:20px;height:20px;accent-color:var(--accent)"
    />
  </div>
</div>

<div class="card">
  <div class="row between">
    <div>
      <strong>Rotation</strong>
      <div class="muted small">
        {rotation.items.filter((i) => i.enabled).length} of {rotation.items.length} modules enabled
      </div>
    </div>
    <button class="btn" onclick={() => navigate('/modules')}>Manage</button>
  </div>
  <div class="chips" style="margin-top:0.6rem">
    {#each rotation.items as it (it.instance_id)}
      <span
        class="chip"
        class:ok={it.is_current}
        class:bad={it.status === 'error'}
        style:opacity={it.enabled ? 1 : 0.5}>{it.name}</span
      >
    {/each}
  </div>
</div>

<style>
  .progress {
    height: 3px;
    background: var(--bg-elev-2);
    border-radius: 2px;
    margin-top: 0.4rem;
    overflow: hidden;
  }
  .bar {
    height: 100%;
    background: var(--accent);
    transition: width 0.5s linear;
  }
</style>
