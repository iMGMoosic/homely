import { api } from '../api/client';
import type { ModuleCatalogEntry, RotationItem } from '../api/types';

export const rotation = $state<{
  items: RotationItem[];
  catalog: ModuleCatalogEntry[];
  loaded: boolean;
  error: string | null;
}>({ items: [], catalog: [], loaded: false, error: null });

export async function loadRotation() {
  try {
    const [items, catalog] = await Promise.all([api.rotation(), api.catalog()]);
    rotation.items = items;
    rotation.catalog = catalog;
    rotation.loaded = true;
    rotation.error = null;
  } catch (e: any) {
    rotation.error = e?.message ?? String(e);
  }
}

export function catalogFor(moduleId: string): ModuleCatalogEntry | undefined {
  return rotation.catalog.find((c) => c.id === moduleId);
}

export async function setEnabled(id: string, enabled: boolean) {
  const item = await api.patchInstance(id, { enabled });
  replace(item);
}

export async function setDuration(id: string, duration_s: number | null) {
  const item =
    duration_s === null
      ? await api.patchInstance(id, { clear_duration: true })
      : await api.patchInstance(id, { duration_s });
  replace(item);
}

export async function move(id: string, delta: number) {
  const ids = rotation.items.map((i) => i.instance_id);
  const idx = ids.indexOf(id);
  const to = idx + delta;
  if (idx < 0 || to < 0 || to >= ids.length) return;
  ids.splice(idx, 1);
  ids.splice(to, 0, id);
  rotation.items = await api.reorder(ids);
}

export async function addInstance(moduleId: string) {
  const item = await api.addInstance(moduleId);
  rotation.items = [...rotation.items, item];
  return item;
}

export async function removeInstance(id: string) {
  await api.removeInstance(id);
  rotation.items = rotation.items.filter((i) => i.instance_id !== id);
}

function replace(item: RotationItem) {
  rotation.items = rotation.items.map((i) => (i.instance_id === item.instance_id ? item : i));
}
