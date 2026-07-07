export const fa = {
  app: {
    name: 'کیوب‌توفو',
    tagline: 'عامل هوشمند زیرساخت',
    description: 'با زبان طبیعی زیرساخت خود را مدیریت کنید',
  },

  common: {
    loading: 'در حال بارگذاری...',
    error: 'خطا',
    success: 'موفقیت',
    cancel: 'انصراف',
    confirm: 'تایید',
    save: 'ذخیره',
    delete: 'حذف',
    edit: 'ویرایش',
    create: 'ایجاد',
    search: 'جستجو...',
    filter: 'فیلتر',
    close: 'بستن',
    back: 'بازگشت',
    next: 'بعدی',
    previous: 'قبلی',
    yes: 'بله',
    no: 'خیر',
    copy: 'کپی',
    copied: 'کپی شد!',
    download: 'دانلود',
    upload: 'آپلود',
    refresh: 'بازنشانی',
    settings: 'تنظیمات',
    help: 'راهنما',
    logout: 'خروج',
    login: 'ورود',
    register: 'ثبت‌نام',
    online: 'متصل',
    offline: 'آفلاین',
    checking: 'در حال بررسی...',
    newChat: 'گفتگوی جدید',
  },

  chat: {
    title: 'با عامل عمیق گفتگو کنید',
    subtitle: 'هر سوالی درباره زیرساخت دارید، بپرسید',
    placeholder: 'چه کاری می‌توانم انجام دهم؟ مثلاً: یک Dockerfile برای پروژه پایتون بساز...',
    send: 'ارسال',
    stop: 'توقف',
    regenerate: 'تولید مجدد',
    thinking: 'در حال فکر کردن...',
    processing: 'در حال پردازش...',
    welcome: 'سلام! من عامل هوشمند کیوب‌توفو هستم',
    welcomeSubtitle: 'چگونه می‌توانم در مدیریت زیرساخت به شما کمک کنم؟',
    disclaimer: 'کیوب‌توفو ممکن است اشتباه کند. تغییرات مهم زیرساختی را همیشه بررسی کنید.',
    suggestions: {
      title: 'پیشنهادات',
      dockerfile: 'یک Dockerfile برای اپلیکیشن Flask بساز',
      kubernetes: 'مانیفست‌های Kubernetes برای ۳ رپلیکا تولید کن',
      terraform: 'تنظیمات Terraform برای VPC با زیرشبکه خصوصی',
      security: 'کد زیرساخت من را از نظر امنیتی بررسی کن',
      diagnose: 'علت CrashLoopBackOff در پادها را پیدا کن',
      cost: 'هزینه‌های زیرساخت را بهینه‌سازی کن',
    },
  },

  agent: {
    name: 'عامل عمیق',
    thinking: 'در حال تحلیل...',
    planning: 'در حال برنامه‌ریزی...',
    executing: 'در حال اجرا...',
    searching: 'در حال جستجو...',
    generating: 'در حال تولید کد...',
    analyzing: 'در حال تحلیل امنیتی...',
    deploying: 'در حال استقرار...',
    completed: 'تکمیل شد',
    failed: 'خطا در اجرا',
    waiting: 'در انتظار تایید شما',
  },

  tools: {
    title: 'ابزارها',
    terraformPlan: 'برنامه‌ریزی Terraform',
    terraformApply: 'اعمال Terraform',
    terraformDestroy: 'حذف منابع Terraform',
    kubernetesApply: 'اعمال Kubernetes',
    kubernetesGet: 'دریافت اطلاعات Kubernetes',
    securityScan: 'اسکن امنیتی',
    costEstimate: 'تخمین هزینه',
    fileWrite: 'نوشتن فایل',
    fileRead: 'خواندن فایل',
    shellExecute: 'اجرای دستور',
    webSearch: 'جستجوی وب',
    codeGenerate: 'تولید کد',
    approval: {
      required: 'نیاز به تایید',
      approve: 'تایید می‌کنم',
      reject: 'رد می‌کنم',
      reason: 'دلیل',
      warning: 'این عملیات تغییرات مهمی در زیرساخت ایجاد می‌کند',
    },
  },

  subAgents: {
    planner: {
      name: 'برنامه‌ریز',
      description: 'طراحی معماری و تولید کد زیرساخت',
    },
    security: {
      name: 'امنیت',
      description: 'بررسی آسیب‌پذیری‌ها و انطباق',
    },
    cost: {
      name: 'هزینه',
      description: 'تخمین و بهینه‌سازی هزینه',
    },
    deployment: {
      name: 'استقرار',
      description: 'اجرای Terraform و Kubernetes',
    },
    diagnostic: {
      name: 'تشخیص',
      description: 'تحلیل و رفع مشکلات کلاستر',
    },
    research: {
      name: 'تحقیق',
      description: 'جستجوی مستندات و راه‌حل‌ها',
    },
  },

  todos: {
    title: 'وظایف',
    addTask: 'افزودن وظیفه',
    pending: 'در انتظار',
    inProgress: 'در حال انجام',
    completed: 'تکمیل شده',
    cancelled: 'لغو شده',
    empty: 'هیچ وظیفه‌ای وجود ندارد',
    clearCompleted: 'پاک کردن تکمیل‌شده‌ها',
  },

  code: {
    copy: 'کپی کد',
    copied: 'کپی شد!',
    download: 'دانلود',
    apply: 'اعمال کن',
    language: 'زبان',
  },

  security: {
    title: 'امنیت',
    scan: 'اسکن امنیتی',
    severity: {
      critical: 'بحرانی',
      high: 'بالا',
      medium: 'متوسط',
      low: 'پایین',
      info: 'اطلاعاتی',
    },
    compliance: {
      title: 'انطباق',
      passing: 'موفق',
      failing: 'ناموفق',
    },
    findings: 'یافته‌ها',
    remediation: 'راه‌حل',
  },

  deployment: {
    title: 'استقرار',
    status: {
      pending: 'در انتظار',
      planning: 'در حال برنامه‌ریزی',
      applying: 'در حال اعمال',
      completed: 'تکمیل شد',
      failed: 'ناموفق',
      cancelled: 'لغو شد',
    },
    resources: {
      toAdd: 'اضافه می‌شود',
      toChange: 'تغییر می‌کند',
      toDestroy: 'حذف می‌شود',
    },
  },

  costs: {
    title: 'هزینه',
    monthly: 'ماهانه',
    estimated: 'تخمینی',
    currency: 'تومان',
    usd: 'دلار',
    savings: 'صرفه‌جویی',
  },

  settings: {
    title: 'تنظیمات',
    theme: {
      title: 'تم',
      light: 'روشن',
      dark: 'تیره',
      system: 'سیستم',
    },
    provider: {
      title: 'ارائه‌دهنده',
      arvancloud: 'ابرآروان',
      aws: 'آمازون',
      gcp: 'گوگل',
      azure: 'آژور',
    },
    model: {
      title: 'مدل هوش مصنوعی',
    },
    apiKey: {
      title: 'کلید API',
      placeholder: 'کلید API خود را وارد کنید',
    },
  },

  errors: {
    generic: 'خطایی رخ داد',
    network: 'خطای شبکه. لطفاً اتصال خود را بررسی کنید.',
    unauthorized: 'دسترسی غیرمجاز',
    notFound: 'یافت نشد',
    validation: 'خطای اعتبارسنجی',
    timeout: 'زمان درخواست به پایان رسید',
    backendOffline: 'سرور در دسترس نیست',
  },

  time: {
    justNow: 'همین الان',
    minutesAgo: '{count} دقیقه پیش',
    hoursAgo: '{count} ساعت پیش',
    daysAgo: '{count} روز پیش',
    weeksAgo: '{count} هفته پیش',
  },
};

export type TranslationKeys = typeof fa;
