export interface ApiError {
  path: string;
  message: string;
  type: string;
}
export interface ApiErrors {
  errors: ApiError[];
}

export type JsonSchema = Record<string, any>;

export interface ModuleCatalogEntry {
  id: string;
  name: string;
  description: string;
  tier: 'need' | 'want' | 'cool';
  icon: string | null;
  supports_portrait: boolean;
  default_duration_s: number;
  allow_multiple: boolean;
  supported_sizes: string[];
  supports_current_size: boolean;
  schema: JsonSchema;
  defaults: Record<string, unknown>;
}

export interface RotationItem {
  instance_id: string;
  module: string;
  name: string;
  enabled: boolean;
  duration_s: number | null;
  effective_duration_s: number;
  settings: Record<string, unknown>;
  status: 'ok' | 'error' | 'disabled' | 'unavailable';
  last_error: string | null;
  is_current: boolean;
  is_idle: boolean;
}

export interface SettingsPayload {
  rotation: Record<string, unknown>;
  brightness: Record<string, unknown>;
  location: Record<string, unknown>;
  schema: Record<'rotation' | 'brightness' | 'location', JsonSchema>;
}

export interface HardwarePayload {
  panel: Record<string, unknown>;
  display: Record<string, unknown>;
  web: Record<string, unknown>;
  schema: Record<'panel' | 'display' | 'web', JsonSchema>;
  requires_restart: boolean;
  restart_pending: boolean;
}

export interface SystemInfo {
  version: string;
  hostname: string;
  ip_addresses: string[];
  uptime_s: number;
  started_at: number;
  backend: string;
  hardware_available: boolean;
  size: string;
  orientation: string;
  cpu_temp_c: number | null;
  python: string;
  platform: string;
  config_path: string;
  state_dir: string;
  auth_enabled: boolean;
  restart_pending: boolean;
  render_fps: number;
  target_fps: number;
  last_error: string | null;
}

export interface StateInfo {
  phase: string;
  current: string | null;
  current_module: string | null;
  pinned: string | null;
  takeover: string | null;
  slot_elapsed: number;
  slot_duration: number;
  brightness: number;
  fps: number;
  rotation: string[];
  restart_pending?: boolean;
}

export interface ActionResult {
  ok: boolean;
  message: string;
}

export interface GeocodeResult {
  name: string;
  admin1: string | null;
  country: string | null;
  latitude: number;
  longitude: number;
  timezone: string | null;
  label: string;
}

export interface TransitChoice {
  id: string;
  label: string;
}

export interface LogLine {
  ts: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  logger: string;
  message: string;
}
