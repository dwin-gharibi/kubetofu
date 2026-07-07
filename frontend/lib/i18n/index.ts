import { fa } from './fa';

export const translations = fa;

export const localeConfig = {
  name: 'فارسی',
  dir: 'rtl' as const,
  locale: 'fa-IR',
};

function getNestedValue(obj: any, path: string): string {
  return path.split('.').reduce((acc, part) => acc && acc[part], obj) || path;
}

export function t(
  key: string,
  params?: Record<string, string | number>
): string {
  const translation = getNestedValue(translations, key);
  
  if (!params) return translation;
  
  return Object.entries(params).reduce(
    (str, [key, value]) => str.replace(`{${key}}`, String(value)),
    translation
  );
}

export function formatNumber(num: number): string {
  return new Intl.NumberFormat('fa-IR').format(num);
}

export function formatCurrency(amount: number, currency: string = 'IRR'): string {
  if (currency === 'IRR' || currency === 'تومان') {
    const formatted = formatNumber(amount);
    return `${formatted} تومان`;
  }
  
  if (currency === 'USD' || currency === 'دلار') {
    return new Intl.NumberFormat('fa-IR', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  }
  
  return `${formatNumber(amount)} ${currency}`;
}

export function formatDate(
  date: Date | string,
  options?: Intl.DateTimeFormatOptions
): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  
  return new Intl.DateTimeFormat('fa-IR', {
    dateStyle: 'medium',
    timeStyle: 'short',
    ...options,
  }).format(d);
}

export function formatRelativeTime(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  const diffWeeks = Math.floor(diffMs / 604800000);
  
  if (diffMinutes < 1) return t('time.justNow');
  if (diffMinutes < 60) return t('time.minutesAgo', { count: diffMinutes });
  if (diffHours < 24) return t('time.hoursAgo', { count: diffHours });
  if (diffDays < 7) return t('time.daysAgo', { count: diffDays });
  return t('time.weeksAgo', { count: diffWeeks });
}

export { fa };
