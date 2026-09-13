<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../api/client';
  import type { SystemInfo } from '../api/types';
  import { status } from '../stores/status.svelte';
  import { toast } from '../lib/ui/toast.svelte';

  let info = $state<SystemInfo | null>(null);
  let busy = $state<string | null>(null);

  async function load() {
    try {
      info = await api.system();
    } catch (e: any) {
      toast(e.message, 'bad');
    }
  }

  async function action(name: string, confirmText?: string) {
    if (confirmText && !confirm(confirmText)) return;
    busy = name;
    try {
      const r = await api.action(name);
      toast(r.message, r.ok ? 'ok' : 'bad');
      if (name === 'restart-renderer') setTimeout(load, 4000);
    } catch (e: any) {
      toast(e.message, 'bad');
    } finally {
      busy = null;
    }
  }

  function fmtUptime(s: number) {
    const d = Math.floor(s / 86400),
      h = Math.floor((s % 86400) / 3600),
      m = Math.floor((s % 3600) / 60);
    return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
  }

  onMount(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  });
</script>

<h1>System</h1>
{#if info}
  {#if info.restart_pending || status.restartPending}
    <div class="banner warn">A restart is needed to apply hardware/web settings.</div>
  {/if}
  <div class="card">
    <dl class="kv">
      <dt>Version</dt>
      <dd>homely {info.version}</dd>
      <dt>Host</dt>
      <dd>{info.hostname} · {info.ip_addresses.join(', ') || 'no address'}</dd>
      <dt>Platform</dt>
      <dd>{info.platform} · Python {info.python}</dd>
      <dt>Display</dt>
      <dd>
        {info.size}
        {info.orientation} · backend {info.backend}{info.backend === 'none' &&
        info.hardware_available
          ? ' (hardware available)'
          : ''}
      </dd>
      <dt>Render</dt>
      <dd>
        {info.render_fps} / {info.target_fps} fps{info.last_error
          ? ` · last error: ${info.last_error}`
          : ''}
      </dd>
      <dt>Uptime</dt>
      <dd>{fmtUptime(info.uptime_s)}</dd>
      {#if info.cpu_temp_c !== null}<dt>CPU temp</dt>
        <dd>{info.cpu_temp_c.toFixed(1)} °C</dd>{/if}
      <dt>Config</dt>
      <dd class="mono small">{info.config_path}</dd>
      <dt>State</dt>
      <dd class="mono small">{info.state_dir}</dd>
      <dt>Auth</dt>
      <dd>
        {info.auth_enabled
          ? 'password required'
          : 'off (anyone on your network can change settings)'}
      </dd>
    </dl>
  </div>
  <div class="card stack">
    <h2>Actions</h2>
    <div class="row" style="flex-wrap:wrap">
      <button class="btn" disabled={!!busy} onclick={() => action('test-pattern')}
        >Test pattern</button
      >
      <button class="btn" disabled={!!busy} onclick={() => action('reload-config')}
        >Reload config file</button
      >
      <button
        class="btn"
        disabled={!!busy}
        onclick={() =>
          action('restart-renderer', 'Restart homely? The display goes dark for a few seconds.')}
        >Restart homely</button
      >
    </div>
    <div class="row" style="flex-wrap:wrap">
      <button
        class="btn danger"
        disabled={!!busy}
        onclick={() => action('reboot', 'Reboot the Raspberry Pi?')}>Reboot Pi</button
      >
      <button
        class="btn danger"
        disabled={!!busy}
        onclick={() =>
          action('shutdown', 'Shut down the Raspberry Pi? You will need to unplug and replug it.')}
        >Shut down Pi</button
      >
    </div>
    <p class="muted small">
      Logs: <span class="mono">journalctl -u homely -f</span> · API docs: <a href="/docs">/docs</a>
    </p>
  </div>
{:else}
  <p class="muted"><span class="spin"></span> Loading…</p>
{/if}
