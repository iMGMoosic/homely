/** Deep-clone plain JSON data (settings objects). Works on Svelte $state proxies too. */
export function clone<T>(value: T): T {
  return value === undefined ? value : (JSON.parse(JSON.stringify(value)) as T);
}
