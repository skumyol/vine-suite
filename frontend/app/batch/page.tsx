'use client';

import { useState } from 'react';
import { Layers, Loader2, Plus, Trash2, AlertCircle } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { analyzeBatch } from '@/lib/api';
import { AnalyzeResult } from '@/lib/types';

export default function BatchPage() {
  const [skus, setSkus] = useState<string[]>(['']);
  const [mode, setMode] = useState('hybrid_fast');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<AnalyzeResult[] | null>(null);
  const [summary, setSummary] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const addSku = () => setSkus([...skus, '']);
  const removeSku = (index: number) => setSkus(skus.filter((_, i) => i !== index));
  const updateSku = (index: number, value: string) => {
    const newSkus = [...skus];
    newSkus[index] = value;
    setSkus(newSkus);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validSkus = skus.filter(s => s.trim());
    if (validSkus.length === 0) return;

    setLoading(true);
    setResults(null);
    setSummary(null);
    setError(null);

    try {
      const response = await analyzeBatch({
        skus: validSkus,
        analyzer_mode: mode as any
      });
      setResults(response.results);
      setSummary(response.summary);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Batch analysis failed';
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
        title="Batch Analysis"
        description="Analyze multiple wine SKUs in a single batch job."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Input Panel */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Layers className="h-4 w-4" />
                SKUs to Analyze
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {skus.map((sku, index) => (
                    <div key={index} className="flex gap-2">
                      <Input
                        placeholder={`SKU ${index + 1}`}
                        value={sku}
                        onChange={(e) => updateSku(index, e.target.value)}
                        className="flex-1"
                      />
                      {skus.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removeSku(index)}
                        >
                          <Trash2 className="h-4 w-4 text-danger" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>

                <Button type="button" variant="outline" onClick={addSku} className="w-full">
                  <Plus className="h-4 w-4 mr-2" />
                  Add SKU
                </Button>

                <div className="pt-4 border-t border-border">
                  <label className="text-sm text-fg-muted block mb-2">Analyzer Mode</label>
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                    className="w-full px-3 py-2 rounded-md border border-border bg-surface text-sm"
                  >
                    <option value="hybrid_fast">Hybrid Fast</option>
                    <option value="hybrid_strict">Hybrid Strict</option>
                    <option value="ocr">OCR Only</option>
                    <option value="vlm">VLM Only</option>
                  </select>
                </div>

                <Button
                  type="submit"
                  disabled={loading || skus.filter(s => s.trim()).length === 0}
                  className="w-full"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Layers className="h-4 w-4 mr-2" />
                  )}
                  Run Batch Analysis
                </Button>

                {error && (
                  <div className="mt-4 p-3 rounded-md bg-danger-soft text-danger text-sm flex items-center gap-2">
                    <AlertCircle className="h-4 w-4" />
                    {error}
                  </div>
                )}
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Results Panel */}
        <div className="lg:col-span-2">
          {summary && (
            <Card className="mb-4">
              <CardHeader>
                <CardTitle className="text-base">Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-5 gap-4 text-center">
                  <div className="p-3 rounded-lg bg-bg-subtle">
                    <p className="text-2xl font-semibold">{summary.total}</p>
                    <p className="text-xs text-fg-muted">Total</p>
                  </div>
                  <div className="p-3 rounded-lg bg-success-soft">
                    <p className="text-2xl font-semibold text-success">{summary.pass}</p>
                    <p className="text-xs text-success">Pass</p>
                  </div>
                  <div className="p-3 rounded-lg bg-warning-soft">
                    <p className="text-2xl font-semibold text-warning">{summary.review}</p>
                    <p className="text-xs text-warning">Review</p>
                  </div>
                  <div className="p-3 rounded-lg bg-danger-soft">
                    <p className="text-2xl font-semibold text-danger">{summary.fail}</p>
                    <p className="text-xs text-danger">Fail</p>
                  </div>
                  <div className="p-3 rounded-lg bg-bg-subtle">
                    <p className="text-2xl font-semibold">{summary.no_image}</p>
                    <p className="text-xs text-fg-muted">No Image</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {results && (
            <div className="space-y-3">
              {results.map((result, i) => (
                <Card key={i} className="overflow-hidden">
                  <div className="p-4 flex items-center gap-4">
                    {result.selected_image ? (
                      <img
                        src={result.selected_image}
                        alt={result.sku}
                        className="h-16 w-16 object-cover rounded-md"
                      />
                    ) : (
                      <div className="h-16 w-16 rounded-md bg-bg-subtle flex items-center justify-center text-fg-muted text-xs">
                        No img
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{result.sku}</p>
                      <p className="text-sm text-fg-muted truncate">
                        {result.parsed_wine.producer} {result.parsed_wine.wine_name}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-fg-muted">
                        {Math.round(result.confidence * 100)}%
                      </span>
                      <Badge variant={getVerdictColor(result.verdict)}>{result.verdict}</Badge>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}

          {!results && !loading && (
            <Card className="h-64 flex items-center justify-center">
              <div className="text-center text-fg-muted">
                <Layers className="h-8 w-8 mx-auto mb-2" />
                <p>Add SKUs and run analysis to see results</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
