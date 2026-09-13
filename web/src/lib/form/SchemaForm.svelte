<script lang="ts">
  import type { JsonSchema } from '../../api/types';
  import Field from './Field.svelte';
  import { normalize } from './normalize';

  let {
    schema,
    value = $bindable({}),
    errors = {},
    onchange,
  }: {
    schema: JsonSchema;
    value: Record<string, any>;
    errors?: Record<string, string>;
    onchange?: () => void;
  } = $props();

  const spec = $derived(normalize(schema));
</script>

{#if errors._}<div class="banner bad">{errors._}</div>{/if}
{#each spec.groups as group (group.name)}
  {#if group.name}
    <h3 class="group">{group.name}</h3>
  {/if}
  {#each group.fields as f (f.key)}
    <Field spec={f} bind:value={value[f.key]} error={errors[f.key]} {errors} {onchange} />
  {/each}
{/each}

<style>
  .group {
    margin: 1.25rem 0 0.6rem;
    color: var(--text-dim);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
  }
  .group:first-child {
    margin-top: 0;
  }
</style>
