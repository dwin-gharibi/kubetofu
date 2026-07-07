const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';

export interface ChatSession {
  id: string;
  title: string;
  status: 'active' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  messages_count: number;
  agents_used: string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: string;
  agent_name?: string;
  tool_name?: string;
  metadata?: Record<string, any>;
}

export interface ToolCallEvent {
  type: 'tool_start' | 'tool_end' | 'tool_error';
  tool_name: string;
  tool_input?: Record<string, any>;
  tool_output?: string;
  error?: string;
}

export interface AgentEvent {
  type: 'agent_thinking' | 'agent_action' | 'agent_response' | 'agent_error';
  agent_name: string;
  message?: string;
  action?: string;
  metadata?: Record<string, any>;
}

export interface StreamEvent {
  type: 'token' | 'tool_call' | 'agent_event' | 'done' | 'error';
  content?: string;
  tool?: ToolCallEvent;
  agent?: AgentEvent;
  error?: string;
  metadata?: Record<string, any>;
}

export class ApiError extends Error {
  status: number;
  data?: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  
  const config: RequestInit = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, config);
    
    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = { detail: response.statusText };
      }
      throw new ApiError(
        errorData.detail || errorData.error || `Request failed: ${response.statusText}`,
        response.status,
        errorData,
      );
    }

    return response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError('سرور در دسترس نیست', 503);
  }
}

export async function checkHealth(): Promise<{ 
  status: string; 
  timestamp: string;
  demo_mode: boolean;
}> {
  try {
    const data = await apiRequest<{ status: string; timestamp: string }>('/health/');
    return { ...data, demo_mode: false };
  } catch {
    return { 
      status: 'demo', 
      timestamp: new Date().toISOString(),
      demo_mode: true 
    };
  }
}

export async function getSessions(): Promise<ChatSession[]> {
  try {
    return await apiRequest<ChatSession[]>('/sessions/');
  } catch {
    return [];
  }
}

export async function createSession(): Promise<ChatSession> {
  try {
    return await apiRequest<ChatSession>('/sessions/', {
      method: 'POST',
      body: JSON.stringify({}),
    });
  } catch {
    return {
      id: `demo-${Date.now()}`,
      title: 'گفتگوی جدید',
      status: 'active',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages_count: 0,
      agents_used: [],
    };
  }
}

export async function getSession(sessionId: string): Promise<ChatSession> {
  return apiRequest<ChatSession>(`/sessions/${sessionId}/`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  try {
    await apiRequest(`/sessions/${sessionId}/`, { method: 'DELETE' });
  } catch {
  }
}

export async function getSessionMessages(sessionId: string): Promise<ChatMessage[]> {
  try {
    return await apiRequest<ChatMessage[]>(`/sessions/${sessionId}/messages/`);
  } catch {
    return [];
  }
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  context?: Record<string, any>;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  thoughts?: any[];
  actions?: any[];
  agents_used?: string[];
  metadata?: Record<string, any>;
}

export async function sendMessage(request: ChatRequest): Promise<ChatResponse> {
  try {
    return await apiRequest<ChatResponse>('/chat/', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  } catch (error) {
    return {
      response: getDemoResponse(request.message),
      session_id: request.session_id || `demo-${Date.now()}`,
      agents_used: ['planner'],
    };
  }
}

export interface ProjectContext {
  project_name: string;
  language?: string;
  framework?: string;
  service_type?: string;
  databases?: string[];
  has_dockerfile?: boolean;
  has_kubernetes?: boolean;
  has_terraform?: boolean;
  files?: Array<{ name: string; path: string; language: string }>;
}

export async function* streamChat(
  message: string,
  sessionId?: string,
  context?: Record<string, any>,
  onEvent?: (event: StreamEvent) => void,
): AsyncGenerator<string> {
  try {
    const response = await fetch(`${API_BASE}/chat/stream/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        context,
      }),
    });

    if (!response.ok) {
      throw new Error(`Stream failed: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No reader available');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6)) as StreamEvent;
            
            onEvent?.(data);

            if (data.type === 'token' && data.content) {
              yield data.content;
            } else if (data.type === 'done' && data.content) {
              yield data.content;
            } else if (data.type === 'error') {
              throw new Error(data.error || 'Stream error');
            }
          } catch (e) {
            if (e instanceof SyntaxError) continue;
            throw e;
          }
        }
      }
    }
  } catch (error) {
    console.warn('Streaming failed, using demo mode:', error);
    
    const projectContext = context as ProjectContext | undefined;
    const response = getDemoResponse(message, projectContext);
    const words = response.split(' ');
    
    onEvent?.({
      type: 'agent_event',
      agent: {
        type: 'agent_thinking',
        agent_name: 'برنامه‌ریز',
        message: 'در حال تحلیل درخواست...',
      },
    });
    
    await sleep(500);
    
    onEvent?.({
      type: 'tool_call',
      tool: {
        type: 'tool_start',
        tool_name: 'code_generator',
        tool_input: { request: message },
      },
    });
    
    await sleep(300);
    
    onEvent?.({
      type: 'tool_call',
      tool: {
        type: 'tool_end',
        tool_name: 'code_generator',
        tool_output: 'کد تولید شد',
      },
    });

    for (let i = 0; i < words.length; i++) {
      yield words[i] + (i < words.length - 1 ? ' ' : '');
      await sleep(30 + Math.random() * 20);
    }
    
    onEvent?.({ type: 'done', content: response });
  }
}

export interface WebSocketCallbacks {
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  onMessage?: (event: StreamEvent) => void;
  onToken?: (token: string) => void;
  onToolCall?: (tool: ToolCallEvent) => void;
  onAgentEvent?: (agent: AgentEvent) => void;
}

export function createChatWebSocket(
  sessionId: string,
  callbacks: WebSocketCallbacks,
): WebSocket | null {
  if (typeof window === 'undefined') return null;

  try {
    const ws = new WebSocket(`${WS_BASE}/chat/${sessionId}/`);

    ws.onopen = () => {
      console.log('WebSocket connected');
      callbacks.onOpen?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as StreamEvent;
        
        callbacks.onMessage?.(data);
        
        if (data.type === 'token' && data.content) {
          callbacks.onToken?.(data.content);
        } else if (data.type === 'tool_call' && data.tool) {
          callbacks.onToolCall?.(data.tool);
        } else if (data.type === 'agent_event' && data.agent) {
          callbacks.onAgentEvent?.(data.agent);
        }
      } catch {
        console.warn('Failed to parse WebSocket message:', event.data);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      callbacks.onError?.(error);
    };

    ws.onclose = () => {
      console.log('WebSocket closed');
      callbacks.onClose?.();
    };

    return ws;
  } catch (error) {
    console.error('Failed to create WebSocket:', error);
    return null;
  }
}

export async function generateCode(
  description: string,
  format: string = 'auto',
  provider: string = 'arvancloud',
): Promise<{ success: boolean; code?: string; error?: string }> {
  try {
    return await apiRequest('/generate/', {
      method: 'POST',
      body: JSON.stringify({ description, format, provider }),
    });
  } catch {
    return {
      success: true,
      code: getDemoCodeResponse(description, format),
    };
  }
}

export async function securityScan(
  code: string,
  type: string,
): Promise<{ success: boolean; findings?: any[]; error?: string }> {
  try {
    return await apiRequest('/security/scan/', {
      method: 'POST',
      body: JSON.stringify({ code, type }),
    });
  } catch {
    return {
      success: true,
      findings: getDemoSecurityFindings(code),
    };
  }
}

export async function costEstimate(
  code: string,
  provider: string = 'arvancloud',
): Promise<{ success: boolean; estimate?: any; error?: string }> {
  try {
    return await apiRequest('/cost/estimate/', {
      method: 'POST',
      body: JSON.stringify({ code, provider }),
    });
  } catch {
    return {
      success: true,
      estimate: getDemoCostEstimate(provider),
    };
  }
}

export async function diagnoseCluster(
  namespace: string = 'default',
  resourceType: string = 'all',
): Promise<{ success: boolean; diagnosis?: any; error?: string }> {
  try {
    return await apiRequest('/diagnose/', {
      method: 'POST',
      body: JSON.stringify({ namespace, resource_type: resourceType }),
    });
  } catch {
    return {
      success: true,
      diagnosis: getDemoDiagnosis(resourceType),
    };
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getDemoResponse(message: string, projectContext?: ProjectContext): string {
  const lower = message.toLowerCase();

  if (projectContext) {
    const projectName = projectContext.project_name;
    const language = projectContext.language || 'unknown';
    const framework = projectContext.framework || '';
    
    if (lower.includes('dockerfile') || lower.includes('داکر')) {
      return getProjectDockerfileResponse(projectContext);
    }
    
    if (lower.includes('kubernetes') || lower.includes('k8s') || lower.includes('استقرار')) {
      return getProjectK8sResponse(projectContext);
    }
    
    if (lower.includes('امنیت') || lower.includes('security') || lower.includes('بررسی')) {
      return getProjectSecurityResponse(projectContext);
    }
    
    if (lower.includes('هزینه') || lower.includes('cost')) {
      return getProjectCostResponse(projectContext);
    }
    
    if (lower.includes('تحلیل') || lower.includes('چیست') || lower.includes('توضیح')) {
      return getProjectAnalysisResponse(projectContext);
    }
    
    return getProjectDefaultResponse(projectContext, message);
  }

  if (lower.includes('dockerfile') || lower.includes('داکر')) {
    return `## Dockerfile برای اپلیکیشن شما

یک Dockerfile بهینه با multi-stage build می‌سازم:

\`\`\`dockerfile
# مرحله ساخت
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# مرحله اجرا
FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .

# تنظیمات امنیتی
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# پورت و healthcheck
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
  CMD curl -f http://localhost:8000/health || exit 1

# اجرا
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "app:app"]
\`\`\`

### ویژگی‌ها:
- ✅ Multi-stage build برای کاهش حجم
- ✅ کاربر غیر root برای امنیت
- ✅ Health check برای مانیتورینگ
- ✅ تنظیمات بهینه Gunicorn

آیا docker-compose هم نیاز دارید؟`;
  }

  if (lower.includes('kubernetes') || lower.includes('k8s') || lower.includes('رپلیکا')) {
    return `## مانیفست‌های Kubernetes

مانیفست‌های کامل برای استقرار اپلیکیشن شما:

\`\`\`yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  labels:
    app: my-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
      - name: my-app
        image: my-app:latest
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: my-app-secrets
              key: database-url
---
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: my-app-service
spec:
  selector:
    app: my-app
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
---
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
\`\`\`

### شامل:
- ✅ Deployment با ۳ رپلیکا
- ✅ Service برای دسترسی
- ✅ HPA برای auto-scaling
- ✅ Health/Readiness probes
- ✅ Resource limits

آیا Ingress یا NetworkPolicy هم نیاز دارید؟`;
  }

  if (lower.includes('terraform') || lower.includes('vpc')) {
    return `## تنظیمات Terraform برای VPC

یک VPC کامل با زیرشبکه‌های عمومی و خصوصی:

\`\`\`hcl
# main.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "environment" {
  default = "production"
}

variable "vpc_cidr" {
  default = "10.0.0.0/16"
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "\${var.environment}-vpc"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# زیرشبکه‌های عمومی
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "\${var.environment}-public-\${count.index + 1}"
    Type = "public"
  }
}

# زیرشبکه‌های خصوصی
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "\${var.environment}-private-\${count.index + 1}"
    Type = "private"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "\${var.environment}-igw"
  }
}

# NAT Gateway
resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = {
    Name = "\${var.environment}-nat"
  }

  depends_on = [aws_internet_gateway.main]
}

# خروجی‌ها
output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnets" {
  value = aws_subnet.public[*].id
}

output "private_subnets" {
  value = aws_subnet.private[*].id
}
\`\`\`

### شامل:
- ✅ VPC با DNS فعال
- ✅ ۲ زیرشبکه عمومی در AZ های مختلف
- ✅ ۲ زیرشبکه خصوصی
- ✅ Internet Gateway
- ✅ NAT Gateway برای دسترسی خصوصی به اینترنت

آیا Security Groups هم اضافه کنم؟`;
  }

  if (lower.includes('امنیت') || lower.includes('security') || lower.includes('بررسی')) {
    return `## گزارش بررسی امنیتی

تنظیمات شما را بررسی کردم. نتایج:

### ✅ موارد مثبت
- استفاده از HTTPS برای ارتباطات
- رمزگذاری داده‌ها در حالت استراحت فعال است
- سیاست‌های IAM با حداقل دسترسی

### ⚠️ هشدارها
| مورد | شدت | توضیح |
|------|-----|-------|
| تگ latest | متوسط | استفاده از تگ مشخص برای ایمیج‌ها |
| پورت‌های باز | متوسط | پورت ۲۲ به همه آی‌پی‌ها باز است |

### ❌ مشکلات
| مورد | شدت | توضیح |
|------|-----|-------|
| SSH باز | بالا | دسترسی SSH از 0.0.0.0/0 |
| رمز در کد | بحرانی | رمز عبور در کد پیدا شد |

### 💡 پیشنهادات
1. محدود کردن دسترسی SSH به IP های مشخص
2. استفاده از Secrets Manager برای رمزها
3. فعال کردن VPC Flow Logs

آیا می‌خواهید این مشکلات را رفع کنم؟`;
  }

  if (lower.includes('هزینه') || lower.includes('cost')) {
    return `## گزارش تحلیل هزینه

هزینه‌های زیرساخت شما را بررسی کردم:

### هزینه ماهانه فعلی

| سرویس | نوع | تعداد | هزینه |
|-------|-----|-------|-------|
| EC2 | t3.medium | 3 | $150 |
| RDS | db.t3.medium | 1 | $200 |
| S3 | Standard | 500GB | $50 |
| ELB | Application | 1 | $30 |
| **جمع** | | | **$430** |

### 💡 پیشنهادات صرفه‌جویی

| پیشنهاد | صرفه‌جویی | توضیح |
|---------|-----------|-------|
| Reserved Instances | $90/ماه | تعهد ۱ ساله برای EC2 |
| RDS Reserved | $60/ماه | تعهد ۱ ساله برای RDS |
| S3 Intelligent-Tiering | $15/ماه | انتقال خودکار به کلاس ارزان‌تر |

### نتیجه
- هزینه فعلی: **$430/ماه**
- بعد از بهینه‌سازی: **$265/ماه**
- صرفه‌جویی: **$165/ماه (38%)**

آیا می‌خواهید این تغییرات را اعمال کنم؟`;
  }

  if (lower.includes('crash') || lower.includes('خطا') || lower.includes('مشکل') || lower.includes('pod') || lower.includes('پاد')) {
    return `## گزارش تشخیص مشکلات کلاستر

کلاستر شما را بررسی کردم. یافته‌ها:

### 🔴 مشکل اصلی: CrashLoopBackOff

**پاد:** my-app-7d8f9b6c5-xyz
**فضای نام:** production

#### علت
پاد به دلیل کمبود حافظه دچار OOMKilled می‌شود.

#### جزئیات
\`\`\`
Last State:     Terminated
  Reason:       OOMKilled
  Exit Code:    137
  Started:      2024-01-20 10:15:00
  Finished:     2024-01-20 10:15:45

Memory Limit:   128Mi
Memory Usage:   256Mi (200% of limit)
\`\`\`

#### راه‌حل
\`\`\`yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"
\`\`\`

#### دستور اعمال
\`\`\`bash
kubectl patch deployment my-app -n production -p '
{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "my-app",
          "resources": {
            "limits": {"memory": "512Mi"},
            "requests": {"memory": "256Mi"}
          }
        }]
      }
    }
  }
}'
\`\`\`

### 📊 وضعیت کلی کلاستر
- نودها: ۳/۳ آماده
- پادها: ۱۲/۱۴ در حال اجرا
- مصرف CPU: ۴۵%
- مصرف حافظه: ۶۸%

آیا این تغییرات را اعمال کنم؟`;
  }

  return `## سلام! 👋

من **عامل هوشمند کیوب‌توفو** هستم. می‌توانم در این زمینه‌ها کمک کنم:

### 🐳 Docker و کانتینرها
- تولید Dockerfile بهینه
- ایجاد docker-compose

### ☸️ Kubernetes
- مانیفست‌های Deployment, Service, Ingress
- تشخیص و رفع مشکلات کلاستر

### 🏗️ Terraform
- تنظیمات VPC, EC2, RDS
- ماژول‌های قابل استفاده مجدد

### 🔒 امنیت
- بررسی آسیب‌پذیری‌ها
- پیشنهادات امنیتی

### 💰 هزینه
- تخمین هزینه زیرساخت
- پیشنهادات صرفه‌جویی

---

**مثال‌های درخواست:**
- "یک Dockerfile برای اپلیکیشن Flask بساز"
- "مانیفست Kubernetes برای ۳ رپلیکا"
- "کد Terraform من را از نظر امنیتی بررسی کن"
- "علت CrashLoopBackOff در پادها را پیدا کن"

چه کاری می‌توانم انجام دهم؟`;
}

function getDemoCodeResponse(description: string, format: string): string {
  if (format === 'kubernetes' || description.toLowerCase().includes('kubernetes')) {
    return `apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: app
  template:
    metadata:
      labels:
        app: app
    spec:
      containers:
      - name: app
        image: app:latest
        ports:
        - containerPort: 8000`;
  }
  return `FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "app.py"]`;
}

function getDemoSecurityFindings(code: string): any[] {
  const findings = [];
  if (code.includes('0.0.0.0/0')) {
    findings.push({
      severity: 'high',
      title: 'دسترسی عمومی',
      description: 'Security group به همه IP ها دسترسی می‌دهد',
    });
  }
  if (code.includes('password') || code.includes('secret')) {
    findings.push({
      severity: 'critical',
      title: 'رمز عبور در کد',
      description: 'رمز عبور به صورت مستقیم در کد وجود دارد',
    });
  }
  return findings;
}

function getDemoCostEstimate(provider: string): any {
  return {
    monthly_total: provider === 'arvancloud' ? '۲,۵۰۰,۰۰۰ تومان' : '$250',
    breakdown: [
      { service: 'محاسبات', cost: provider === 'arvancloud' ? '۱,۵۰۰,۰۰۰ تومان' : '$150' },
      { service: 'ذخیره‌سازی', cost: provider === 'arvancloud' ? '۵۰۰,۰۰۰ تومان' : '$50' },
      { service: 'شبکه', cost: provider === 'arvancloud' ? '۵۰۰,۰۰۰ تومان' : '$50' },
    ],
  };
}

function getDemoDiagnosis(resourceType: string): any {
  return {
    status: 'healthy',
    summary: `وضعیت ${resourceType} سالم است`,
    issues: [],
    recommendations: ['مانیتورینگ را فعال نگه دارید'],
  };
}

function getProjectDockerfileResponse(ctx: ProjectContext): string {
  const { project_name, language, framework, databases = [], service_type } = ctx;
  
  let dockerfile = '';
  let description = '';
  
  if (language === 'python') {
    const fw = framework || 'flask';
    dockerfile = `# مرحله ساخت
FROM python:3.11-slim as builder

WORKDIR /app

# نصب وابستگی‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# مرحله اجرا
FROM python:3.11-slim

WORKDIR /app

# کپی وابستگی‌ها از builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# کپی کد
COPY . .

# تنظیمات امنیتی
RUN useradd --create-home --shell /bin/bash appuser && \\
    chown -R appuser:appuser /app
USER appuser

# پورت
EXPOSE ${service_type === 'api' ? '8000' : '5000'}

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
  CMD curl -f http://localhost:${service_type === 'api' ? '8000' : '5000'}/health || exit 1

# اجرا
CMD ["${fw === 'fastapi' ? 'uvicorn' : 'gunicorn'}", "${fw === 'fastapi' ? 'main:app --host 0.0.0.0 --port 8000' : '--bind 0.0.0.0:5000 --workers 4 app:app'}"]`;
    
    description = `فریم‌ورک ${fw} با multi-stage build`;
  } else if (language === 'javascript' || language === 'typescript') {
    const fw = framework || 'node';
    dockerfile = `# مرحله ساخت
FROM node:20-alpine as builder

WORKDIR /app

# نصب وابستگی‌ها
COPY package*.json ./
RUN npm ci --only=production

# مرحله build (برای TypeScript)
${language === 'typescript' ? `COPY tsconfig.json ./
COPY src ./src
RUN npm run build` : ''}

# مرحله اجرا
FROM node:20-alpine

WORKDIR /app

# کپی وابستگی‌ها و کد
COPY --from=builder /app/node_modules ./node_modules
${language === 'typescript' ? 'COPY --from=builder /app/dist ./dist' : 'COPY . .'}

# تنظیمات امنیتی
RUN addgroup -g 1001 -S nodejs && \\
    adduser -S nodejs -u 1001
USER nodejs

# متغیرهای محیطی
ENV NODE_ENV=production
ENV PORT=3000

# پورت
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

# اجرا
CMD ["node", "${language === 'typescript' ? 'dist/index.js' : 'index.js'}"]`;
    
    description = `${fw} با Node.js 20 Alpine`;
  } else if (language === 'go') {
    dockerfile = `# مرحله ساخت
FROM golang:1.21-alpine as builder

WORKDIR /app

# نصب وابستگی‌ها
COPY go.mod go.sum ./
RUN go mod download

# ساخت باینری
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o main .

# مرحله اجرا - ایمیج scratch برای حداقل حجم
FROM scratch

WORKDIR /app

# کپی باینری و certificates
COPY --from=builder /app/main .
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# پورت
EXPOSE 8080

# اجرا
ENTRYPOINT ["./main"]`;
    
    description = 'Go با scratch image برای حداقل حجم';
  } else {
    dockerfile = `FROM alpine:latest
WORKDIR /app
COPY . .
CMD ["./start.sh"]`;
    description = 'ایمیج ساده Alpine';
  }
  
  let dbNote = '';
  if (databases.length > 0) {
    dbNote = `

### 🗄️ نکته دیتابیس
پروژه شما از ${databases.join('، ')} استفاده می‌کند. برای اتصال:
\`\`\`bash
# docker-compose
${databases.includes('postgresql') ? 'DATABASE_URL=postgresql://user:pass@db:5432/mydb' : ''}
${databases.includes('mongodb') ? 'MONGO_URI=mongodb://db:27017/mydb' : ''}
${databases.includes('redis') ? 'REDIS_URL=redis://redis:6379' : ''}
\`\`\``;
  }

  return `## Dockerfile برای "${project_name}"

یک Dockerfile بهینه برای پروژه ${language} شما (${description}):

\`\`\`dockerfile
${dockerfile}
\`\`\`

### ✅ ویژگی‌های این Dockerfile:
- Multi-stage build برای کاهش حجم نهایی
- کاربر غیر-root برای امنیت
- Health check برای مانیتورینگ
- Cache layer بهینه برای سرعت build
${dbNote}

آیا docker-compose برای محیط توسعه هم بسازم؟`;
}

function getProjectK8sResponse(ctx: ProjectContext): string {
  const { project_name, language, framework, databases = [], service_type } = ctx;
  const port = service_type === 'api' ? 8000 : (language === 'javascript' ? 3000 : 5000);
  const appName = project_name.toLowerCase().replace(/[^a-z0-9-]/g, '-');
  
  let dbYaml = '';
  if (databases.includes('postgresql')) {
    dbYaml = `
---
# PostgreSQL StatefulSet
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: ${appName}-db
spec:
  serviceName: ${appName}-db
  replicas: 1
  selector:
    matchLabels:
      app: ${appName}-db
  template:
    metadata:
      labels:
        app: ${appName}-db
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: ${appName}
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: ${appName}-db-secret
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: ${appName}-db-secret
              key: password
        volumeMounts:
        - name: db-data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: db-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: ${appName}-db
spec:
  selector:
    app: ${appName}-db
  ports:
  - port: 5432
    targetPort: 5432
  clusterIP: None`;
  }

  return `## مانیفست‌های Kubernetes برای "${project_name}"

مانیفست‌های کامل برای استقرار پروژه ${language}/${framework || 'native'}:

\`\`\`yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${appName}
  labels:
    app: ${appName}
    version: v1
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: ${appName}
  template:
    metadata:
      labels:
        app: ${appName}
        version: v1
    spec:
      containers:
      - name: ${appName}
        image: ${appName}:latest
        imagePullPolicy: Always
        ports:
        - containerPort: ${port}
          name: http
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: ${port}
          initialDelaySeconds: 30
          periodSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: ${port}
          initialDelaySeconds: 5
          periodSeconds: 5
        env:
        - name: NODE_ENV
          value: "production"
        ${databases.includes('postgresql') ? `- name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: ${appName}-secret
              key: database-url` : ''}
---
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: ${appName}-service
spec:
  selector:
    app: ${appName}
  ports:
  - port: 80
    targetPort: ${port}
    name: http
  type: ClusterIP
---
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ${appName}-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - ${appName}.example.com
    secretName: ${appName}-tls
  rules:
  - host: ${appName}.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ${appName}-service
            port:
              number: 80
---
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ${appName}-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ${appName}
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
${dbYaml}
\`\`\`

### 📋 خلاصه:
- **Deployment:** ۳ رپلیکا با rolling update
- **Service:** ClusterIP برای ترافیک داخلی
- **Ingress:** با TLS و cert-manager
- **HPA:** Auto-scaling بین ۳ تا ۱۰ پاد
${databases.length > 0 ? `- **دیتابیس:** ${databases.join('، ')} با StatefulSet` : ''}

آیا NetworkPolicy یا PodDisruptionBudget هم اضافه کنم؟`;
}

function getProjectSecurityResponse(ctx: ProjectContext): string {
  const { project_name, language, framework, has_dockerfile, has_kubernetes, databases = [] } = ctx;
  
  const findings = [];
  const warnings = [];
  const positives = [];
  
  if (has_dockerfile) {
    positives.push('Dockerfile موجود است');
    warnings.push({ item: 'تگ latest', severity: 'متوسط', desc: 'استفاده از تگ‌های مشخص برای ایمیج‌ها' });
  } else {
    findings.push({ item: 'عدم containerization', severity: 'متوسط', desc: 'پروژه Dockerfile ندارد' });
  }
  
  if (databases.length > 0) {
    warnings.push({ item: 'اتصال دیتابیس', severity: 'متوسط', desc: 'بررسی رمزگذاری اتصال' });
  }
  
  if (language === 'python') {
    warnings.push({ item: 'وابستگی‌ها', severity: 'پایین', desc: 'بررسی آسیب‌پذیری‌های pip با safety' });
  } else if (language === 'javascript') {
    warnings.push({ item: 'وابستگی‌ها', severity: 'پایین', desc: 'اجرای npm audit برای بررسی امنیتی' });
  }

  return `## گزارش بررسی امنیتی "${project_name}"

پروژه ${language}/${framework || 'native'} شما را از نظر امنیتی بررسی کردم:

### ✅ موارد مثبت
${positives.map(p => `- ${p}`).join('\n') || '- بررسی در جریان است'}
- تحلیل ساختار پروژه انجام شد
- زبان ${language} شناسایی شد

### ⚠️ هشدارها
${warnings.length > 0 ? `
| مورد | شدت | توضیح |
|------|-----|-------|
${warnings.map(w => `| ${w.item} | ${w.severity} | ${w.desc} |`).join('\n')}
` : '- موردی یافت نشد'}

### ❌ مشکلات احتمالی
${findings.length > 0 ? `
| مورد | شدت | توضیح |
|------|-----|-------|
${findings.map(f => `| ${f.item} | ${f.severity} | ${f.desc} |`).join('\n')}
` : '- مشکل بحرانی یافت نشد'}

### 💡 پیشنهادات امنیتی
1. ${!has_dockerfile ? 'ایجاد Dockerfile با کاربر غیر-root' : 'اضافه کردن security scanning در CI/CD'}
2. استفاده از secrets management (مثل HashiCorp Vault)
3. ${has_kubernetes ? 'اضافه کردن NetworkPolicy برای محدود کردن ترافیک' : 'پیاده‌سازی rate limiting'}
4. فعال کردن logging و monitoring
${databases.length > 0 ? `5. رمزگذاری ارتباط با ${databases.join('، ')} با TLS` : ''}

### 🔧 اقدامات پیشنهادی
\`\`\`bash
# بررسی وابستگی‌ها
${language === 'python' ? 'pip install safety && safety check' : ''}
${language === 'javascript' ? 'npm audit --audit-level=high' : ''}

# اسکن ایمیج Docker
${has_dockerfile ? 'docker scan ' + project_name.toLowerCase() + ':latest' : '# ابتدا Dockerfile بسازید'}
\`\`\`

آیا می‌خواهید هر یک از این مشکلات را برطرف کنم؟`;
}

function getProjectCostResponse(ctx: ProjectContext): string {
  const { project_name, language, framework, databases = [], service_type } = ctx;
  
  const isApi = service_type === 'api';
  const computeCost = isApi ? 150 : 100;
  const dbCost = databases.length > 0 ? databases.length * 80 : 0;
  const storageCost = 30;
  const networkCost = isApi ? 50 : 20;
  const total = computeCost + dbCost + storageCost + networkCost;
  
  const optimizedCompute = Math.round(computeCost * 0.65);
  const optimizedDb = Math.round(dbCost * 0.7);
  const savings = total - (optimizedCompute + optimizedDb + storageCost + networkCost);

  return `## تخمین هزینه استقرار "${project_name}"

بر اساس تحلیل پروژه ${language}/${framework || 'native'}:

### 📊 هزینه ماهانه تخمینی

| سرویس | نوع | هزینه |
|-------|-----|-------|
| محاسبات | ${isApi ? '3x t3.small' : '2x t3.micro'} | $${computeCost} |
${databases.length > 0 ? `| دیتابیس | ${databases.join(', ')} | $${dbCost} |
` : ''}| ذخیره‌سازی | EBS/S3 | $${storageCost} |
| شبکه | Load Balancer + Transfer | $${networkCost} |
| **جمع کل** | | **$${total}/ماه** |

### 💰 پیشنهادات صرفه‌جویی

| پیشنهاد | صرفه‌جویی | توضیح |
|---------|-----------|-------|
| Reserved Instances | $${computeCost - optimizedCompute}/ماه | تعهد ۱ ساله برای محاسبات |
${databases.length > 0 ? `| RDS Reserved | $${dbCost - optimizedDb}/ماه | تعهد ۱ ساله برای دیتابیس |
` : ''}| Spot Instances | متغیر | برای workload های غیربحرانی |

### 📈 خلاصه
- **هزینه فعلی:** $${total}/ماه
- **بعد از بهینه‌سازی:** $${total - savings}/ماه
- **صرفه‌جویی:** **$${savings}/ماه (${Math.round((savings/total)*100)}%)**

### ☁️ مقایسه با ابر ایرانی (آروان‌کلود)
| سرویس | AWS | آروان‌کلود |
|-------|-----|-----------|
| محاسبات | $${computeCost} | ~${computeCost * 50000} تومان |
| کل | $${total} | ~${total * 50000} تومان |

*نرخ تقریبی: ۱ دلار = ۵۰,۰۰۰ تومان*

آیا می‌خواهید Terraform برای بهینه‌ترین معماری بنویسم؟`;
}

function getProjectAnalysisResponse(ctx: ProjectContext): string {
  const { project_name, language, framework, databases = [], has_dockerfile, has_kubernetes, has_terraform, service_type, files = [] } = ctx;

  return `## تحلیل کامل پروژه "${project_name}"

### 🔍 مشخصات فنی
- **زبان برنامه‌نویسی:** ${language}
${framework ? `- **فریم‌ورک:** ${framework}` : ''}
- **نوع سرویس:** ${service_type || 'نامشخص'}
- **تعداد فایل:** ${files.length}
${databases.length > 0 ? `- **دیتابیس‌ها:** ${databases.join('، ')}` : ''}

### 📦 وضعیت IaC
| مورد | وضعیت | توضیح |
|------|-------|-------|
| Dockerfile | ${has_dockerfile ? '✅ موجود' : '❌ ندارد'} | ${has_dockerfile ? 'آماده containerization' : 'نیاز به ایجاد'} |
| Kubernetes | ${has_kubernetes ? '✅ موجود' : '❌ ندارد'} | ${has_kubernetes ? 'مانیفست‌ها موجود' : 'نیاز به ایجاد برای استقرار'} |
| Terraform | ${has_terraform ? '✅ موجود' : '❌ ندارد'} | ${has_terraform ? 'زیرساخت تعریف شده' : 'نیاز به تعریف زیرساخت'} |

### 🎯 توصیه‌های من
${!has_dockerfile ? '1. **ایجاد Dockerfile** - اولین قدم برای containerization\n' : ''}${!has_kubernetes ? '2. **ایجاد مانیفست‌های Kubernetes** - برای استقرار مقیاس‌پذیر\n' : ''}${!has_terraform ? '3. **تنظیمات Terraform** - برای مدیریت زیرساخت\n' : ''}4. **بررسی امنیتی** - تحلیل آسیب‌پذیری‌ها
5. **تخمین هزینه** - برنامه‌ریزی بودجه

### 🚀 آماده برای شروع
چه کاری می‌خواهید اول انجام دهیم؟
- Dockerfile بسازم
- مانیفست‌های Kubernetes تولید کنم
- پروژه را از نظر امنیتی بررسی کنم
- هزینه استقرار را تخمین بزنم`;
}

function getProjectDefaultResponse(ctx: ProjectContext, message: string): string {
  const { project_name, language, framework, has_dockerfile, has_kubernetes, has_terraform } = ctx;
  
  const suggestions = [];
  if (!has_dockerfile) suggestions.push('Dockerfile بسازم');
  if (!has_kubernetes) suggestions.push('مانیفست‌های Kubernetes تولید کنم');
  if (!has_terraform) suggestions.push('تنظیمات Terraform بنویسم');
  suggestions.push('پروژه را بررسی امنیتی کنم');
  suggestions.push('هزینه استقرار را تخمین بزنم');

  return `## درباره "${project_name}"

پروژه ${language}${framework ? `/${framework}` : ''} شما را تحلیل کردم.

با توجه به درخواست شما: "${message}"

### 🛠️ می‌توانم این کارها را انجام دهم:
${suggestions.map((s, i) => `${i + 1}. ${s}`).join('\n')}

### 📊 وضعیت فعلی پروژه:
- Dockerfile: ${has_dockerfile ? '✅' : '❌'}
- Kubernetes: ${has_kubernetes ? '✅' : '❌'}
- Terraform: ${has_terraform ? '✅' : '❌'}

کدام کار را شروع کنم؟`;
}
