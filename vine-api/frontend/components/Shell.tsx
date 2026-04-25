'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/cn';
import {
  Home,
  ScanSearch,
  Layers,
  BarChart3,
  Activity,
  Wine,
} from 'lucide-react';

const navItems = [
  { href: '/', label: 'Overview', icon: Home },
  { href: '/analyze', label: 'Analyze', icon: ScanSearch },
  { href: '/batch', label: 'Batch', icon: Layers },
  { href: '/eval', label: 'Evaluate', icon: BarChart3 },
  { href: '/health', label: 'Health', icon: Activity },
];

function NavItem({
  href,
  label,
  icon: Icon,
  isActive,
}: {
  href: string;
  label: string;
  icon: React.ElementType;
  isActive: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
        isActive
          ? 'bg-sidebar-active text-sidebar-fg-active'
          : 'text-sidebar-fg hover:bg-sidebar-hover hover:text-sidebar-fg-active'
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 border-r border-sidebar-border bg-sidebar-bg flex flex-col">
        <div className="p-4 border-b border-sidebar-border">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
              <Wine className="h-4 w-4 text-primary-fg" />
            </div>
            <span className="font-semibold text-fg">Vine API</span>
          </Link>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => (
            <NavItem
              key={item.href}
              {...item}
              isActive={pathname === item.href}
            />
          ))}
        </nav>

        <div className="p-4 border-t border-sidebar-border">
          <div className="text-xs text-sidebar-fg">
            <p className="font-medium">Vine API</p>
            <p className="mt-0.5">Unified wine analysis</p>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto p-8">{children}</div>
      </main>
    </div>
  );
}
