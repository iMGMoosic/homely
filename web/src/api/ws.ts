/** Reconnecting WebSocket helper. */
export function wsUrl(path: string): string {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}${path}`;
}

export interface ReconnectingSocket {
  send(data: string): void;
  close(): void;
  readonly connected: boolean;
}

export function connect(
  path: string,
  handlers: {
    onMessage: (ev: MessageEvent) => void;
    onOpen?: () => void;
    onClose?: () => void;
  },
  binary = false,
): ReconnectingSocket {
  let ws: WebSocket | null = null;
  let closed = false;
  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let connected = false;

  const open = () => {
    if (closed) return;
    ws = new WebSocket(wsUrl(path));
    if (binary) ws.binaryType = 'arraybuffer';
    ws.onopen = () => {
      attempt = 0;
      connected = true;
      handlers.onOpen?.();
    };
    ws.onmessage = handlers.onMessage;
    ws.onclose = () => {
      connected = false;
      handlers.onClose?.();
      if (!closed) {
        const delay = Math.min(10000, 500 * 2 ** attempt++);
        timer = setTimeout(open, delay);
      }
    };
    ws.onerror = () => ws?.close();
  };
  open();

  return {
    send(data: string) {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(data);
    },
    close() {
      closed = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    },
    get connected() {
      return connected;
    },
  };
}
