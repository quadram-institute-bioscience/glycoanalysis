/** Svelte writable store for session state. */

import { writable } from 'svelte/store';
import type { SessionState, StepState } from './types';

const INITIAL_STEPS: StepState[] = [
  { step: 1, label: 'Reading peaks file', status: 'pending', detail: '' },
  { step: 2, label: 'Reading metadata', status: 'pending', detail: '' },
  { step: 3, label: 'Joining metadata', status: 'pending', detail: '' },
  { step: 4, label: 'Applying S/N filter', status: 'pending', detail: '' },
  { step: 5, label: 'Matching peaks to glycans', status: 'pending', detail: '' },
  { step: 6, label: 'Calibration shift correction', status: 'pending', detail: '' },
  { step: 7, label: 'Writing output files', status: 'pending', detail: '' },
];

function createInitialState(): SessionState {
  return {
    phase: 'idle',
    sessionId: null,
    steps: INITIAL_STEPS.map((s) => ({ ...s })),
    result: null,
    error: null,
  };
}

export const session = writable<SessionState>(createInitialState());

export function resetSession(): void {
  session.set(createInitialState());
}
