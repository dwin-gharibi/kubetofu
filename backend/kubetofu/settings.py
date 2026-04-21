import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-secret-key-change-in-production")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS") + [
    "kube-tofu.dwin.codes",
    "admin.kube-tofu.dwin.codes",
    "core.kube-tofu.dwin.codes",
    ".dwin.codes",
]

CSRF_TRUSTED_ORIGINS = [
    "https://kube-tofu.dwin.codes",
    "https://admin.kube-tofu.dwin.codes",
    "https://core.kube-tofu.dwin.codes",
]

SESSION_COOKIE_DOMAIN = ".kube-tofu.dwin.codes"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_DOMAIN = ".kube-tofu.dwin.codes"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "channels",
    "django_celery_beat",
    "django_celery_results",
    "core",
    "api",
    "agents",
    "providers",
    "executor",
    "state",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "kubetofu.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "kubetofu.wsgi.application"
ASGI_APPLICATION = "kubetofu.asgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="sqlite:///db.sqlite3",
    )
}

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "api.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Kube-Tofu API",
    "DESCRIPTION": "Deep Agentic Infrastructure as Code Platform API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
) + [
    "https://kube-tofu.dwin.codes",
    "https://admin.kube-tofu.dwin.codes",
    "https://core.kube-tofu.dwin.codes",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]
CORS_EXPOSE_HEADERS = [
    "content-type",
    "x-csrftoken",
]

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "default"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

LLM_SETTINGS = {
    "PROVIDER": env("KUBETOFU_LLM_PROVIDER", default="anthropic"),
    "MODEL": env("KUBETOFU_LLM_MODEL", default="claude-sonnet-4-20250514"),
    "TEMPERATURE": env.float("KUBETOFU_LLM_TEMPERATURE", default=0.1),
    "MAX_TOKENS": env.int("KUBETOFU_LLM_MAX_TOKENS", default=4096),
    "OPENAI_API_KEY": env("OPENAI_API_KEY", default=""),
    "ANTHROPIC_API_KEY": env("ANTHROPIC_API_KEY", default=""),
}

AGENT_SETTINGS = {
    "MAX_ITERATIONS": env.int("AGENT_MAX_ITERATIONS", default=10),
    "TIMEOUT_SECONDS": env.int("AGENT_TIMEOUT_SECONDS", default=300),
    "ENABLE_PARALLEL_EXECUTION": env.bool("AGENT_PARALLEL_EXECUTION", default=True),
    "MEMORY_TYPE": env("AGENT_MEMORY_TYPE", default="vector"),
    "VECTOR_DB_PATH": env("AGENT_VECTOR_DB_PATH", default=str(BASE_DIR / "vectordb")),
}

ARVANCLOUD_SETTINGS = {
    "API_KEY": env("ARVAN_API_KEY", default=""),
    "REGION": env("ARVAN_REGION", default="ir-thr-at1"),
    "BASE_URL": env("ARVAN_BASE_URL", default="https://napi.arvancloud.ir"),
    "IAAS_URL": env("ARVAN_IAAS_URL", default="https://napi.arvancloud.ir/ecc/v1"),
    "CDN_URL": env("ARVAN_CDN_URL", default="https://napi.arvancloud.ir/cdn/4.0"),
    "DNS_URL": env("ARVAN_DNS_URL", default="https://napi.arvancloud.ir/cdn/4.0/domains"),
}

INFRASTRUCTURE_SETTINGS = {
    "TERRAFORM_PATH": env("TERRAFORM_PATH", default="tofu"),
    "KUBECTL_PATH": env("KUBECTL_PATH", default="kubectl"),
    "STATE_BACKEND": env("STATE_BACKEND", default="local"),
    "WORKSPACE_DIR": env("WORKSPACE_DIR", default=str(BASE_DIR / "workspaces")),
    "PLANS_DIR": env("PLANS_DIR", default=str(BASE_DIR / "plans")),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "agents": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
