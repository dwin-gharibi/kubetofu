import type { Metadata, Viewport } from 'next';
import './globals.css';
import { Providers } from '@/components/providers';
import { Toaster } from '@/components/ui/toaster';

export const metadata: Metadata = {
  title: 'کیوب‌توفو | پلتفرم هوشمند IaC',
  description: 'پلتفرم هوشمند مدیریت زیرساخت با عامل‌های هوش مصنوعی عمیق',
  keywords: ['IaC', 'زیرساخت', 'کوبرنتیز', 'ترافرم', 'هوش مصنوعی', 'دوآپس'],
  authors: [{ name: 'تیم کیوب‌توفو' }],
  icons: {
    icon: '/favicon.ico',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0c0f1a' },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="anonymous" />
      </head>
      <body className="font-sans antialiased bg-background text-foreground">
        <Providers>
          <main className="min-h-screen">
            {children}
          </main>
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
