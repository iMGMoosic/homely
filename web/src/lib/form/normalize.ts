import type { JsonSchema } from '../../api/types';

export type Widget =
  | 'text'
  | 'textarea'
  | 'number'
  | 'slider'
  | 'toggle'
  | 'select'
  | 'color'
  | 'secret'
  | 'time'
  | 'timezone'
  | 'string-list'
  | 'object-list'
  | 'object'
  | 'hidden'
  | 'unsupported';

export interface FieldSpec {
  key: string;
  title: string;
  description?: string;
  help?: string;
  widget: Widget;
  type: string;
  nullable: boolean;
  enum?: Array<string | number | boolean>;
  minimum?: number;
  maximum?: number;
  step?: number;
  unit?: string;
  placeholder?: string;
  pattern?: string;
  maxLength?: number;
  group: string;
  order: number;
  default?: unknown;
  children?: FieldSpec[]; // for nested objects
  itemSchema?: JsonSchema;
}

export interface FormSpec {
  groups: Array<{ name: string; fields: FieldSpec[] }>;
  fields: FieldSpec[];
}

function deref(schema: JsonSchema, root: JsonSchema): JsonSchema {
  if (schema && typeof schema.$ref === 'string') {
    const path = schema.$ref.replace(/^#\//, '').split('/');
    let node: any = root;
    for (const p of path) node = node?.[p];
    return {
      ...(node ?? {}),
      ...Object.fromEntries(Object.entries(schema).filter(([k]) => k !== '$ref')),
    };
  }
  return schema;
}

function collapse(schema: JsonSchema, root: JsonSchema): { schema: JsonSchema; nullable: boolean } {
  schema = deref(schema, root);
  const variants: JsonSchema[] | undefined = schema.anyOf ?? schema.oneOf;
  if (variants) {
    const nonNull = variants.filter((v) => v.type !== 'null').map((v) => deref(v, root));
    const nullable = nonNull.length < variants.length;
    if (nonNull.length === 1) {
      const { anyOf, oneOf, ...rest } = schema;
      return { schema: { ...nonNull[0], ...rest }, nullable };
    }
    // Enum-like union of consts
    if (nonNull.every((v) => 'const' in v)) {
      const { anyOf, oneOf, ...rest } = schema;
      return {
        schema: { ...rest, type: typeof nonNull[0].const, enum: nonNull.map((v) => v.const) },
        nullable,
      };
    }
    return { schema, nullable };
  }
  if (Array.isArray(schema.type)) {
    const types = schema.type.filter((t: string) => t !== 'null');
    return { schema: { ...schema, type: types[0] }, nullable: types.length < schema.type.length };
  }
  return { schema, nullable: false };
}

function pickWidget(s: JsonSchema, nullable: boolean): Widget {
  const x = s['x-widget'];
  if (x === 'hidden') return 'hidden';
  if (s.enum) return 'select';
  switch (s.type) {
    case 'boolean':
      return 'toggle';
    case 'integer':
    case 'number':
      if (x === 'slider' && s.minimum !== undefined && s.maximum !== undefined) return 'slider';
      return 'number';
    case 'string':
      if (s.format === 'color' || x === 'color') return 'color';
      if (s.format === 'password' || s.writeOnly) return 'secret';
      if (s.format === 'time' || x === 'time') return 'time';
      if (x === 'timezone') return 'timezone';
      if (x === 'textarea') return 'textarea';
      return 'text';
    case 'array':
      if (s.items && (s.items.type === 'string' || x === 'string-list')) return 'string-list';
      if (s.items && (s.items.type === 'object' || s.items.properties)) return 'object-list';
      return 'unsupported';
    case 'object':
      return s.properties ? 'object' : 'unsupported';
    default:
      return nullable ? 'text' : 'unsupported';
  }
}

function titleFor(key: string, raw: JsonSchema, s: JsonSchema): string {
  // Prefer a title set on the property itself; a $ref'd model's title is its class name.
  if (raw.title) return raw.title;
  if (!raw.$ref && !raw.anyOf && !raw.oneOf && s.title) return s.title;
  return key
    .replace(/_s$/, ' (seconds)')
    .replace(/_/g, ' ')
    .replace(/^\w/, (c) => c.toUpperCase());
}

export function normalize(root: JsonSchema, prefix = ''): FormSpec {
  const props: Record<string, JsonSchema> = root.properties ?? {};
  const fields: FieldSpec[] = [];
  let i = 0;
  for (const [key, raw] of Object.entries(props)) {
    const { schema: s0, nullable } = collapse(raw, root);
    const s = s0.items ? { ...s0, items: { ...deref(s0.items, root), $defs: root.$defs } } : s0;
    const widget = pickWidget(s, nullable);
    const spec: FieldSpec = {
      key: prefix ? `${prefix}.${key}` : key,
      title: titleFor(key, raw, s),
      description: s.description,
      help: s['x-help'],
      widget,
      type: s.type ?? 'string',
      nullable,
      enum: s.enum,
      minimum: s.minimum ?? (s.exclusiveMinimum !== undefined ? s.exclusiveMinimum + 1 : undefined),
      maximum: s.maximum ?? (s.exclusiveMaximum !== undefined ? s.exclusiveMaximum - 1 : undefined),
      step: s.type === 'integer' ? 1 : s.multipleOf,
      unit: s['x-unit'],
      placeholder: s['x-placeholder'],
      pattern: s.pattern,
      maxLength: s.maxLength,
      group: s['x-group'] ?? '',
      order: typeof s['x-order'] === 'number' ? s['x-order'] : 1000 + i,
      default: s.default,
      itemSchema: s.items,
    };
    if (widget === 'object') {
      spec.children = normalize({ ...s, $defs: root.$defs }, spec.key).fields;
    }
    fields.push(spec);
    i++;
  }
  fields.sort((a, b) => a.order - b.order);
  const groupNames: string[] = [];
  for (const f of fields) if (!groupNames.includes(f.group)) groupNames.push(f.group);
  const groups = groupNames.map((name) => ({
    name,
    fields: fields.filter((f) => f.group === name),
  }));
  return { groups, fields };
}

/** Build a default object for an object schema (used when adding list items). */
export function defaultsFor(schema: JsonSchema): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  const spec = normalize(schema);
  for (const f of spec.fields) {
    if (f.default !== undefined) out[f.key] = f.default;
    else if (f.widget === 'toggle') out[f.key] = false;
    else if (f.widget === 'object')
      out[f.key] = defaultsFor({ ...schema.properties?.[f.key], $defs: schema.$defs });
    else if (f.widget === 'string-list' || f.widget === 'object-list') out[f.key] = [];
    else if (f.widget === 'select' && f.enum?.length) out[f.key] = f.enum[0];
    else if (f.type === 'integer' || f.type === 'number') out[f.key] = f.minimum ?? 0;
    else out[f.key] = f.nullable ? null : '';
  }
  return out;
}

export function getPath(obj: any, path: string): unknown {
  return path.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

export function setPath(obj: any, path: string, value: unknown): void {
  const keys = path.split('.');
  let node = obj;
  for (const k of keys.slice(0, -1)) {
    if (node[k] == null || typeof node[k] !== 'object') node[k] = {};
    node = node[k];
  }
  node[keys[keys.length - 1]] = value;
}
