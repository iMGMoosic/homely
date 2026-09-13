<script lang="ts">
  import { onMount } from 'svelte';
  import { api, ApiRequestError } from '../api/client';
  import type { HardwarePayload, SettingsPayload } from '../api/types';
  import SchemaForm from '../lib/form/SchemaForm.svelte';
  import { toast } from '../lib/ui/toast.svelte';
  import { clone } from '../lib/clone';

  let settings = $state<SettingsPayload | null>(null);
  let hardware = $state<HardwarePayload | null>(null);
  let values = $state<Record<string, any>>({});
  let errors = $state<Record<string, Record<string, string>>>({});
  let dirty = $state<Record<string, boolean>>({});
  let saving = $state<string | null>(null);
  let open = $state<Record<string, boolean>>({ brightness: true, rotation: true, location: true });

  const sections: Array<{
    key: string;
    title: string;
    help: string;
    source: 'settings' | 'hardware';
  }> = [
    {
      key: 'brightness',
      title: 'Brightness & night mode',
      help: 'Rules dim or turn off the display between two times; 0 means off.',
      source: 'settings',
    },
    {
      key: 'rotation',
      title: 'Rotation',
      help: 'How long each module shows by default, and how they transition.',
      source: 'settings',
    },
    {
      key: 'location',
      title: 'Location',
      help: 'Shared by weather, transit, sports and the clock. Leave the timezone empty to use the system one.',
      source: 'settings',
    },
    {
      key: 'panel',
      title: 'Panel & driver',
      help: 'Applies after a restart. See docs/hardware.md for tuning tips.',
      source: 'hardware',
    },
    {
      key: 'display',
      title: 'Display backend',
      help: 'Applies after a restart.',
      source: 'hardware',
    },
    { key: 'web', title: 'Web server', help: 'Applies after a restart.', source: 'hardware' },
  ];

  async function load() {
    try {
      const [s, h] = await Promise.all([api.settings(), api.hardware()]);
      values = {
        brightness: clone(s.brightness),
        rotation: clone(s.rotation),
        location: clone(s.location),
        panel: clone(h.panel),
        display: clone(h.display),
        web: clone(h.web),
      };
      dirty = {};
      settings = s;
      hardware = h;
    } catch (e: any) {
      toast(e.message, 'bad');
    }
  }

  async function save(key: string, source: 'settings' | 'hardware') {
    saving = key;
    errors[key] = {};
    try {
      if (source === 'settings') {
        settings = await api.saveGlobalSettings({ [key]: values[key] } as any);
        values[key] = clone((settings as any)[key]);
      } else {
        hardware = await api.saveHardware({ [key]: values[key] } as any);
        values[key] = clone((hardware as any)[key]);
        toast('Saved. Restart homely to apply hardware changes.', 'warn');
      }
      dirty[key] = false;
      if (source === 'settings') toast('Saved', 'ok');
    } catch (e: any) {
      if (e instanceof ApiRequestError && e.status === 422) {
        const stripped: Record<string, string> = {};
        for (const [p, m] of Object.entries(e.errors))
          stripped[p.replace(new RegExp(`^${key}\\.?`), '') || '_'] = m;
        errors[key] = stripped;
      } else toast(e.message, 'bad');
    } finally {
      saving = null;
    }
  }

  onMount(load);
</script>

<h1>Display settings</h1>
{#if !settings || !hardware}
  <p class="muted"><span class="spin"></span> Loading…</p>
{:else}
  {#each sections as s (s.key)}
    {@const schema =
      s.source === 'settings'
        ? settings.schema[s.key as 'rotation']
        : hardware.schema[s.key as 'panel']}
    <details class="card" bind:open={open[s.key]}>
      <summary>
        <strong>{s.title}</strong>
        {#if dirty[s.key]}<span class="chip warn">unsaved</span>{/if}
        {#if s.source === 'hardware'}<span class="chip">restart</span>{/if}
        <div class="muted small">{s.help}</div>
      </summary>
      <div style="margin-top:0.9rem">
        {#if values[s.key]}
          <SchemaForm
            {schema}
            bind:value={values[s.key]}
            errors={errors[s.key] ?? {}}
            onchange={() => (dirty[s.key] = true)}
          />
        {/if}
        <div class="row" style="justify-content:flex-end">
          <button
            class="btn primary"
            disabled={!dirty[s.key] || saving === s.key}
            onclick={() => save(s.key, s.source)}
          >
            {#if saving === s.key}<span class="spin"></span>{/if} Save
          </button>
        </div>
      </div>
    </details>
  {/each}
{/if}

<style>
  summary {
    cursor: pointer;
    list-style: none;
  }
  summary::-webkit-details-marker {
    display: none;
  }
  summary strong {
    margin-right: 0.4rem;
  }
</style>
