<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../api/client';
  import type { LogLine, SystemInfo } from '../api/types';
  import { status } from '../stores/status.svelte';
  import { toast } from '../lib/ui/toast.svelte';

  let info = $state<SystemInfo | null>(null);
  let busy = $state<string | null>(null);
  let logs = $state<LogLine[]>([]);
  let logLevel = $state<'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'>('INFO');
  let logsOpen = $state(false);
  let logBox: HTMLPreElement | undefined = $state();

  async function loadLogs() {
    if (!logsOpen) return;
    try {
      logs = await api.logs(logLevel, 200);
      requestAnimationFrame(() => logBox && (logBox.scrollTop = logBox.scrollHeight));
    } catch {
      /* transient */
    }
  }

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
    const l = setInterval(loadLogs, 4000);
    return () => {
      clearInterval(t);
      clearInterval(l);
    };
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
      Full logs: <span class="mono">journalctl -u homely -f</span> · API docs:
      <a href="/docs">/docs</a>
    </p>
  </div>
  <details class="card" bind:open={logsOpen} ontoggle={loadLogs}>
    <summary
      ><strong>Recent logs</strong>
      <span class="muted small">last 200 lines, refreshes every few seconds</span></summary
    >
    <div class="row" style="margin:0.6rem 0;gap:0.5rem;align-items:center">
      <label class="small" for="log-level">Level</label>
      <select id="log-level" bind:value={logLevel} onchange={loadLogs}>
        <option>DEBUG</option><option>INFO</option><option>WARNING</option><option>ERROR</option>
      </select>
      <button class="btn sm" onclick={loadLogs}>Refresh</button>
    </div>
    <pre class="logs mono small" bind:this={logBox}>{#each logs as ln (ln.ts + ln.message)}<span
          class={'lvl ' + ln.level}>{ln.ts.slice(11, 19)} {ln.level.padEnd(7)}</span
        > {ln.logger}: {ln.message}
      {/each}{#if !logs.length}nothing logged at this level yet{/if}</pre>
  </details>
{:else}
  <p class="muted"><span class="spin"></span> Loading…</p>
{/if}

<style>
  .logs {
    max-height: 22rem;
    overflow: auto;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.6rem;
    white-space: pre-wrap;
    word-break: break-word;
    margin: 0;
  }
  .lvl {
    color: var(--text-dim);
  }
  .lvl.WARNING {
    color: var(--warn, #e0a030);
  }
  .lvl.ERROR {
    color: var(--danger);
  }
  summary {
    cursor: pointer;
    list-style: none;
  }
</style>
