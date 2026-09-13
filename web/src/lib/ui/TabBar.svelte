<script lang="ts">
  import { router, navigate } from '../../router.svelte';
  import { status } from '../../stores/status.svelte';

  const tabs = [
    { name: 'dashboard', path: '/', label: 'Home', icon: '⌂' },
    { name: 'modules', path: '/modules', label: 'Modules', icon: '▦' },
    { name: 'display', path: '/display', label: 'Display', icon: '☼' },
    { name: 'system', path: '/system', label: 'System', icon: '⚙' },
  ];
  const active = $derived(router.route.name === 'module' ? 'modules' : router.route.name);
</script>

<nav class="tabbar" aria-label="Main">
  <div class="brand">
    <span class="logo" aria-hidden="true"></span>
    <span class="name">homely</span>
    <span
      class="dot"
      class:on={status.connected}
      title={status.connected ? 'connected' : 'disconnected'}
    ></span>
  </div>
  {#each tabs as t}
    <button class="tab" class:active={active === t.name} onclick={() => navigate(t.path)}>
      <span class="icon" aria-hidden="true">{t.icon}</span>
      <span class="label">{t.label}</span>
    </button>
  {/each}
</nav>

<style>
  .tabbar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    height: calc(var(--tab-h) + env(safe-area-inset-bottom));
    padding-bottom: env(safe-area-inset-bottom);
    background: color-mix(in srgb, var(--bg-elev) 94%, transparent);
    backdrop-filter: blur(10px);
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: space-around;
    z-index: 20;
  }
  .brand {
    display: none;
  }
  .tab {
    flex: 1;
    background: none;
    border: none;
    color: var(--text-dim);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.15rem;
    font-size: 0.72rem;
  }
  .tab .icon {
    font-size: 1.25rem;
    line-height: 1;
  }
  .tab.active {
    color: var(--accent);
  }
  @media (min-width: 900px) {
    .tabbar {
      top: 0;
      bottom: 0;
      right: auto;
      width: 220px;
      height: auto;
      flex-direction: column;
      justify-content: flex-start;
      border-top: none;
      border-right: 1px solid var(--border);
      padding: 1rem 0.75rem;
      gap: 0.25rem;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem 0.75rem 1.25rem;
      font-weight: 700;
      font-size: 1.1rem;
    }
    .logo {
      width: 14px;
      height: 14px;
      border-radius: 3px;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--danger);
      margin-left: auto;
    }
    .dot.on {
      background: var(--ok);
    }
    .tab {
      flex: 0 0 auto;
      flex-direction: row;
      justify-content: flex-start;
      gap: 0.6rem;
      padding: 0.6rem 0.75rem;
      border-radius: 10px;
      font-size: 0.95rem;
    }
    .tab.active {
      background: var(--bg-elev-2);
    }
    .tab .icon {
      font-size: 1.1rem;
      width: 1.4rem;
      text-align: center;
    }
  }
</style>
