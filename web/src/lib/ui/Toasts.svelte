<script lang="ts">
  import { toasts } from './toast.svelte';
</script>

<div class="toasts" aria-live="polite">
  {#each toasts.items as t (t.id)}
    <div class="toast {t.kind}">{t.text}</div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed;
    top: 0.75rem;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    z-index: 50;
    pointer-events: none;
    width: min(92vw, 420px);
  }
  .toast {
    background: var(--bg-elev-2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.6rem 0.9rem;
    font-size: 0.92rem;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
  }
  .toast.ok {
    border-color: var(--ok);
  }
  .toast.warn {
    border-color: var(--accent-2);
  }
  .toast.bad {
    border-color: var(--danger);
  }
</style>
