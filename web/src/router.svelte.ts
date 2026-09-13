/** Tiny hash router: #/, #/modules, #/modules/:id, #/display, #/system */

export type Route = { name: string; params: Record<string, string> };

const patterns: Array<[RegExp, string, string[]]> = [
  [/^\/?$/, 'dashboard', []],
  [/^\/modules\/?$/, 'modules', []],
  [/^\/modules\/([^/]+)\/?$/, 'module', ['id']],
  [/^\/display\/?$/, 'display', []],
  [/^\/system\/?$/, 'system', []],
];

function parse(hash: string): Route {
  const path = hash.replace(/^#/, '') || '/';
  for (const [re, name, keys] of patterns) {
    const m = path.match(re);
    if (m) {
      const params: Record<string, string> = {};
      keys.forEach((k, i) => (params[k] = decodeURIComponent(m[i + 1])));
      return { name, params };
    }
  }
  return { name: 'dashboard', params: {} };
}

export const router = $state<{ route: Route }>({ route: parse(location.hash) });

window.addEventListener('hashchange', () => {
  router.route = parse(location.hash);
});

export function navigate(path: string) {
  location.hash = path.startsWith('#') ? path : `#${path}`;
}
