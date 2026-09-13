import type {
  ActionResult,
  ApiErrors,
  HardwarePayload,
  ModuleCatalogEntry,
  RotationItem,
  SettingsPayload,
  StateInfo,
  SystemInfo,
} from './types';

export class ApiRequestError extends Error {
  status: number;
  errors: Record<string, string>;
  constructor(status: number, message: string, errors: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.errors = errors;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    if (res.status === 422 && data && Array.isArray((data as ApiErrors).errors)) {
      const errs: Record<string, string> = {};
      for (const e of (data as ApiErrors).errors) errs[e.path || '_'] = e.message;
      throw new ApiRequestError(422, 'Please fix the highlighted fields.', errs);
    }
    const detail =
      data && typeof data === 'object' && 'detail' in data ? String(data.detail) : res.statusText;
    throw new ApiRequestError(res.status, detail || `HTTP ${res.status}`);
  }
  return data as T;
}

export const api = {
  catalog: () => request<ModuleCatalogEntry[]>('GET', '/api/modules'),
  rotation: () => request<RotationItem[]>('GET', '/api/rotation'),
  instance: (id: string) => request<RotationItem>('GET', `/api/rotation/${encodeURIComponent(id)}`),
  addInstance: (module: string) => request<RotationItem>('POST', '/api/rotation', { module }),
  removeInstance: (id: string) =>
    request<void>('DELETE', `/api/rotation/${encodeURIComponent(id)}`),
  patchInstance: (
    id: string,
    patch: { enabled?: boolean; duration_s?: number | null; clear_duration?: boolean },
  ) => request<RotationItem>('PATCH', `/api/rotation/${encodeURIComponent(id)}`, patch),
  saveSettings: (id: string, settings: Record<string, unknown>) =>
    request<RotationItem>('PUT', `/api/rotation/${encodeURIComponent(id)}/settings`, settings),
  reorder: (order: string[]) => request<RotationItem[]>('PUT', '/api/rotation/order', { order }),
  pin: (id: string, pinned: boolean) =>
    request<void>('POST', `/api/rotation/${encodeURIComponent(id)}/pin`, { pinned }),
  settings: () => request<SettingsPayload>('GET', '/api/settings'),
  saveGlobalSettings: (
    body: Partial<Pick<SettingsPayload, 'rotation' | 'brightness' | 'location'>>,
  ) => request<SettingsPayload>('PUT', '/api/settings', body),
  setBrightness: (level: number) => request<StateInfo>('PUT', '/api/brightness', { level }),
  hardware: () => request<HardwarePayload>('GET', '/api/hardware'),
  saveHardware: (body: Partial<Pick<HardwarePayload, 'panel' | 'display' | 'web'>>) =>
    request<HardwarePayload>('PUT', '/api/hardware', body),
  system: () => request<SystemInfo>('GET', '/api/system'),
  state: () => request<StateInfo>('GET', '/api/state'),
  action: (name: string) => request<ActionResult>('POST', `/api/system/actions/${name}`),
};
