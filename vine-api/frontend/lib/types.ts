/** TypeScript types for Vine API */

export interface AnalyzeRequest {
  sku: string;
  analyzer_mode?: 'ocr' | 'vlm' | 'hybrid_fast' | 'hybrid_strict';
}

export interface BatchAnalyzeRequest {
  skus: string[];
  analyzer_mode?: 'ocr' | 'vlm' | 'hybrid_fast' | 'hybrid_strict';
}

export interface Candidate {
  image_url: string;
  source: string;
  score: number;
  verdict: 'PASS' | 'REVIEW' | 'FAIL';
}

export interface AnalyzeResult {
  sku: string;
  parsed_wine: {
    producer?: string;
    wine_name?: string;
    vintage?: string;
    appellation?: string;
  };
  selected_image: string | null;
  confidence: number;
  verdict: 'PASS' | 'REVIEW' | 'FAIL' | 'NO_IMAGE';
  reasoning: string;
  candidates: Candidate[];
  analyzer_mode: string;
  processing_time_ms: number;
}

export interface AnalyzeResponse {
  result: AnalyzeResult;
}

export interface BatchAnalyzeResponse {
  results: AnalyzeResult[];
  summary: {
    total: number;
    pass: number;
    review: number;
    fail: number;
    no_image: number;
    average_confidence: number;
  };
}

export interface AnalyzerMode {
  id: string;
  name: string;
  description: string;
  providers: {
    searcher: string;
    analyzer: string;
  };
}

export interface ModesResponse {
  modes: AnalyzerMode[];
  default: string;
}

export interface PipelineResult {
  pipeline_id: string;
  sku: string;
  verdict: 'PASS' | 'REVIEW' | 'FAIL' | 'NO_IMAGE';
  confidence: number;
  processing_time_ms: number;
}

export interface PipelineEvalResponse {
  results: PipelineResult[];
  summary: {
    total: number;
    by_verdict: Record<string, number>;
    avg_confidence: number;
    avg_processing_time_ms: number;
  };
}

export interface HealthStatus {
  status: 'ok' | 'error' | 'degraded';
  message?: string;
}

export interface ProviderHealth {
  name: string;
  type: 'searcher' | 'analyzer' | 'ocr';
  status: 'healthy' | 'unhealthy' | 'unknown';
  latency_ms?: number;
  error?: string;
}

export interface ProvidersHealthResponse {
  providers: ProviderHealth[];
  summary: {
    total: number;
    healthy: number;
    unhealthy: number;
  };
}
