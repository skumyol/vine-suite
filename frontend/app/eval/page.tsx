'use client';

import { useState } from 'react';
import { BarChart3, Loader2, Play, Zap, AlertCircle } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { evaluatePipelines, evaluatePipelinesQuick } from '@/lib/api';
import { PipelineEvalResponse } from '@/lib/types';

export default function EvalPage() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<PipelineEvalResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runQuickEval = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await evaluatePipelinesQuick();
      setResults(response);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Evaluation failed';
      setError(msg);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const runFullEval = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await evaluatePipelines();
      setResults(response);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Evaluation failed';
      setError(msg);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const getVerdictColor = (verdict: string) => {
    switch (verdict) {
      case 'PASS': return 'success';
      case 'REVIEW': return 'warning';
      case 'FAIL': return 'destructive';
      default: return 'secondary';
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pipeline Evaluation"
        description="Compare analyzer pipeline performance across different modes and configurations."
        actions={
          <>
            <Button variant="outline" onClick={runQuickEval} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Zap className="h-4 w-4 mr-2" />}
              Quick Eval
            </Button>
            <Button onClick={runFullEval} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Play className="h-4 w-4 mr-2" />}
              Full Evaluation
            </Button>
          </>
        }
      />

      {error && (
        <Card className="border-danger">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-danger">
              <AlertCircle className="h-4 w-4" />
              <p className="text-sm">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {results?.summary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Evaluation Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 rounded-lg bg-bg-subtle">
                <p className="text-2xl font-semibold">{results.summary.total}</p>
                <p className="text-xs text-fg-muted">Total Evaluations</p>
              </div>
              <div className="p-4 rounded-lg bg-bg-subtle">
                <p className="text-2xl font-semibold">{Math.round(results.summary.avg_confidence * 100)}%</p>
                <p className="text-xs text-fg-muted">Avg Confidence</p>
              </div>
              <div className="p-4 rounded-lg bg-bg-subtle">
                <p className="text-2xl font-semibold">{Math.round(results.summary.avg_processing_time_ms)}ms</p>
                <p className="text-xs text-fg-muted">Avg Processing Time</p>
              </div>
              <div className="p-4 rounded-lg bg-bg-subtle">
                <p className="text-2xl font-semibold">
                  {Object.keys(results.summary.by_verdict).length}
                </p>
                <p className="text-xs text-fg-muted">Unique Verdicts</p>
              </div>
            </div>

            {results.summary.by_verdict && (
              <div className="mt-6 pt-6 border-t border-border">
                <p className="text-sm font-medium mb-3">Verdict Distribution</p>
                <div className="flex gap-2">
                  {Object.entries(results.summary.by_verdict).map(([verdict, count]) => (
                    <Badge key={verdict} variant={getVerdictColor(verdict)} className="text-sm">
                      {verdict}: {count as number}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {results?.results && results.results.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Results</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-xs font-medium text-fg-muted border-b border-border">
                    <th className="text-left py-2 px-3">Pipeline</th>
                    <th className="text-left py-2 px-3">SKU</th>
                    <th className="text-left py-2 px-3">Verdict</th>
                    <th className="text-left py-2 px-3">Confidence</th>
                    <th className="text-left py-2 px-3">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {results.results.map((result, i) => (
                    <tr key={i} className="text-sm">
                      <td className="py-3 px-3 font-mono text-xs">{result.pipeline_id}</td>
                      <td className="py-3 px-3 max-w-xs truncate">{result.sku}</td>
                      <td className="py-3 px-3">
                        <Badge variant={getVerdictColor(result.verdict)}>{result.verdict}</Badge>
                      </td>
                      <td className="py-3 px-3">{Math.round(result.confidence * 100)}%</td>
                      <td className="py-3 px-3 text-fg-muted">{result.processing_time_ms}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {!results && (
        <Card className="h-64 flex items-center justify-center">
          <div className="text-center text-fg-muted">
            <BarChart3 className="h-8 w-8 mx-auto mb-2" />
            <p>Run an evaluation to see pipeline comparison results</p>
          </div>
        </Card>
      )}
    </div>
  );
}
