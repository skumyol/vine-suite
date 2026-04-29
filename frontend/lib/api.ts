/** API client for Vine API */

import {
  AnalyzeRequest,
  AnalyzeResponse,
  BatchAnalyzeRequest,
  BatchAnalyzeResponse,
  ModesResponse,
  PipelineEvalResponse,
  ProvidersHealthResponse,
} from './types';

// Base path for API calls (empty in dev, /vine in production with nginx)
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || '';

// API base path - matches backend /api/v1/ routes
const API_BASE = `${BASE_PATH}/api/v1`;

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  console.log('[API] Fetching:', url); // Debug logging
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API error: ${response.status} - ${error}`);
  }

  return response.json();
}

/** Analyze a single SKU */
export async function analyzeSku(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  return fetchApi<AnalyzeResponse>('/analyze', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/** Analyze multiple SKUs in batch */
export async function analyzeBatch(request: BatchAnalyzeRequest): Promise<BatchAnalyzeResponse> {
  return fetchApi<BatchAnalyzeResponse>('/batch', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/** List available analyzer modes */
export async function listModes(): Promise<ModesResponse> {
  return fetchApi<ModesResponse>('/modes');
}

/** Evaluate pipelines (quick) */
export async function evaluatePipelinesQuick(): Promise<PipelineEvalResponse> {
  return fetchApi<PipelineEvalResponse>('/eval/pipelines/quick');
}

/** Evaluate all pipelines */
export async function evaluatePipelines(modes?: string[]): Promise<PipelineEvalResponse> {
  const params = new URLSearchParams();
  if (modes && modes.length > 0) {
    params.append('modes', modes.join(','));
  }
  return fetchApi<PipelineEvalResponse>(`/eval/pipelines?${params.toString()}`);
}

/** Get provider health status */
export async function getProviderHealth(): Promise<ProvidersHealthResponse> {
  return fetchApi<ProvidersHealthResponse>('/health/providers');
}

/** Basic health check */
export async function healthCheck(): Promise<{ status: string }> {
  return fetchApi<{ status: string }>('/health');
}
