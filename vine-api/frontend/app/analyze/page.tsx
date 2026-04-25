'use client';

import { useState } from 'react';
import { ScanSearch, Loader2, Image as ImageIcon, AlertCircle } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { analyzeSku, listModes } from '@/lib/api';
import { AnalyzeResult } from '@/lib/types';

export default function AnalyzePage() {
  const [sku, setSku] = useState('');
  const [mode, setMode] = useState('hybrid_fast');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sku.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await analyzeSku({ sku: sku.trim(), analyzer_mode: mode as any });
      setResult(response.result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
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
        title="Analyze Wine SKU"
        description="Analyze a single wine SKU to find and verify bottle images."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">SKU Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex gap-3">
              <Input
                placeholder="Enter wine SKU (e.g., Domaine Leflaive Puligny-Montrachet 2020)"
                value={sku}
                onChange={(e) => setSku(e.target.value)}
                className="flex-1"
              />
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                className="px-3 py-2 rounded-md border border-border bg-surface text-sm"
              >
                <option value="hybrid_fast">Hybrid Fast</option>
                <option value="hybrid_strict">Hybrid Strict</option>
                <option value="ocr">OCR Only</option>
                <option value="vlm">VLM Only</option>
              </select>
              <Button type="submit" disabled={loading || !sku.trim()}>
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ScanSearch className="h-4 w-4" />
                )}
                Analyze
              </Button>
            </div>
          </form>

          {error && (
            <div className="mt-4 p-4 rounded-md bg-danger-soft text-danger flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Analysis Result</CardTitle>
            <Badge variant={getVerdictColor(result.verdict)}>{result.verdict}</Badge>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Parsed Info */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-fg-muted uppercase">Producer</p>
                <p className="text-sm font-medium">{result.parsed_wine.producer || 'N/A'}</p>
              </div>
              <div>
                <p className="text-xs text-fg-muted uppercase">Wine</p>
                <p className="text-sm font-medium">{result.parsed_wine.wine_name || 'N/A'}</p>
              </div>
              <div>
                <p className="text-xs text-fg-muted uppercase">Vintage</p>
                <p className="text-sm font-medium">{result.parsed_wine.vintage || 'N/A'}</p>
              </div>
              <div>
                <p className="text-xs text-fg-muted uppercase">Confidence</p>
                <p className="text-sm font-medium">{Math.round(result.confidence * 100)}%</p>
              </div>
            </div>

            {/* Selected Image */}
            {result.selected_image ? (
              <div>
                <p className="text-xs text-fg-muted uppercase mb-2">Selected Image</p>
                <div className="relative aspect-video max-w-md rounded-lg overflow-hidden border border-border">
                  <img
                    src={result.selected_image}
                    alt="Selected wine bottle"
                    className="w-full h-full object-contain bg-bg-subtle"
                  />
                </div>
              </div>
            ) : (
              <div className="p-8 rounded-lg border border-dashed border-border bg-bg-subtle/50 text-center">
                <ImageIcon className="h-8 w-8 text-fg-muted mx-auto mb-2" />
                <p className="text-sm text-fg-muted">No image selected</p>
                <p className="text-xs text-fg-subtle mt-1">{result.reasoning}</p>
              </div>
            )}

            {/* Reasoning */}
            <div>
              <p className="text-xs text-fg-muted uppercase mb-1">Reasoning</p>
              <p className="text-sm text-fg">{result.reasoning}</p>
            </div>

            {/* Candidates */}
            {result.candidates.length > 0 && (
              <div>
                <p className="text-xs text-fg-muted uppercase mb-3">Top Candidates ({result.candidates.length})</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {result.candidates.slice(0, 4).map((candidate, i) => (
                    <div key={i} className="space-y-1">
                      <div className="aspect-square rounded-md overflow-hidden border border-border bg-bg-subtle">
                        <img
                          src={candidate.image_url}
                          alt={`Candidate ${i + 1}`}
                          className="w-full h-full object-cover"
                        />
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-fg-subtle">{candidate.source}</span>
                        <Badge variant={getVerdictColor(candidate.verdict)} className="text-[10px]">
                          {Math.round(candidate.score * 100)}%
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Processing Info */}
            <div className="pt-4 border-t border-border">
              <div className="flex items-center gap-4 text-xs text-fg-muted">
                <span>Mode: <span className="text-fg">{result.analyzer_mode}</span></span>
                <span>Time: <span className="text-fg">{result.processing_time_ms}ms</span></span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
