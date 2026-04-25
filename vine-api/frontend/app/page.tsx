'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  ScanSearch,
  Layers,
  BarChart3,
  Activity,
  ArrowRight,
  CheckCircle2,
  XCircle,
  Wine,
} from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { healthCheck, getProviderHealth } from '@/lib/api';

interface StatusInfo {
  status: 'ok' | 'error' | 'loading';
  message: string;
  providers?: {
    total: number;
    healthy: number;
    unhealthy: number;
  };
}

const quickLinks = [
  {
    href: '/analyze',
    title: 'Analyze SKU',
    description: 'Analyze a single wine SKU for image verification',
    icon: ScanSearch,
  },
  {
    href: '/batch',
    title: 'Batch Analysis',
    description: 'Process multiple SKUs in one batch job',
    icon: Layers,
  },
  {
    href: '/eval',
    title: 'Evaluate Pipelines',
    description: 'Compare analyzer pipeline performance',
    icon: BarChart3,
  },
  {
    href: '/health',
    title: 'System Health',
    description: 'Monitor provider health and status',
    icon: Activity,
  },
];

export default function Home() {
  const [apiStatus, setApiStatus] = useState<StatusInfo>({ status: 'loading', message: 'Checking...' });

  useEffect(() => {
    async function checkHealth() {
      try {
        const [basic, providers] = await Promise.all([
          healthCheck(),
          getProviderHealth(),
        ]);
        setApiStatus({
          status: basic.status === 'ok' ? 'ok' : 'error',
          message: 'API is operational',
          providers: providers.summary,
        });
      } catch {
        setApiStatus({
          status: 'error',
          message: 'API is unreachable',
        });
      }
    }
    checkHealth();
  }, []);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Vine API Dashboard"
        description="Unified wine image analysis service. Analyze wine SKUs, run batch jobs, and evaluate pipelines."
      />

      {/* Status Card */}
      <Card className={apiStatus.status === 'ok' ? 'border-success/30' : apiStatus.status === 'error' ? 'border-danger/30' : ''}>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${
                apiStatus.status === 'ok' ? 'bg-success/10 text-success' : 
                apiStatus.status === 'error' ? 'bg-danger/10 text-danger' : 
                'bg-bg-muted text-fg-muted'
              }`}>
                {apiStatus.status === 'ok' ? <CheckCircle2 className="h-5 w-5" /> :
                 apiStatus.status === 'error' ? <XCircle className="h-5 w-5" /> : 
                 <Activity className="h-5 w-5" />}
              </div>
              <div>
                <h3 className="font-medium text-fg">API Status</h3>
                <p className="text-sm text-fg-muted">{apiStatus.message}</p>
              </div>
            </div>
            {apiStatus.providers && (
              <div className="flex items-center gap-4 text-sm">
                <div className="text-right">
                  <p className="text-fg-muted">Providers</p>
                  <p className="font-medium">{apiStatus.providers.total}</p>
                </div>
                <div className="text-right">
                  <p className="text-fg-muted">Healthy</p>
                  <p className="font-medium text-success">{apiStatus.providers.healthy}</p>
                </div>
                {apiStatus.providers.unhealthy > 0 && (
                  <div className="text-right">
                    <p className="text-fg-muted">Unhealthy</p>
                    <p className="font-medium text-danger">{apiStatus.providers.unhealthy}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Quick Links */}
      <div>
        <h2 className="text-lg font-semibold tracking-tight mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {quickLinks.map((link) => (
            <Link key={link.href} href={link.href}>
              <Card className="h-full hover:shadow-card transition-shadow group">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="h-10 w-10 rounded-lg bg-primary-soft text-primary flex items-center justify-center">
                      <link.icon className="h-5 w-5" />
                    </div>
                    <ArrowRight className="h-4 w-4 text-fg-subtle group-hover:text-primary transition-colors" />
                  </div>
                  <CardTitle className="text-base mt-3">{link.title}</CardTitle>
                  <CardDescription>{link.description}</CardDescription>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      </div>

      {/* About */}
      <div>
        <h2 className="text-lg font-semibold tracking-tight mb-4">About Vine API</h2>
        <Card>
          <CardContent className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <h3 className="font-medium text-fg mb-2">Image Analysis</h3>
                <p className="text-sm text-fg-muted">
                  Verify wine bottle photos using OCR and Vision Language Models. 
                  Find, verify, and trust at scale.
                </p>
              </div>
              <div>
                <h3 className="font-medium text-fg mb-2">Multiple Modes</h3>
                <p className="text-sm text-fg-muted">
                  Choose from OCR-only, VLM-only, or hybrid analyzers with 
                  fast or strict verification levels.
                </p>
              </div>
              <div>
                <h3 className="font-medium text-fg mb-2">Pipeline Evaluation</h3>
                <p className="text-sm text-fg-muted">
                  Compare different analyzer configurations and providers 
                  to find the optimal setup.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
