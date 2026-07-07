'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

interface Toast {
  id: string;
  title: string;
  description?: string;
  type: 'success' | 'error' | 'info' | 'warning';
}

let toasts: Toast[] = [];
let listeners: ((toasts: Toast[]) => void)[] = [];

export function toast(toast: Omit<Toast, 'id'>) {
  const id = Math.random().toString(36).substr(2, 9);
  const newToast = { ...toast, id };
  toasts = [...toasts, newToast];
  listeners.forEach((listener) => listener(toasts));

  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id);
    listeners.forEach((listener) => listener(toasts));
  }, 5000);
}

const icons = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
  warning: AlertTriangle,
};

const colors = {
  success: 'border-green-500 bg-green-50 dark:bg-green-950/30',
  error: 'border-red-500 bg-red-50 dark:bg-red-950/30',
  info: 'border-blue-500 bg-blue-50 dark:bg-blue-950/30',
  warning: 'border-orange-500 bg-orange-50 dark:bg-orange-950/30',
};

const iconColors = {
  success: 'text-green-500',
  error: 'text-red-500',
  info: 'text-blue-500',
  warning: 'text-orange-500',
};

export function Toaster() {
  const [activeToasts, setActiveToasts] = useState<Toast[]>([]);

  useEffect(() => {
    listeners.push(setActiveToasts);
    return () => {
      listeners = listeners.filter((l) => l !== setActiveToasts);
    };
  }, []);

  const removeToast = (id: string) => {
    toasts = toasts.filter((t) => t.id !== id);
    listeners.forEach((listener) => listener(toasts));
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      <AnimatePresence>
        {activeToasts.map((t) => {
          const Icon = icons[t.type];
          return (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 50, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className={`flex w-80 items-start gap-3 rounded-lg border-l-4 p-4 shadow-lg ${colors[t.type]}`}
            >
              <Icon className={`mt-0.5 h-5 w-5 ${iconColors[t.type]}`} />
              <div className="flex-1">
                <p className="font-medium">{t.title}</p>
                {t.description && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    {t.description}
                  </p>
                )}
              </div>
              <button
                onClick={() => removeToast(t.id)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
