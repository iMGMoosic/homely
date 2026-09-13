<script lang="ts">
  let {
    checked = $bindable(false),
    disabled = false,
    label = '',
    onchange,
  }: {
    checked?: boolean;
    disabled?: boolean;
    label?: string;
    onchange?: (v: boolean) => void;
  } = $props();
</script>

<button
  type="button"
  class="toggle"
  role="switch"
  aria-checked={checked}
  aria-label={label}
  {disabled}
  onclick={() => {
    checked = !checked;
    onchange?.(checked);
  }}
>
  <span class="knob"></span>
</button>

<style>
  .toggle {
    width: 46px;
    height: 28px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--bg-elev-2);
    position: relative;
    padding: 0;
    transition: background 0.15s;
    flex: none;
  }
  .toggle[aria-checked='true'] {
    background: var(--accent);
    border-color: var(--accent);
  }
  .toggle:disabled {
    opacity: 0.5;
  }
  .knob {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #fff;
    transition: transform 0.15s;
  }
  .toggle[aria-checked='true'] .knob {
    transform: translateX(18px);
  }
</style>
