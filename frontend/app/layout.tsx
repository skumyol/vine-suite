import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Shell } from '@/components/Shell';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Vine API — Wine Analysis Dashboard',
  description:
    'Unified wine image analysis service. Analyze wine SKUs, run batch jobs, and evaluate pipelines.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans antialiased">
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
