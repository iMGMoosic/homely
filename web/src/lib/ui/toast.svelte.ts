export type ToastKind = 'ok' | 'warn' | 'bad' | 'info';
export interface Toast {
  id: number;
  text: string;
  kind: ToastKind;
}

export const toasts = $state<{ items: Toast[] }>({ items: [] });
let nextId = 1;

export function toast(text: string, kind: ToastKind = 'info', ms = 3500) {
  const id = nextId++;
  toasts.items = [...toasts.items, { id, text, kind }];
  setTimeout(() => {
    toasts.items = toasts.items.filter((t) => t.id !== id);
  }, ms);
}
