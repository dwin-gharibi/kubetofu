'use client';

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send,
  Loader2,
  Copy,
  Check,
  Zap,
  Settings,
  Moon,
  Sun,
  Plus,
  Terminal,
  Shield,
  DollarSign,
  FileCode,
  Server,
  Activity,
  Bot,
  User,
  StopCircle,
  X,
  MessageSquare,
  Trash2,
  Cpu,
  Search,
  CheckCircle,
  AlertCircle,
  Clock,
  PanelLeftClose,
  PanelLeft,
  MoreVertical,
  FolderOpen,
  Upload,
  FolderPlus,
  Package,
  ChevronDown,
  FileText,
  Database,
  Globe,
  Code2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { cn } from '@/lib/utils';
import { useTheme } from '@/components/providers';
import { 
  useChatStore, 
  type ToolCall, 
  type SubAgentActivity,
  type Project,
  type ProjectAnalysis,
  createProjectFromFiles,
  analyzeProjectFiles,
} from '@/lib/store';
import * as api from '@/lib/api';

const SUB_AGENT_INFO: Record<string, { icon: any; name: string; color: string }> = {
  planner: { icon: Cpu, name: 'برنامه‌ریز', color: 'text-blue-400' },
  security: { icon: Shield, name: 'امنیت', color: 'text-green-400' },
  cost: { icon: DollarSign, name: 'هزینه', color: 'text-yellow-400' },
  deployment: { icon: Server, name: 'استقرار', color: 'text-purple-400' },
  diagnostic: { icon: Activity, name: 'تشخیص', color: 'text-orange-400' },
  research: { icon: Search, name: 'تحقیق', color: 'text-cyan-400' },
};

const SERVICE_TYPE_ICONS: Record<string, any> = {
  web: Globe,
  api: Server,
  worker: Cpu,
  static: FileText,
  database: Database,
  unknown: Code2,
};

const getProjectSuggestions = (analysis?: ProjectAnalysis) => {
  if (!analysis) return [];
  
  const suggestions = [];
  
  if (!analysis.hasDockerfile) {
    suggestions.push({
      icon: FileCode,
      text: `یک Dockerfile برای اپلیکیشن ${analysis.framework || analysis.language} بساز`,
      gradient: 'from-blue-500 to-cyan-500',
    });
  }
  
  if (!analysis.hasKubernetes) {
    suggestions.push({
      icon: Server,
      text: 'مانیفست‌های Kubernetes برای استقرار تولید کن',
      gradient: 'from-purple-500 to-pink-500',
    });
  }
  
  if (!analysis.hasTerraform && analysis.databases.length > 0) {
    suggestions.push({
      icon: Terminal,
      text: `تنظیمات Terraform برای ${analysis.databases[0]} بساز`,
      gradient: 'from-orange-500 to-red-500',
    });
  }
  
  suggestions.push({
    icon: Shield,
    text: 'پروژه را از نظر امنیتی بررسی کن',
    gradient: 'from-green-500 to-emerald-500',
  });
  
  suggestions.push({
    icon: DollarSign,
    text: 'هزینه استقرار این پروژه را تخمین بزن',
    gradient: 'from-pink-500 to-rose-500',
  });
  
  return suggestions;
};

const DEFAULT_SUGGESTIONS = [
  { icon: FileCode, text: 'یک Dockerfile برای اپلیکیشن Flask بساز', gradient: 'from-blue-500 to-cyan-500' },
  { icon: Server, text: 'مانیفست‌های Kubernetes برای ۳ رپلیکا تولید کن', gradient: 'from-purple-500 to-pink-500' },
  { icon: Terminal, text: 'تنظیمات Terraform برای VPC با زیرشبکه خصوصی', gradient: 'from-orange-500 to-red-500' },
  { icon: Shield, text: 'کد زیرساخت من را از نظر امنیتی بررسی کن', gradient: 'from-green-500 to-emerald-500' },
  { icon: Activity, text: 'علت CrashLoopBackOff در پادها را پیدا کن', gradient: 'from-yellow-500 to-orange-500' },
  { icon: DollarSign, text: 'هزینه‌های زیرساخت را بهینه‌سازی کن', gradient: 'from-pink-500 to-rose-500' },
];

export default function ChatPage() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  
  const {
    projects,
    currentProjectId,
    sessions,
    currentSessionId,
    agentState,
    isLoading,
    streamingContent,
    isAnalyzingProject,
    addProject,
    updateProject,
    deleteProject,
    setCurrentProject,
    getCurrentProject,
    setProjectAnalysis,
    setAnalyzingProject,
    createSession,
    deleteSession,
    setCurrentSession,
    addMessage,
    setAgentThinking,
    addToolCall,
    updateToolCall,
    clearToolCalls,
    addSubAgentActivity,
    clearSubAgents,
    setLoading,
    setStreamingContent,
    setError,
    getCurrentSession,
  } = useChatStore();
  
  const [input, setInput] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showSidebar, setShowSidebar] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [showProjectSelector, setShowProjectSelector] = useState(false);
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'demo'>('checking');
  const [sessionMenuId, setSessionMenuId] = useState<string | null>(null);
  const [sidebarTab, setSidebarTab] = useState<'chats' | 'projects'>('chats');
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  
  const currentSession = getCurrentSession();
  const currentProject = getCurrentProject();
  const messages = useMemo(() => currentSession?.messages || [], [currentSession?.messages]);
  
  const suggestions = currentProject?.analysis 
    ? getProjectSuggestions(currentProject.analysis)
    : DEFAULT_SUGGESTIONS;

  useEffect(() => {
    const checkApi = async () => {
      const health = await api.checkHealth();
      setApiStatus(health.demo_mode ? 'demo' : 'online');
    };
    checkApi();
    const interval = setInterval(checkApi, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + 'px';
    }
  }, [input]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [currentSessionId]);

  useEffect(() => {
    if (sessions.length === 0) {
      createSession(currentProjectId || undefined);
    } else if (!currentSessionId && sessions.length > 0) {
      setCurrentSession(sessions[0].id);
    }
  }, [sessions, currentSessionId, createSession, setCurrentSession, currentProjectId]);

  const handleProjectUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setAnalyzingProject(true);
    
    try {
      const fileList = Array.from(files);
      const projectName = fileList[0].webkitRelativePath?.split('/')[0] || 'پروژه جدید';
      
      const project = await createProjectFromFiles(projectName, fileList);
      addProject(project);
      
      const sessionId = createSession(project.id);
      setCurrentSession(sessionId);
      
      addMessage(sessionId, {
        role: 'assistant',
        content: getProjectAnalysisMessage(project),
      });
      
      setShowProjectModal(false);
    } catch (error) {
      console.error('Failed to upload project:', error);
      setError('خطا در آپلود پروژه');
    } finally {
      setAnalyzingProject(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const getProjectAnalysisMessage = (project: Project): string => {
    const analysis = project.analysis;
    if (!analysis) return `پروژه "${project.name}" با موفقیت بارگذاری شد.`;

    let message = `## تحلیل پروژه "${project.name}"\n\n`;
    
    message += `### مشخصات\n`;
    message += `- **زبان:** ${analysis.language}\n`;
    if (analysis.framework !== 'none') {
      message += `- **فریم‌ورک:** ${analysis.framework}\n`;
    }
    message += `- **نوع سرویس:** ${analysis.serviceType}\n`;
    message += `- **تعداد فایل:** ${project.files.length}\n`;
    
    if (analysis.databases.length > 0) {
      message += `- **دیتابیس‌ها:** ${analysis.databases.join('، ')}\n`;
    }
    
    if (analysis.ports.length > 0) {
      message += `- **پورت‌ها:** ${analysis.ports.join('، ')}\n`;
    }
    
    message += `\n### وضعیت IaC\n`;
    message += `- Dockerfile: ${analysis.hasDockerfile ? '✅ موجود' : '❌ ندارد'}\n`;
    message += `- Kubernetes: ${analysis.hasKubernetes ? '✅ موجود' : '❌ ندارد'}\n`;
    message += `- Terraform: ${analysis.hasTerraform ? '✅ موجود' : '❌ ندارد'}\n`;
    
    if (analysis.suggestions.length > 0) {
      message += `\n### پیشنهادات\n`;
      analysis.suggestions.forEach(s => {
        message += `- ${s}\n`;
      });
    }
    
    message += `\n---\n\nچه کاری می‌توانم برای این پروژه انجام دهم؟`;
    
    return message;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    let sessionId = currentSessionId;
    if (!sessionId) {
      sessionId = createSession(currentProjectId || undefined);
    }

    const projectContext = currentProject ? {
      project_name: currentProject.name,
      language: currentProject.analysis?.language,
      framework: currentProject.analysis?.framework,
      service_type: currentProject.analysis?.serviceType,
      databases: currentProject.analysis?.databases,
      has_dockerfile: currentProject.analysis?.hasDockerfile,
      has_kubernetes: currentProject.analysis?.hasKubernetes,
      has_terraform: currentProject.analysis?.hasTerraform,
      files: currentProject.files.map(f => ({ name: f.name, path: f.path, language: f.language })),
    } : undefined;

    addMessage(sessionId, {
      role: 'user',
      content: input.trim(),
    });

    const userInput = input.trim();
    setInput('');
    setLoading(true);
    setStreamingContent('');
    setError(null);
    clearToolCalls();
    clearSubAgents();

    abortControllerRef.current = new AbortController();

    try {
      let fullResponse = '';

      const handleEvent = (event: api.StreamEvent) => {
        if (event.type === 'tool_call' && event.tool) {
          if (event.tool.type === 'tool_start') {
            addToolCall({
              name: event.tool.tool_name,
              status: 'running',
              input: event.tool.tool_input,
              startTime: new Date(),
            });
          } else if (event.tool.type === 'tool_end') {
            const toolCalls = useChatStore.getState().agentState.toolCalls;
            const toolCall = toolCalls.find(t => t.name === event.tool?.tool_name && t.status === 'running');
            if (toolCall) {
              updateToolCall(toolCall.id, {
                status: 'completed',
                output: event.tool.tool_output,
                endTime: new Date(),
              });
            }
          }
        } else if (event.type === 'agent_event' && event.agent) {
          if (event.agent.type === 'agent_thinking') {
            setAgentThinking(true, event.agent.agent_name);
            addSubAgentActivity({
              type: 'planner',
              name: event.agent.agent_name || 'عامل',
              status: 'thinking',
              message: event.agent.message || 'در حال تحلیل...',
            });
          }
        }
      };

      for await (const chunk of api.streamChat(userInput, sessionId, projectContext, handleEvent)) {
        if (abortControllerRef.current?.signal.aborted) break;
        fullResponse += chunk;
        setStreamingContent(fullResponse);
      }

      if (!abortControllerRef.current?.signal.aborted && fullResponse) {
        addMessage(sessionId, {
          role: 'assistant',
          content: fullResponse,
          toolCalls: useChatStore.getState().agentState.toolCalls,
        });
      }
      
      setStreamingContent('');
      setAgentThinking(false);
      clearToolCalls();
      clearSubAgents();
    } catch (err) {
      if (!abortControllerRef.current?.signal.aborted) {
        console.error('Chat error:', err);
        setError('متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید.');
        addMessage(sessionId, {
          role: 'assistant',
          content: 'متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید.',
        });
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleSuggestionClick = (text: string) => {
    setInput(text);
    inputRef.current?.focus();
  };

  const handleCopy = async (content: string, id: string) => {
    await navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleNewChat = (withProject?: string) => {
    const id = createSession(withProject || currentProjectId || undefined);
    setCurrentSession(id);
    setStreamingContent('');
    clearToolCalls();
    clearSubAgents();
  };

  const handleSelectProject = (projectId: string | null) => {
    setCurrentProject(projectId);
    setShowProjectSelector(false);
    
    if (projectId) {
      const projectSessions = sessions.filter(s => s.projectId === projectId);
      if (projectSessions.length > 0) {
        setCurrentSession(projectSessions[0].id);
      } else {
        handleNewChat(projectId);
      }
    }
  };

  const handleDeleteSession = (id: string) => {
    deleteSession(id);
    setSessionMenuId(null);
  };

  const handleStopGeneration = () => {
    abortControllerRef.current?.abort();
    setLoading(false);
    if (streamingContent && currentSessionId) {
      addMessage(currentSessionId, {
        role: 'assistant',
        content: streamingContent,
      });
      setStreamingContent('');
    }
  };

  const CodeBlock = useCallback(({ language, children }: { language: string; children: string }) => (
    <div className="relative group my-4 rounded-xl overflow-hidden" dir="ltr">
      <div className="flex items-center justify-between px-4 py-2 bg-zinc-800 text-zinc-400 text-xs">
        <span>{language}</span>
        <button
          onClick={() => handleCopy(children, `code-${children.substring(0, 20)}`)}
          className="flex items-center gap-1 hover:text-white transition-colors"
        >
          {copiedId === `code-${children.substring(0, 20)}` ? (
            <><Check className="h-3 w-3" /> کپی شد</>
          ) : (
            <><Copy className="h-3 w-3" /> کپی کد</>
          )}
        </button>
      </div>
      <SyntaxHighlighter language={language} style={oneDark} customStyle={{ margin: 0, borderRadius: 0, fontSize: '13px' }}>
        {children}
      </SyntaxHighlighter>
    </div>
  ), [copiedId]);

  const ToolCallItem = ({ tool }: { tool: ToolCall }) => (
    <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-secondary/50 text-sm">
      <div className={cn(
        'h-6 w-6 rounded-full flex items-center justify-center',
        tool.status === 'running' && 'bg-blue-500/20 text-blue-400',
        tool.status === 'completed' && 'bg-green-500/20 text-green-400',
        tool.status === 'failed' && 'bg-red-500/20 text-red-400',
      )}>
        {tool.status === 'running' && <Loader2 className="h-3 w-3 animate-spin" />}
        {tool.status === 'completed' && <CheckCircle className="h-3 w-3" />}
        {tool.status === 'failed' && <AlertCircle className="h-3 w-3" />}
      </div>
      <span className="font-medium">{tool.name}</span>
      {tool.status === 'running' && <span className="text-xs text-muted-foreground">در حال اجرا...</span>}
    </motion.div>
  );

  const SubAgentItem = ({ agent }: { agent: SubAgentActivity }) => {
    const info = SUB_AGENT_INFO[agent.type] || { icon: Bot, name: agent.name, color: 'text-primary' };
    const Icon = info.icon;
    return (
      <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className="flex items-center gap-2 text-sm py-1">
        <Icon className={cn('h-4 w-4', info.color)} />
        <span className="font-medium">{info.name}</span>
        <span className="text-muted-foreground">-</span>
        <span className="text-muted-foreground">{agent.message}</span>
        {agent.status === 'thinking' && <div className="loading-dots mr-2"><span></span><span></span><span></span></div>}
      </motion.div>
    );
  };

  return (
    <div className="flex h-screen bg-background">
      <AnimatePresence mode="wait">
        {showSidebar && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 300, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="flex flex-col border-l bg-card overflow-hidden"
          >
            <div className="flex items-center justify-between p-4 border-b">
              <Link href="/" className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-purple-600">
                  <Zap className="h-4 w-4 text-white" />
                </div>
                <span className="font-semibold gradient-text">کیوب‌توفو</span>
              </Link>
              <button onClick={() => setShowSidebar(false)} className="btn-ghost btn-icon h-8 w-8">
                <PanelLeftClose className="h-4 w-4" />
              </button>
            </div>

            <div className="flex border-b">
              <button
                onClick={() => setSidebarTab('chats')}
                className={cn(
                  'flex-1 py-2.5 text-sm font-medium transition-colors',
                  sidebarTab === 'chats' ? 'border-b-2 border-primary text-primary' : 'text-muted-foreground hover:text-foreground'
                )}
              >
                گفتگوها
              </button>
              <button
                onClick={() => setSidebarTab('projects')}
                className={cn(
                  'flex-1 py-2.5 text-sm font-medium transition-colors',
                  sidebarTab === 'projects' ? 'border-b-2 border-primary text-primary' : 'text-muted-foreground hover:text-foreground'
                )}
              >
                پروژه‌ها
              </button>
            </div>

            {sidebarTab === 'chats' ? (
              <>
                <div className="p-3">
                  <button
                    onClick={() => handleNewChat()}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                  >
                    <Plus className="h-4 w-4" />
                    <span>گفتگوی جدید</span>
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto p-2">
                  <div className="space-y-1">
                    {sessions.map((session) => {
                      const sessionProject = projects.find(p => p.id === session.projectId);
                      return (
                        <div
                          key={session.id}
                          className={cn(
                            'group relative flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-colors',
                            session.id === currentSessionId ? 'bg-primary/10 text-primary' : 'hover:bg-accent'
                          )}
                          onClick={() => setCurrentSession(session.id)}
                        >
                          <MessageSquare className="h-4 w-4 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <span className="block truncate text-sm">{session.title}</span>
                            {sessionProject && (
                              <span className="text-xs text-muted-foreground flex items-center gap-1">
                                <Package className="h-3 w-3" />
                                {sessionProject.name}
                              </span>
                            )}
                          </div>
                          <button
                            onClick={(e) => { e.stopPropagation(); setSessionMenuId(sessionMenuId === session.id ? null : session.id); }}
                            className="opacity-0 group-hover:opacity-100 btn-ghost h-6 w-6 p-0"
                          >
                            <MoreVertical className="h-3 w-3" />
                          </button>
                          {sessionMenuId === session.id && (
                            <>
                              <div className="fixed inset-0 z-10" onClick={() => setSessionMenuId(null)} />
                              <div className="absolute left-0 top-full mt-1 w-32 rounded-lg border bg-popover p-1 shadow-lg z-20">
                                <button
                                  onClick={(e) => { e.stopPropagation(); handleDeleteSession(session.id); }}
                                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-destructive hover:bg-destructive/10"
                                >
                                  <Trash2 className="h-3 w-3" />
                                  حذف
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="p-3">
                  <button
                    onClick={() => setShowProjectModal(true)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                  >
                    <FolderPlus className="h-4 w-4" />
                    <span>افزودن پروژه</span>
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-2">
                  <div className="space-y-1">
                    {projects.length === 0 ? (
                      <div className="text-center py-8 text-muted-foreground text-sm">
                        <FolderOpen className="h-8 w-8 mx-auto mb-2 opacity-50" />
                        <p>پروژه‌ای وجود ندارد</p>
                        <p className="text-xs mt-1">یک پروژه آپلود کنید</p>
                      </div>
                    ) : (
                      projects.map((project) => {
                        const ServiceIcon = SERVICE_TYPE_ICONS[project.analysis?.serviceType || 'unknown'];
                        return (
                          <div
                            key={project.id}
                            className={cn(
                              'group flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-colors',
                              project.id === currentProjectId ? 'bg-primary/10 text-primary' : 'hover:bg-accent'
                            )}
                            onClick={() => handleSelectProject(project.id)}
                          >
                            <div className="h-8 w-8 rounded-lg bg-secondary flex items-center justify-center">
                              <ServiceIcon className="h-4 w-4" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <span className="block truncate text-sm font-medium">{project.name}</span>
                              <span className="text-xs text-muted-foreground">
                                {project.analysis?.language} • {project.files.length} فایل
                              </span>
                            </div>
                            <button
                              onClick={(e) => { e.stopPropagation(); deleteProject(project.id); }}
                              className="opacity-0 group-hover:opacity-100 btn-ghost h-6 w-6 p-0 text-destructive"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </>
            )}

            <div className="p-3 border-t">
              <div className={cn(
                'flex items-center gap-2 px-3 py-2 rounded-lg text-xs',
                apiStatus === 'online' && 'bg-green-500/10 text-green-500',
                apiStatus === 'demo' && 'bg-yellow-500/10 text-yellow-500',
                apiStatus === 'checking' && 'bg-muted text-muted-foreground'
              )}>
                <span className={cn(
                  'w-2 h-2 rounded-full',
                  apiStatus === 'online' && 'bg-green-500',
                  apiStatus === 'demo' && 'bg-yellow-500',
                  apiStatus === 'checking' && 'bg-muted-foreground'
                )} />
                <span>
                  {apiStatus === 'online' && 'متصل به سرور'}
                  {apiStatus === 'demo' && 'حالت دمو'}
                  {apiStatus === 'checking' && 'در حال بررسی...'}
                </span>
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      <div className="flex-1 flex flex-col">
        <header className="flex items-center justify-between px-4 h-14 border-b bg-background/80 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            {!showSidebar && (
              <button onClick={() => setShowSidebar(true)} className="btn-ghost btn-icon h-9 w-9">
                <PanelLeft className="h-4 w-4" />
              </button>
            )}
            
            <div className="relative">
              <button
                onClick={() => setShowProjectSelector(!showProjectSelector)}
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors',
                  currentProject ? 'bg-primary/10 text-primary' : 'hover:bg-accent'
                )}
              >
                {currentProject ? (
                  <>
                    <Package className="h-4 w-4" />
                    <span className="text-sm font-medium">{currentProject.name}</span>
                  </>
                ) : (
                  <>
                    <FolderOpen className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">انتخاب پروژه</span>
                  </>
                )}
                <ChevronDown className="h-3 w-3" />
              </button>
              
              {showProjectSelector && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowProjectSelector(false)} />
                  <div className="absolute top-full right-0 mt-2 w-64 rounded-xl border bg-popover p-2 shadow-lg z-50">
                    <button
                      onClick={() => handleSelectProject(null)}
                      className={cn(
                        'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors',
                        !currentProjectId ? 'bg-accent' : 'hover:bg-accent'
                      )}
                    >
                      <Globe className="h-4 w-4" />
                      <span>بدون پروژه</span>
                    </button>
                    {projects.length > 0 && <div className="border-t my-2" />}
                    {projects.map((project) => (
                      <button
                        key={project.id}
                        onClick={() => handleSelectProject(project.id)}
                        className={cn(
                          'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors',
                          project.id === currentProjectId ? 'bg-primary/10 text-primary' : 'hover:bg-accent'
                        )}
                      >
                        <Package className="h-4 w-4" />
                        <span className="truncate">{project.name}</span>
                      </button>
                    ))}
                    <div className="border-t my-2" />
                    <button
                      onClick={() => { setShowProjectSelector(false); setShowProjectModal(true); }}
                      className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-primary hover:bg-primary/10 transition-colors"
                    >
                      <FolderPlus className="h-4 w-4" />
                      <span>افزودن پروژه جدید</span>
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')} className="btn-ghost btn-icon h-9 w-9">
              {resolvedTheme === 'dark' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            </button>
            <button onClick={() => setShowSettings(!showSettings)} className={cn('btn-ghost btn-icon h-9 w-9', showSettings && 'bg-accent')}>
              <Settings className="h-4 w-4" />
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4">
            {messages.length === 0 && !streamingContent ? (
              <div className="flex flex-col items-center justify-center min-h-[calc(100vh-14rem)] text-center py-8">
                {!currentProject ? (
                  <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="max-w-xl">
                    <div className="h-24 w-24 mx-auto rounded-3xl bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 flex items-center justify-center mb-6 shadow-glow">
                      <Zap className="h-12 w-12 text-white" />
                    </div>
                    <h1 className="text-2xl md:text-3xl font-bold mb-3">
                      عامل هوشمند IaC کیوب‌توفو
                    </h1>
                    <p className="text-muted-foreground mb-6 text-lg">
                      برای شروع، پروژه نرم‌افزاری خود را آپلود کنید تا زیرساخت مناسب آن را تولید کنم
                    </p>
                    
                    <motion.div
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.2 }}
                      onClick={() => setShowProjectModal(true)}
                      className="mx-auto max-w-md p-6 rounded-2xl border-2 border-dashed border-primary/30 bg-primary/5 hover:bg-primary/10 hover:border-primary/50 cursor-pointer transition-all group"
                    >
                      <div className="h-16 w-16 mx-auto rounded-2xl bg-primary/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                        <Upload className="h-8 w-8 text-primary" />
                      </div>
                      <h3 className="font-semibold text-lg mb-2">آپلود پروژه</h3>
                      <p className="text-sm text-muted-foreground mb-4">
                        پوشه پروژه خود را انتخاب کنید. من به طور خودکار زبان، فریم‌ورک و وابستگی‌ها را شناسایی می‌کنم.
                      </p>
                      <div className="flex flex-wrap justify-center gap-2 text-xs">
                        <span className="px-2 py-1 rounded-full bg-blue-500/20 text-blue-400">Python</span>
                        <span className="px-2 py-1 rounded-full bg-yellow-500/20 text-yellow-400">JavaScript</span>
                        <span className="px-2 py-1 rounded-full bg-cyan-500/20 text-cyan-400">Go</span>
                        <span className="px-2 py-1 rounded-full bg-purple-500/20 text-purple-400">TypeScript</span>
                      </div>
                    </motion.div>
                    
                    <motion.div
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.3 }}
                      className="mt-8"
                    >
                      <p className="text-sm text-muted-foreground mb-4">بعد از آپلود پروژه، می‌توانم:</p>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div className="p-3 rounded-xl bg-secondary/50 text-center">
                          <FileCode className="h-5 w-5 mx-auto mb-2 text-blue-400" />
                          <span className="text-xs">Dockerfile بسازم</span>
                        </div>
                        <div className="p-3 rounded-xl bg-secondary/50 text-center">
                          <Server className="h-5 w-5 mx-auto mb-2 text-purple-400" />
                          <span className="text-xs">Kubernetes تولید کنم</span>
                        </div>
                        <div className="p-3 rounded-xl bg-secondary/50 text-center">
                          <Terminal className="h-5 w-5 mx-auto mb-2 text-orange-400" />
                          <span className="text-xs">Terraform بنویسم</span>
                        </div>
                        <div className="p-3 rounded-xl bg-secondary/50 text-center">
                          <Shield className="h-5 w-5 mx-auto mb-2 text-green-400" />
                          <span className="text-xs">امنیت بررسی کنم</span>
                        </div>
                      </div>
                    </motion.div>
                    
                    {projects.length > 0 && (
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.4 }}
                        className="mt-6"
                      >
                        <p className="text-sm text-muted-foreground mb-3">یا یکی از پروژه‌های قبلی را انتخاب کنید:</p>
                        <div className="flex flex-wrap justify-center gap-2">
                          {projects.slice(0, 4).map((project) => (
                            <button
                              key={project.id}
                              onClick={() => handleSelectProject(project.id)}
                              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary hover:bg-secondary/80 transition-colors text-sm"
                            >
                              <Package className="h-4 w-4" />
                              {project.name}
                            </button>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </motion.div>
                ) : (
                  <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="mb-8 w-full max-w-2xl">
                    <div className="h-20 w-20 mx-auto rounded-3xl bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 flex items-center justify-center mb-6 shadow-glow">
                      <Zap className="h-10 w-10 text-white" />
                    </div>
                    <h1 className="text-2xl md:text-3xl font-bold mb-2">
                      بیایید روی &ldquo;{currentProject.name}&rdquo; کار کنیم
                    </h1>
                    
                    {currentProject.analysis && (
                      <div className="mt-4 p-4 rounded-xl bg-secondary/50 text-right">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          <div>
                            <span className="text-muted-foreground block mb-1">زبان</span>
                            <span className="font-medium">{currentProject.analysis.language}</span>
                          </div>
                          {currentProject.analysis.framework !== 'none' && (
                            <div>
                              <span className="text-muted-foreground block mb-1">فریم‌ورک</span>
                              <span className="font-medium">{currentProject.analysis.framework}</span>
                            </div>
                          )}
                          <div>
                            <span className="text-muted-foreground block mb-1">فایل‌ها</span>
                            <span className="font-medium">{currentProject.files.length}</span>
                          </div>
                          {currentProject.analysis.databases.length > 0 && (
                            <div>
                              <span className="text-muted-foreground block mb-1">دیتابیس</span>
                              <span className="font-medium">{currentProject.analysis.databases.join(', ')}</span>
                            </div>
                          )}
                        </div>

                        <div className="mt-4 pt-4 border-t border-border/50 flex flex-wrap gap-3 justify-center">
                          <span className={cn(
                            'px-3 py-1 rounded-full text-xs',
                            currentProject.analysis.hasDockerfile ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                          )}>
                            {currentProject.analysis.hasDockerfile ? '✓' : '✗'} Dockerfile
                          </span>
                          <span className={cn(
                            'px-3 py-1 rounded-full text-xs',
                            currentProject.analysis.hasKubernetes ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                          )}>
                            {currentProject.analysis.hasKubernetes ? '✓' : '✗'} Kubernetes
                          </span>
                          <span className={cn(
                            'px-3 py-1 rounded-full text-xs',
                            currentProject.analysis.hasTerraform ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                          )}>
                            {currentProject.analysis.hasTerraform ? '✓' : '✗'} Terraform
                          </span>
                        </div>
                      </div>
                    )}
                    
                    <p className="text-muted-foreground mt-4 mb-6">
                      چه کاری می‌توانم برای این پروژه انجام دهم؟
                    </p>
                    
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 w-full">
                      {suggestions.slice(0, 6).map((suggestion, i) => (
                        <motion.button
                          key={i}
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: 0.1 + i * 0.05 }}
                          onClick={() => handleSuggestionClick(suggestion.text)}
                          className="card-interactive p-4 text-right group"
                        >
                          <div className={cn('h-8 w-8 rounded-lg bg-gradient-to-br mb-3 flex items-center justify-center', suggestion.gradient)}>
                            <suggestion.icon className="h-4 w-4 text-white" />
                          </div>
                          <p className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">
                            {suggestion.text}
                          </p>
                        </motion.button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </div>
            ) : (
              <div className="py-6 space-y-6">
                <AnimatePresence initial={false}>
                  {messages.map((message) => (
                    <motion.div
                      key={message.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={cn('flex gap-4', message.role === 'user' && 'flex-row-reverse')}
                    >
                      <div className={cn(
                        'flex-shrink-0 h-9 w-9 rounded-xl flex items-center justify-center',
                        message.role === 'assistant' ? 'bg-gradient-to-br from-blue-500 to-purple-600' : 'bg-primary'
                      )}>
                        {message.role === 'assistant' ? <Bot className="h-5 w-5 text-white" /> : <User className="h-5 w-5 text-primary-foreground" />}
                      </div>
                      <div className={cn('flex-1 max-w-[85%]', message.role === 'user' && 'text-left')}>
                        {message.toolCalls && message.toolCalls.length > 0 && (
                          <div className="mb-3 space-y-2">
                            {message.toolCalls.map((tool) => <ToolCallItem key={tool.id} tool={tool} />)}
                          </div>
                        )}
                        <div className={cn(
                          'inline-block rounded-2xl px-4 py-3',
                          message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-secondary'
                        )}>
                          {message.role === 'assistant' ? (
                            <div className="prose prose-invert prose-sm max-w-none">
                              <ReactMarkdown
                                components={{
                                  code({ node, className, children, ...props }) {
                                    const match = /language-(\w+)/.exec(className || '');
                                    return match ? (
                                      <CodeBlock language={match[1]}>{String(children).replace(/\n$/, '')}</CodeBlock>
                                    ) : (
                                      <code className="bg-zinc-800 px-1.5 py-0.5 rounded text-sm" {...props}>{children}</code>
                                    );
                                  },
                                }}
                              >
                                {message.content}
                              </ReactMarkdown>
                            </div>
                          ) : (
                            <p className="whitespace-pre-wrap">{message.content}</p>
                          )}
                        </div>
                        {message.role === 'assistant' && (
                          <div className="flex items-center gap-2 mt-2">
                            <button onClick={() => handleCopy(message.content, message.id)} className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
                              {copiedId === message.id ? <><Check className="h-3 w-3" /> کپی شد</> : <><Copy className="h-3 w-3" /> کپی</>}
                            </button>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>

                {(streamingContent || isLoading) && (
                  <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex gap-4">
                    <div className="flex-shrink-0 h-9 w-9 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                      <Bot className="h-5 w-5 text-white" />
                    </div>
                    <div className="flex-1">
                      {agentState.toolCalls.length > 0 && (
                        <div className="mb-3 space-y-2">
                          {agentState.toolCalls.map((tool) => <ToolCallItem key={tool.id} tool={tool} />)}
                        </div>
                      )}
                      {agentState.subAgents.length > 0 && (
                        <div className="mb-3 py-2 px-3 rounded-lg bg-secondary/30">
                          {agentState.subAgents.map((agent) => <SubAgentItem key={agent.id} agent={agent} />)}
                        </div>
                      )}
                      {streamingContent ? (
                        <div className="inline-block rounded-2xl px-4 py-3 bg-secondary">
                          <div className="prose prose-invert prose-sm max-w-none">
                            <ReactMarkdown
                              components={{
                                code({ node, className, children, ...props }) {
                                  const match = /language-(\w+)/.exec(className || '');
                                  return match ? (
                                    <CodeBlock language={match[1]}>{String(children).replace(/\n$/, '')}</CodeBlock>
                                  ) : (
                                    <code className="bg-zinc-800 px-1.5 py-0.5 rounded text-sm" {...props}>{children}</code>
                                  );
                                },
                              }}
                            >
                              {streamingContent}
                            </ReactMarkdown>
                          </div>
                          <span className="inline-block w-2 h-4 bg-primary animate-pulse mr-1" />
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 px-4 py-3 rounded-2xl bg-secondary">
                          <div className="loading-dots"><span></span><span></span><span></span></div>
                          <span className="text-sm text-muted-foreground">
                            {agentState.isThinking ? `${agentState.currentAgent || 'عامل'} در حال فکر کردن...` : 'در حال پردازش...'}
                          </span>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </div>

        <div className="border-t bg-background/80 backdrop-blur-xl p-4">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            <div className="relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e); }}}
                placeholder={currentProject ? `درباره "${currentProject.name}" بپرسید...` : 'پیام خود را بنویسید...'}
                className="input resize-none py-4 pl-14 min-h-[56px] max-h-[200px]"
                rows={1}
                disabled={isLoading}
              />
              <div className="absolute bottom-3 left-3 flex items-center gap-2">
                {isLoading ? (
                  <button type="button" onClick={handleStopGeneration} className="btn-ghost btn-icon h-8 w-8 text-red-500 hover:text-red-600" title="توقف">
                    <StopCircle className="h-4 w-4" />
                  </button>
                ) : (
                  <button type="submit" disabled={!input.trim() || isLoading} className="btn-primary h-8 w-8 p-0 rounded-lg disabled:opacity-50">
                    <Send className="h-4 w-4 rotate-180" />
                  </button>
                )}
              </div>
            </div>
            <p className="text-xs text-center text-muted-foreground mt-3">
              کیوب‌توفو ممکن است اشتباه کند. تغییرات مهم زیرساختی را همیشه بررسی کنید.
            </p>
          </form>
        </div>
      </div>

      <AnimatePresence>
        {showProjectModal && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-black/50 z-50" onClick={() => setShowProjectModal(false)} />
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-card rounded-2xl border shadow-xl z-50 p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold">افزودن پروژه</h2>
                <button onClick={() => setShowProjectModal(false)} className="btn-ghost btn-icon h-8 w-8">
                  <X className="h-4 w-4" />
                </button>
              </div>
              
              <div className="space-y-4">
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed rounded-xl p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
                >
                  {isAnalyzingProject ? (
                    <div className="flex flex-col items-center gap-3">
                      <Loader2 className="h-10 w-10 text-primary animate-spin" />
                      <p className="text-sm text-muted-foreground">در حال تحلیل پروژه...</p>
                    </div>
                  ) : (
                    <>
                      <Upload className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
                      <p className="font-medium mb-1">پوشه پروژه را انتخاب کنید</p>
                      <p className="text-sm text-muted-foreground">یا فایل‌ها را اینجا رها کنید</p>
                    </>
                  )}
                </div>
                
                <input
                  ref={fileInputRef}
                  type="file"
                  webkitdirectory="true"
                  directory="true"
                  multiple
                  onChange={handleProjectUpload}
                  className="hidden"
                />
                
                <p className="text-xs text-muted-foreground text-center">
                  پروژه به صورت محلی تحلیل می‌شود و فقط اطلاعات ضروری به سرور ارسال می‌شود
                </p>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showSettings && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-black/50 z-40" onClick={() => setShowSettings(false)} />
            <motion.div initial={{ opacity: 0, x: -300 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -300 }} className="fixed top-0 right-0 bottom-0 w-80 bg-card border-r z-50 overflow-y-auto">
              <div className="flex items-center justify-between p-4 border-b">
                <h2 className="text-lg font-semibold">تنظیمات</h2>
                <button onClick={() => setShowSettings(false)} className="btn-ghost btn-icon h-8 w-8"><X className="h-4 w-4" /></button>
              </div>
              <div className="p-4 space-y-6">
                <div>
                  <h3 className="text-sm font-medium mb-3">تم</h3>
                  <div className="grid grid-cols-3 gap-2">
                    {[{ value: 'light', label: 'روشن', icon: Sun }, { value: 'dark', label: 'تیره', icon: Moon }, { value: 'system', label: 'سیستم', icon: Settings }].map((option) => (
                      <button key={option.value} onClick={() => setTheme(option.value as any)} className={cn('p-3 rounded-xl border text-sm transition-all', theme === option.value ? 'border-primary bg-primary/10' : 'border-border hover:bg-accent')}>
                        <option.icon className="h-4 w-4 mx-auto mb-1" />
                        <span className="block">{option.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <div className="pt-4 border-t">
                  <p className="text-sm text-muted-foreground">کیوب‌توفو نسخه ۲.۰.۰</p>
                  <p className="text-xs text-muted-foreground mt-1">عامل هوشمند زیرساخت با هوش مصنوعی</p>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
