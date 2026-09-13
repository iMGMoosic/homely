import { connect, type ReconnectingSocket } from '../api/ws';
import type { StateInfo } from '../api/types';
import { toast } from '../lib/ui/toast.svelte';

export const status = $state<{
  state: StateInfo | null;
  connected: boolean;
  restartPending: boolean;
  lastConfigChange: number;
  moduleErrors: Record<string, string>;
}>({ state: null, connected: false, restartPending: false, lastConfigChange: 0, moduleErrors: {} });

let socket: ReconnectingSocket | null = null;

export function startStatus() {
  if (socket) return;
  socket = connect('/api/ws/events', {
    onOpen: () => (status.connected = true),
    onClose: () => (status.connected = false),
    onMessage: (ev) => {
      let msg: any;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      switch (msg.type) {
        case 'status':
          status.state = msg as StateInfo;
          status.restartPending = !!msg.restart_pending;
          break;
        case 'config_changed':
          status.lastConfigChange = Date.now();
          break;
        case 'module_error':
          status.moduleErrors[msg.instance_id] = msg.message;
          toast(`Module ${msg.instance_id} failed: ${msg.message}`, 'bad');
          break;
        case 'restart_requested':
          status.restartPending = true;
          toast('homely is restarting…', 'warn');
          break;
      }
    },
  });
}
