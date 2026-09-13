<script lang="ts">
  import { defaultsFor, normalize, type FieldSpec } from './normalize';
  import Toggle from '../ui/Toggle.svelte';
  import Self from './Field.svelte';

  let {
    spec,
    value = $bindable(),
    error = undefined,
    errors = {},
    onchange,
  }: {
    spec: FieldSpec;
    value: any;
    error?: string;
    errors?: Record<string, string>;
    onchange?: () => void;
  } = $props();

  const id = $derived(`f-${spec.key.replace(/\./g, '-')}`);
  const isSecretSet = $derived(value && typeof value === 'object' && value.$secret === true);
  let secretDraft = $state('');
  let listDraft = $state('');
  const TIMEZONES = (Intl as any).supportedValuesOf
    ? ((Intl as any).supportedValuesOf('timeZone') as string[])
    : [];

  function num(e: Event) {
    const t = e.target as HTMLInputElement;
    if (t.value === '') {
      value = spec.nullable ? null : value;
    } else {
      const n = Number(t.value);
      value = spec.type === 'integer' ? Math.round(n) : n;
    }
    onchange?.();
  }
  function str(e: Event) {
    const t = e.target as HTMLInputElement | HTMLTextAreaElement;
    value = t.value === '' && spec.nullable ? null : t.value;
    onchange?.();
  }
  function addListItem() {
    const items = listDraft
      .split(/\n+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (!items.length) return;
    value = [...(Array.isArray(value) ? value : []), ...items];
    listDraft = '';
    onchange?.();
  }
  const itemFields = $derived(
    spec.widget === 'object-list' && spec.itemSchema ? normalize(spec.itemSchema).fields : [],
  );
  function addObjectItem() {
    value = [...(Array.isArray(value) ? value : []), defaultsFor(spec.itemSchema ?? {})];
    onchange?.();
  }
  function removeListItem(i: number) {
    value = (value as string[]).filter((_, j) => j !== i);
    onchange?.();
  }
</script>

{#if spec.widget === 'hidden'}
  <!-- nothing -->
{:else if spec.widget === 'object'}
  <fieldset class="nested">
    <legend>{spec.title}</legend>
    {#if spec.description}<p class="help">{spec.description}</p>{/if}
    {#each spec.children ?? [] as child (child.key)}
      <Self
        spec={child}
        bind:value={value[child.key.split('.').pop()!]}
        error={errors[child.key]}
        {errors}
        {onchange}
      />
    {/each}
  </fieldset>
{:else}
  <div class="field" class:inline={spec.widget === 'toggle'}>
    <label for={id}>
      {spec.title}
      {#if spec.description && spec.widget === 'toggle'}<div class="help">
          {spec.description}
        </div>{/if}
    </label>

    {#if spec.widget === 'toggle'}
      <Toggle bind:checked={value} label={spec.title} onchange={() => onchange?.()} />
    {:else if spec.widget === 'select'}
      <select
        {id}
        class="input"
        class:invalid={!!error}
        value={value == null ? '' : String(value)}
        onchange={(e) => {
          const raw = (e.target as HTMLSelectElement).value;
          const match = spec.enum?.find((o) => String(o) === raw);
          value = raw === '' ? null : (match ?? raw);
          onchange?.();
        }}
      >
        {#if spec.nullable}<option value="">—</option>{/if}
        {#each spec.enum ?? [] as opt}
          <option value={String(opt)}>{String(opt).replace(/_/g, ' ')}</option>
        {/each}
      </select>
    {:else if spec.widget === 'slider'}
      <div class="range-row">
        <input
          {id}
          type="range"
          min={spec.minimum}
          max={spec.maximum}
          step={spec.step ?? 1}
          value={value ?? spec.minimum}
          oninput={num}
        />
        <output>{value}{spec.unit ?? ''}</output>
      </div>
    {:else if spec.widget === 'number'}
      <input
        {id}
        type="number"
        class="input"
        class:invalid={!!error}
        inputmode={spec.type === 'integer' ? 'numeric' : 'decimal'}
        min={spec.minimum}
        max={spec.maximum}
        step={spec.step ?? 'any'}
        value={value ?? ''}
        placeholder={spec.placeholder}
        oninput={num}
      />
    {:else if spec.widget === 'color'}
      <div class="row">
        <input
          type="color"
          value={typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value) ? value : '#000000'}
          oninput={(e) => {
            value = (e.target as HTMLInputElement).value.toUpperCase();
            onchange?.();
          }}
          aria-label="{spec.title} picker"
        />
        <input
          {id}
          type="text"
          class="input mono"
          class:invalid={!!error}
          value={value ?? ''}
          maxlength="7"
          placeholder="#RRGGBB"
          oninput={(e) => {
            value = (e.target as HTMLInputElement).value.toUpperCase();
            onchange?.();
          }}
        />
      </div>
    {:else if spec.widget === 'secret'}
      <div class="row">
        <input
          {id}
          type="password"
          class="input grow"
          class:invalid={!!error}
          autocomplete="off"
          placeholder={isSecretSet ? '•••••••• (saved; leave blank to keep)' : 'not set'}
          bind:value={secretDraft}
          oninput={() => {
            value = secretDraft === '' ? (isSecretSet ? { $secret: true } : null) : secretDraft;
            onchange?.();
          }}
        />
        {#if isSecretSet}
          <button
            type="button"
            class="btn sm"
            onclick={() => {
              value = null;
              secretDraft = '';
              onchange?.();
            }}>Clear</button
          >
        {/if}
      </div>
    {:else if spec.widget === 'time'}
      <input
        {id}
        type="time"
        class="input"
        class:invalid={!!error}
        value={value ?? ''}
        oninput={str}
      />
    {:else if spec.widget === 'timezone'}
      <input
        {id}
        type="text"
        class="input"
        class:invalid={!!error}
        list="{id}-tz"
        value={value ?? ''}
        placeholder="System timezone"
        oninput={str}
      />
      <datalist id="{id}-tz">
        {#each TIMEZONES as tz}<option value={tz}></option>{/each}
      </datalist>
    {:else if spec.widget === 'string-list'}
      <ul class="string-list">
        {#each Array.isArray(value) ? value : [] as item, i}
          <li class="row">
            <span class="grow mono small">{item}</span>
            <button
              type="button"
              class="btn sm icon"
              aria-label="Remove"
              onclick={() => removeListItem(i)}>✕</button
            >
          </li>
        {/each}
      </ul>
      <div class="row">
        <input
          type="text"
          class="input grow"
          placeholder={spec.placeholder ?? 'Add an item'}
          bind:value={listDraft}
          onkeydown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              addListItem();
            }
          }}
        />
        <button type="button" class="btn sm" onclick={addListItem}>Add</button>
      </div>
    {:else if spec.widget === 'object-list'}
      <div class="stack">
        {#each Array.isArray(value) ? value : [] as _item, i (i)}
          <div class="item">
            <div class="row between" style="margin-bottom:0.4rem">
              <span class="muted small">#{i + 1}</span>
              <button
                type="button"
                class="btn sm icon"
                aria-label="Remove"
                onclick={() => removeListItem(i)}>✕</button
              >
            </div>
            {#each itemFields as child (child.key)}
              <Self
                spec={child}
                bind:value={value[i][child.key]}
                error={errors[`${spec.key}.${i}.${child.key}`]}
                {errors}
                {onchange}
              />
            {/each}
          </div>
        {/each}
        <button type="button" class="btn sm" onclick={addObjectItem}>+ Add</button>
      </div>
    {:else if spec.widget === 'textarea'}
      <textarea
        {id}
        class="input"
        class:invalid={!!error}
        rows="3"
        value={value ?? ''}
        oninput={str}></textarea>
    {:else if spec.widget === 'text'}
      <input
        {id}
        type="text"
        class="input"
        class:invalid={!!error}
        value={value ?? ''}
        maxlength={spec.maxLength}
        placeholder={spec.placeholder}
        oninput={str}
      />
    {:else}
      <div class="banner warn">
        Unsupported setting type for “{spec.title}”. Edit it in the config file.
      </div>
    {/if}

    {#if spec.description && spec.widget !== 'toggle'}<div class="help">
        {spec.description}
      </div>{/if}
    {#if spec.help}<div class="help">{spec.help}</div>{/if}
    {#if error}<div class="error">{error}</div>{/if}
  </div>
{/if}

<style>
  .nested {
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.75rem 0.9rem 0;
    margin: 0 0 1rem;
  }
  legend {
    padding: 0 0.4rem;
    font-weight: 600;
  }
  input[type='color'] {
    width: 44px;
    height: 40px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg);
    padding: 2px;
  }
  .string-list {
    list-style: none;
    margin: 0 0 0.4rem;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .item {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.6rem 0.75rem 0;
  }
  .string-list li {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.3rem 0.3rem 0.3rem 0.7rem;
  }
</style>
