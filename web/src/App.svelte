<script lang="ts">
  import { onMount } from 'svelte';
  import { router } from './router.svelte';
  import { startStatus, status } from './stores/status.svelte';
  import TabBar from './lib/ui/TabBar.svelte';
  import Toasts from './lib/ui/Toasts.svelte';
  import Dashboard from './routes/Dashboard.svelte';
  import Modules from './routes/Modules.svelte';
  import ModuleSettings from './routes/ModuleSettings.svelte';
  import Display from './routes/Display.svelte';
  import System from './routes/System.svelte';

  onMount(startStatus);
</script>

<div class="layout">
  <TabBar />
  <main class="content">
    {#if status.restartPending}
      <div class="banner warn">
        Hardware or web settings changed. Restart homely from the System tab to apply.
      </div>
    {/if}
    {#if router.route.name === 'dashboard'}
      <Dashboard />
    {:else if router.route.name === 'modules'}
      <Modules />
    {:else if router.route.name === 'module'}
      <ModuleSettings id={router.route.params.id} />
    {:else if router.route.name === 'display'}
      <Display />
    {:else if router.route.name === 'system'}
      <System />
    {/if}
  </main>
  <Toasts />
</div>
