'use client';

import { useEffect, useState } from 'react';
import { Activity, CheckCircle2, XCircle, AlertTriangle, RefreshCw, Loader2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { getProviderHealth, healthCheck } from '@/lib/api';
import { ProviderHealth } from '@/lib/types';

export default function HealthPage() {
  const [providers, setProviders] = useState<ProviderHealth[]>([]);
  const [summary, setSummary] = useState<{ total: number; healthy: number; unhealthy: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiStatus, setApiStatus] = useState<'ok' | 'error'>('ok');

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const [basic, providersData] = await Promise.all([
        healthCheck(),
        getProviderHealth(),
      ]);
      setApiStatus(basic.status === 'ok' ? 'ok' : 'error');
      setProviders(providersData.providers);
      setSummary(providersData.summary);
    } catch {
      setApiStatus('error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle2 className="h-4 w-4 text-success" />;
      case 'unhealthy':
        return <XCircle className="h-4 w-4 text-danger" />;
      default:
        return <AlertTriangle className="h-4 w-4 text-warning" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'healthy':
        return <Badge variant="success">Healthy</Badge>;
      case 'unhealthy':
        return <Badge variant="destructive">Unhealthy</Badge>;
      default:
        return <Badge variant="warning">Unknown</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="System Health"
        description="Monitor API and provider health status."
        actions={
          <Button variant="outline" onClick={fetchHealth} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
            Refresh
          </Button>
        }
      />

      {/* API Status */}
      <Card className={apiStatus === 'ok' ? 'border-success/30' : 'border-danger/30'}>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`h-12 w-12 rounded-lg flex items-center justify-center ${
                apiStatus === 'ok' ? 'bg-success/10' : 'bg-danger/10'
              }`}>
                <Activity className={`h-6 w-6 ${apiStatus === 'ok' ? 'text-success' : 'text-danger'}`} />
              </div>
              <div>
                <h3 className="font-semibold text-fg">Vine API</h3>
                <p className="text-sm text-fg-muted">
                  {apiStatus === 'ok' ? 'All systems operational' : 'API is experiencing issues'}
                </p>
              </div>
            </div>
            <Badge variant={apiStatus === 'ok' ? 'success' : 'destructive'} className="text-sm">
              {apiStatus === 'ok' ? 'Operational' : 'Error'}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Summary */}
      {summary && (
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardContent className="p-6 text-center">
              <p className="text-3xl font-semibold">{summary.total}</p>
              <p className="text-sm text-fg-muted">Total Providers</p>
            </CardContent>
          </Card>
          <Card className="border-success/30">
            <CardContent className="p-6 text-center">
              <p className="text-3xl font-semibold text-success">{summary.healthy}</p>
              <p className="text-sm text-success">Healthy</p>
            </CardContent>
          </Card>
          <Card className={summary.unhealthy > 0 ? 'border-danger/30' : ''}>
            <CardContent className="p-6 text-center">
              <p className={`text-3xl font-semibold ${summary.unhealthy > 0 ? 'text-danger' : ''}`}>
                {summary.unhealthy}
              </p>
              <p className={`text-sm ${summary.unhealthy > 0 ? 'text-danger' : 'text-fg-muted'}`}>Unhealthy</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Providers Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Provider Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs font-medium text-fg-muted border-b border-border">
                  <th className="text-left py-2 px-3">Status</th>
                  <th className="text-left py-2 px-3">Name</th>
                  <th className="text-left py-2 px-3">Type</th>
                  <th className="text-left py-2 px-3">Latency</th>
                  <th className="text-left py-2 px-3">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {providers.map((provider, i) => (
                  <tr key={i} className="text-sm">
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(provider.status)}
                        {getStatusBadge(provider.status)}
                      </div>
                    </td>
                    <td className="py-3 px-3 font-medium">{provider.name}</td>
                    <td className="py-3 px-3">
                      <Badge variant="outline" className="text-xs capitalize">
                        {provider.type}
                      </Badge>
                    </td>
                    <td className="py-3 px-3">
                      {provider.latency_ms ? `${provider.latency_ms}ms` : '-'}
                    </td>
                    <td className="py-3 px-3 text-danger text-xs">
                      {provider.error || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
