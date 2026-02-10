/** TypeScript types matching the backend Pydantic models. */

export type Phase = 'idle' | 'uploading' | 'running' | 'done' | 'error';

export interface MatchStats {
  total_peaks: number;
  matched_peaks: number;
  unmatched_peaks: number;
  total_match_rows: number;
  avg_matches_per_peak: number;
  match_rate: number;
}

export interface SampleRow {
  sample: string;
  total_peaks: number;
  matched: number;
  match_rate: number;
}

export interface ShiftRow {
  sample: string;
  shift_median: number;
  shift_mean: number;
  shift_std: number;
  n_peaks: number;
  assessment: string;
}

export interface HistogramData {
  values: number[];
  bin_count: number;
}

export interface CompositionCount {
  composition: string;
  count: number;
}

export interface CompleteResult {
  type: 'complete';
  session_id: string;
  stats: MatchStats;
  per_sample: SampleRow[];
  shifts: ShiftRow[];
  ppm_distribution: HistogramData;
  confidence_distribution: HistogramData;
  composition_counts: CompositionCount[];
  downloads: string[];
}

export interface ProgressEvent {
  type: 'progress';
  step: number;
  total_steps: number;
  label: string;
  status: string;
}

export interface StepCompleteEvent {
  type: 'step_complete';
  step: number;
  total_steps: number;
  label: string;
  status: string;
  detail: string;
}

export interface ErrorEvent {
  type: 'error';
  step: number | null;
  message: string;
}

export type WsMessage = ProgressEvent | StepCompleteEvent | ErrorEvent | CompleteResult;

export interface StepState {
  step: number;
  label: string;
  status: 'pending' | 'running' | 'done' | 'error';
  detail: string;
}

export interface SessionState {
  phase: Phase;
  sessionId: string | null;
  steps: StepState[];
  result: CompleteResult | null;
  error: string | null;
}
