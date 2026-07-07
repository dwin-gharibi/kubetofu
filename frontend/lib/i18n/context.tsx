'use client';

import React, { createContext, useContext, ReactNode } from 'react';
import { t as translate, formatNumber, formatCurrency, formatDate, formatRelativeTime } from './index';

interface LocaleContextType {
  t: (key: string, params?: Record<string, string | number>) => string;
  formatNumber: (num: number) => string;
  formatCurrency: (amount: number, currency?: string) => string;
  formatDate: (date: Date | string, options?: Intl.DateTimeFormatOptions) => string;
  formatRelativeTime: (date: Date | string) => string;
  isRTL: true;
  dir: 'rtl';
}

const LocaleContext = createContext<LocaleContextType | null>(null);

interface LocaleProviderProps {
  children: ReactNode;
}

export function LocaleProvider({ children }: LocaleProviderProps) {
  const value: LocaleContextType = {
    t: translate,
    formatNumber,
    formatCurrency,
    formatDate,
    formatRelativeTime,
    isRTL: true,
    dir: 'rtl',
  };
  
  return (
    <LocaleContext.Provider value={value}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useLocale() {
  const context = useContext(LocaleContext);
  if (!context) {
    return {
      t: translate,
      formatNumber,
      formatCurrency,
      formatDate,
      formatRelativeTime,
      isRTL: true as const,
      dir: 'rtl' as const,
    };
  }
  return context;
}

export function useTranslation() {
  const { t, isRTL, dir } = useLocale();
  return { t, isRTL, dir };
}
