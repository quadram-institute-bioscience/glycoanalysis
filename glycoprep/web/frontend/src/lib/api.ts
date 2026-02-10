/** Fetch + WebSocket helpers for the glycoprep API. */

import { session } from './stores';
import type { WsMessage, CompleteResult } from './types';

/** Base path for API requests (works behind nginx /glycoprep/ and in dev). */
const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

/** POST multipart form to /api/upload, returns { session_id, ws_url }. */
export async function uploadFiles(form: FormData): Promise<{ session_id: string; ws_url: string }> {
  const res = await fetch(`${BASE}/api/upload`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Upload failed (${res.status})`);
  }
  return res.json();
}

/** GET /api/session/{sid} — poll session state (fallback). */
export async function pollSession(sid: string): Promise<any> {
  const res = await fetch(`${BASE}/api/session/${sid}`);
  if (!res.ok) {
    throw new Error(`Session not found (${res.status})`);
  }
  return res.json();
}

/** Build the download URL for a result file. */
export function downloadUrl(sid: string, filename: string): string {
  return `${BASE}/api/download/${sid}/${filename}`;
}

/** Connect WebSocket and pipe events into the session store. */
export function connectWs(sid: string): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${location.host}${BASE}/ws/${sid}`);

  ws.onmessage = (event) => {
    const msg: WsMessage = JSON.parse(event.data);

    session.update((s) => {
      if (msg.type === 'progress') {
        const idx = msg.step - 1;
        if (s.steps[idx]) {
          s.steps[idx].status = 'running';
          s.steps[idx].label = msg.label;
        }
      } else if (msg.type === 'step_complete') {
        const idx = msg.step - 1;
        if (s.steps[idx]) {
          s.steps[idx].status = 'done';
          s.steps[idx].detail = msg.detail;
        }
      } else if (msg.type === 'error') {
        s.phase = 'error';
        s.error = msg.message;
        if (msg.step != null) {
          const idx = msg.step - 1;
          if (s.steps[idx]) {
            s.steps[idx].status = 'error';
          }
        }
      } else if (msg.type === 'complete') {
        s.phase = 'done';
        s.result = msg as CompleteResult;
      }
      return s;
    });
  };

  ws.onerror = () => {
    session.update((s) => {
      if (s.phase === 'running') {
        s.phase = 'error';
        s.error = 'WebSocket connection lost. Trying to recover...';
      }
      return s;
    });
    // Attempt fallback poll
    tryFallbackPoll(sid);
  };

  ws.onclose = () => {
    // If still running, attempt fallback poll
    session.update((s) => {
      if (s.phase === 'running') {
        tryFallbackPoll(sid);
      }
      return s;
    });
  };

  return ws;
}

async function tryFallbackPoll(sid: string): Promise<void> {
  // Wait a moment then poll
  await new Promise((r) => setTimeout(r, 2000));
  try {
    const data = await pollSession(sid);
    if (data.status === 'done' && data.result) {
      session.update((s) => {
        s.phase = 'done';
        s.result = data.result;
        return s;
      });
    } else if (data.status === 'error') {
      session.update((s) => {
        s.phase = 'error';
        s.error = data.error || 'Pipeline failed';
        return s;
      });
    }
  } catch {
    // ignore — user can reload
  }
}
