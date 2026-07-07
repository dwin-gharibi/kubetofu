'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Zap,
  ArrowLeft,
  Bot,
  Shield,
  DollarSign,
  Terminal,
  Server,
  FileCode,
  Activity,
  Sparkles,
  Github,
  Moon,
  Sun,
  Check,
  ChevronDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { t } from '@/lib/i18n';
import { useTheme } from '@/components/providers';

const FEATURES = [
  {
    icon: FileCode,
    title: 'تولید کد IaC',
    description: 'با زبان طبیعی کد Terraform، Kubernetes، Docker و Ansible تولید کنید',
    gradient: 'from-blue-500 to-cyan-500',
  },
  {
    icon: Shield,
    title: 'اسکن امنیتی',
    description: 'آسیب‌پذیری‌ها را شناسایی و انطباق با استانداردها را بررسی کنید',
    gradient: 'from-green-500 to-emerald-500',
  },
  {
    icon: DollarSign,
    title: 'بهینه‌سازی هزینه',
    description: 'هزینه‌ها را تخمین بزنید و راه‌های صرفه‌جویی را پیدا کنید',
    gradient: 'from-yellow-500 to-orange-500',
  },
  {
    icon: Activity,
    title: 'تشخیص مشکلات',
    description: 'مشکلات کلاستر Kubernetes را تشخیص داده و رفع کنید',
    gradient: 'from-purple-500 to-pink-500',
  },
  {
    icon: Server,
    title: 'استقرار خودکار',
    description: 'زیرساخت را با یک دستور روی ابرآروان یا AWS مستقر کنید',
    gradient: 'from-orange-500 to-red-500',
  },
  {
    icon: Bot,
    title: 'عامل‌های هوشمند',
    description: 'زیرعامل‌های تخصصی برای برنامه‌ریزی، امنیت و استقرار',
    gradient: 'from-pink-500 to-rose-500',
  },
];

const SAMPLE_CONVERSATION = [
  {
    role: 'user',
    content: 'یک Dockerfile بهینه برای اپلیکیشن Flask با PostgreSQL بساز',
  },
  {
    role: 'assistant',
    content: `بسیار خب! یک Dockerfile بهینه با multi-stage build می‌سازم:

\`\`\`dockerfile
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .
USER nobody
EXPOSE 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
\`\`\``,
  },
];

const PLANS = [
  {
    name: 'رایگان',
    price: '۰',
    period: 'برای همیشه',
    features: [
      '۱۰۰ درخواست در ماه',
      'تولید کد پایه',
      'اسکن امنیتی محدود',
      'پشتیبانی انجمن',
    ],
    cta: 'شروع رایگان',
    popular: false,
  },
  {
    name: 'حرفه‌ای',
    price: '۴۹۰,۰۰۰',
    period: 'تومان / ماه',
    features: [
      'درخواست نامحدود',
      'همه ابزارها',
      'اسکن امنیتی کامل',
      'پشتیبانی اولویت‌دار',
      'API اختصاصی',
    ],
    cta: 'شروع دوره آزمایشی',
    popular: true,
  },
  {
    name: 'سازمانی',
    price: 'سفارشی',
    period: 'تماس بگیرید',
    features: [
      'همه امکانات حرفه‌ای',
      'استقرار اختصاصی',
      'SLA تضمینی',
      'پشتیبانی ۲۴/۷',
      'آموزش تیم',
    ],
    cta: 'تماس با فروش',
    popular: false,
  },
];

export default function LandingPage() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <header className="fixed top-0 left-0 right-0 z-50 border-b bg-background/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-purple-600">
                <Zap className="h-6 w-6 text-white" />
              </div>
              <span className="text-xl font-bold gradient-text">
                کیوب‌توفو
              </span>
            </div>

            <nav className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                ویژگی‌ها
              </a>
              <a href="#demo" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                نمونه
              </a>
              <a href="#pricing" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                قیمت‌ها
              </a>
            </nav>

            <div className="flex items-center gap-3">
              {mounted && (
                <button
                  onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
                  className="btn-ghost btn-icon h-9 w-9"
                >
                  {resolvedTheme === 'dark' ? (
                    <Moon className="h-4 w-4" />
                  ) : (
                    <Sun className="h-4 w-4" />
                  )}
                </button>
              )}
              <Link
                href="/chat"
                className="btn-primary btn-sm px-4"
              >
                ورود به چت
              </Link>
            </div>
          </div>
        </div>
      </header>

      <section className="pt-32 pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6"
            >
              <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 text-primary text-sm font-medium">
                <Sparkles className="h-4 w-4" />
                عامل هوشمند زیرساخت با هوش مصنوعی
              </span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="text-4xl sm:text-5xl lg:text-6xl font-bold mb-6"
            >
              مدیریت زیرساخت با
              <span className="gradient-text block mt-2">زبان طبیعی فارسی</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto mb-10"
            >
              کیوب‌توفو یک عامل هوشمند است که با گفتگوی ساده، کد Terraform و Kubernetes تولید می‌کند،
              امنیت را بررسی می‌کند و زیرساخت را مستقر می‌کند.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="flex flex-col sm:flex-row items-center justify-center gap-4"
            >
              <Link
                href="/chat"
                className="btn-primary btn-lg px-8 gap-2 w-full sm:w-auto"
              >
                <span>شروع گفتگو</span>
                <ArrowLeft className="h-5 w-5" />
              </Link>
              <a
                href="https://github.com/dwin-gharibi/kube-tofu"
                target="_blank"
                rel="noopener noreferrer"
                className="btn-outline btn-lg px-8 gap-2 w-full sm:w-auto"
              >
                <Github className="h-5 w-5" />
                <span>مشاهده در گیت‌هاب</span>
              </a>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="mt-16 relative"
          >
            <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-transparent z-10 pointer-events-none" />
            <div className="relative rounded-2xl border bg-card overflow-hidden shadow-2xl">
              <div className="flex items-center gap-3 px-4 py-3 border-b bg-card">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-purple-600">
                  <Zap className="h-4 w-4 text-white" />
                </div>
                <span className="font-medium">کیوب‌توفو</span>
                <span className="text-xs text-muted-foreground">- عامل هوشمند زیرساخت</span>
              </div>
              
              <div className="p-6 space-y-6 max-h-[400px] overflow-hidden">
                {SAMPLE_CONVERSATION.map((msg, i) => (
                  <div
                    key={i}
                    className={cn(
                      'flex gap-3',
                      msg.role === 'user' && 'flex-row-reverse'
                    )}
                  >
                    <div className={cn(
                      'flex-shrink-0 h-8 w-8 rounded-lg flex items-center justify-center',
                      msg.role === 'assistant'
                        ? 'bg-gradient-to-br from-blue-500 to-purple-600'
                        : 'bg-primary'
                    )}>
                      {msg.role === 'assistant' ? (
                        <Bot className="h-4 w-4 text-white" />
                      ) : (
                        <span className="text-xs text-primary-foreground">ش</span>
                      )}
                    </div>
                    <div className={cn(
                      'rounded-2xl px-4 py-3 max-w-[80%]',
                      msg.role === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-secondary'
                    )}>
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      <section id="features" className="py-20 px-4 sm:px-6 lg:px-8 bg-secondary/30">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              همه چیز در یک گفتگو
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              کیوب‌توفو با عامل‌های هوشمند تخصصی، تمام نیازهای زیرساختی شما را پوشش می‌دهد
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((feature, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="card p-6 hover:shadow-lg transition-shadow"
              >
                <div className={cn(
                  'h-12 w-12 rounded-xl bg-gradient-to-br flex items-center justify-center mb-4',
                  feature.gradient
                )}>
                  <feature.icon className="h-6 w-6 text-white" />
                </div>
                <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                <p className="text-muted-foreground">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section id="demo" className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              چگونه کار می‌کند؟
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              در سه مرحله ساده، زیرساخت خود را با هوش مصنوعی مدیریت کنید
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                step: '۱',
                title: 'توضیح دهید',
                description: 'نیاز زیرساختی خود را به زبان طبیعی فارسی توضیح دهید',
                icon: Terminal,
              },
              {
                step: '۲',
                title: 'بررسی کنید',
                description: 'کد تولید شده را بررسی و در صورت نیاز اصلاح کنید',
                icon: FileCode,
              },
              {
                step: '۳',
                title: 'مستقر کنید',
                description: 'با یک تایید، زیرساخت را روی ابر مورد نظر مستقر کنید',
                icon: Server,
              },
            ].map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="text-center"
              >
                <div className="relative inline-block mb-6">
                  <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto">
                    <item.icon className="h-8 w-8 text-primary" />
                  </div>
                  <span className="absolute -top-2 -right-2 h-8 w-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold">
                    {item.step}
                  </span>
                </div>
                <h3 className="text-xl font-semibold mb-2">{item.title}</h3>
                <p className="text-muted-foreground">{item.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="py-20 px-4 sm:px-6 lg:px-8 bg-secondary/30">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              پلن‌های قیمت‌گذاری
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              پلن مناسب خود را انتخاب کنید و همین امروز شروع کنید
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {PLANS.map((plan, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className={cn(
                  'card p-6 relative',
                  plan.popular && 'border-primary shadow-lg scale-105'
                )}
              >
                {plan.popular && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-primary text-primary-foreground text-xs font-medium">
                    محبوب‌ترین
                  </span>
                )}
                <div className="text-center mb-6">
                  <h3 className="text-xl font-semibold mb-2">{plan.name}</h3>
                  <div className="flex items-baseline justify-center gap-1">
                    <span className="text-4xl font-bold">{plan.price}</span>
                    <span className="text-muted-foreground">{plan.period}</span>
                  </div>
                </div>
                <ul className="space-y-3 mb-6">
                  {plan.features.map((feature, j) => (
                    <li key={j} className="flex items-center gap-2 text-sm">
                      <Check className="h-4 w-4 text-success flex-shrink-0" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                <button
                  className={cn(
                    'w-full py-3 rounded-xl font-medium transition-colors',
                    plan.popular
                      ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                      : 'bg-secondary hover:bg-secondary/80'
                  )}
                >
                  {plan.cta}
                </button>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="card p-12 bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600 border-0 text-white"
          >
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              آماده شروع هستید؟
            </h2>
            <p className="text-lg opacity-90 mb-8 max-w-xl mx-auto">
              همین الان با عامل هوشمند کیوب‌توفو گفتگو کنید و زیرساخت خود را به سطح بعدی ببرید
            </p>
            <Link
              href="/chat"
              className="inline-flex items-center gap-2 rounded-full bg-white px-8 py-4 font-medium text-purple-600 transition-all hover:scale-105 hover:shadow-lg"
            >
              <span>شروع گفتگو رایگان</span>
              <ArrowLeft className="h-5 w-5" />
            </Link>
          </motion.div>
        </div>
      </section>

      <footer className="border-t py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-purple-600">
                <Zap className="h-6 w-6 text-white" />
              </div>
              <span className="text-xl font-bold gradient-text">
                کیوب‌توفو
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              ساخته شده با ❤️ برای جامعه توسعه‌دهندگان ایران
            </p>
            <div className="flex items-center gap-4">
              <a
                href="https://github.com/dwin-gharibi/kube-tofu"
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <Github className="h-5 w-5" />
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
