import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { generateId } from './utils';

export interface ProjectFile {
  name: string;
  path: string;
  language: string;
  content?: string;
}

export interface ProjectAnalysis {
  language: string;
  framework: string;
  serviceType: string;
  databases: string[];
  ports: number[];
  hasDockerfile: boolean;
  hasKubernetes: boolean;
  hasTerraform: boolean;
  suggestions: string[];
}

export interface Project {
  id: string;
  name: string;
  files: ProjectFile[];
  analysis?: ProjectAnalysis;
  createdAt: Date;
  updatedAt: Date;
}

export interface ToolCall {
  id: string;
  name: string;
  status: 'running' | 'completed' | 'failed';
  input?: Record<string, any>;
  output?: string;
  error?: string;
  startTime?: Date;
  endTime?: Date;
}

export interface SubAgentActivity {
  id: string;
  type: string;
  name: string;
  status: 'thinking' | 'executing' | 'completed' | 'failed';
  message?: string;
  startTime?: Date;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
  metadata?: Record<string, any>;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  projectId?: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface AgentState {
  isThinking: boolean;
  currentAgent?: string;
  toolCalls: ToolCall[];
  subAgents: SubAgentActivity[];
}

interface ChatStore {
  projects: Project[];
  currentProjectId: string | null;
  isAnalyzingProject: boolean;
  sessions: ChatSession[];
  currentSessionId: string | null;
  agentState: AgentState;
  isLoading: boolean;
  streamingContent: string;
  error: string | null;
  addProject: (project: Project) => void;
  updateProject: (id: string, updates: Partial<Project>) => void;
  deleteProject: (id: string) => void;
  setCurrentProject: (id: string | null) => void;
  getCurrentProject: () => Project | undefined;
  setProjectAnalysis: (id: string, analysis: ProjectAnalysis) => void;
  setAnalyzingProject: (analyzing: boolean) => void;
  createSession: (projectId?: string) => string;
  updateSession: (id: string, updates: Partial<ChatSession>) => void;
  deleteSession: (id: string) => void;
  setCurrentSession: (id: string | null) => void;
  getCurrentSession: () => ChatSession | undefined;
  addMessage: (sessionId: string, message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  updateMessage: (sessionId: string, messageId: string, updates: Partial<ChatMessage>) => void;
  clearMessages: (sessionId: string) => void;
  setAgentThinking: (thinking: boolean, agent?: string) => void;
  addToolCall: (tool: Omit<ToolCall, 'id'>) => void;
  updateToolCall: (id: string, updates: Partial<ToolCall>) => void;
  clearToolCalls: () => void;
  addSubAgentActivity: (activity: Omit<SubAgentActivity, 'id' | 'startTime'>) => void;
  updateSubAgentActivity: (id: string, updates: Partial<SubAgentActivity>) => void;
  clearSubAgents: () => void;
  setLoading: (loading: boolean) => void;
  setStreamingContent: (content: string) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const initialAgentState: AgentState = {
  isThinking: false,
  currentAgent: undefined,
  toolCalls: [],
  subAgents: [],
};

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      projects: [],
      currentProjectId: null,
      isAnalyzingProject: false,
      sessions: [],
      currentSessionId: null,
      agentState: initialAgentState,
      isLoading: false,
      streamingContent: '',
      error: null,

      addProject: (project) => set((state) => ({
        projects: [...state.projects, project],
        currentProjectId: project.id,
      })),

      updateProject: (id, updates) => set((state) => ({
        projects: state.projects.map((p) =>
          p.id === id ? { ...p, ...updates, updatedAt: new Date() } : p
        ),
      })),

      deleteProject: (id) => set((state) => ({
        projects: state.projects.filter((p) => p.id !== id),
        currentProjectId: state.currentProjectId === id ? null : state.currentProjectId,
        sessions: state.sessions.map((s) =>
          s.projectId === id ? { ...s, projectId: undefined } : s
        ),
      })),

      setCurrentProject: (id) => set({ currentProjectId: id }),

      getCurrentProject: () => {
        const state = get();
        return state.projects.find((p) => p.id === state.currentProjectId);
      },

      setProjectAnalysis: (id, analysis) => set((state) => ({
        projects: state.projects.map((p) =>
          p.id === id ? { ...p, analysis, updatedAt: new Date() } : p
        ),
      })),

      setAnalyzingProject: (analyzing) => set({ isAnalyzingProject: analyzing }),

      createSession: (projectId) => {
        const id = generateId();
        const session: ChatSession = {
          id,
          title: 'گفتگوی جدید',
          messages: [],
          projectId,
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        set((state) => ({
          sessions: [session, ...state.sessions],
          currentSessionId: id,
        }));
        return id;
      },

      updateSession: (id, updates) => set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === id ? { ...s, ...updates, updatedAt: new Date() } : s
        ),
      })),

      deleteSession: (id) => set((state) => {
        const filteredSessions = state.sessions.filter((s) => s.id !== id);
        return {
          sessions: filteredSessions,
          currentSessionId:
            state.currentSessionId === id
              ? filteredSessions[0]?.id || null
              : state.currentSessionId,
        };
      }),

      setCurrentSession: (id) => set({ currentSessionId: id }),

      getCurrentSession: () => {
        const state = get();
        return state.sessions.find((s) => s.id === state.currentSessionId);
      },

      addMessage: (sessionId, message) => set((state) => {
        const fullMessage: ChatMessage = {
          ...message,
          id: generateId(),
          timestamp: new Date(),
        };

        const session = state.sessions.find((s) => s.id === sessionId);
        const isFirstUserMessage =
          message.role === 'user' &&
          session &&
          session.messages.filter((m) => m.role === 'user').length === 0;

        return {
          sessions: state.sessions.map((s) =>
            s.id === sessionId
              ? {
                  ...s,
                  messages: [...s.messages, fullMessage],
                  title: isFirstUserMessage ? message.content.slice(0, 50) : s.title,
                  updatedAt: new Date(),
                }
              : s
          ),
        };
      }),

      updateMessage: (sessionId, messageId, updates) => set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === sessionId
            ? {
                ...s,
                messages: s.messages.map((m) =>
                  m.id === messageId ? { ...m, ...updates } : m
                ),
                updatedAt: new Date(),
              }
            : s
        ),
      })),

      clearMessages: (sessionId) => set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === sessionId
            ? { ...s, messages: [], title: 'گفتگوی جدید', updatedAt: new Date() }
            : s
        ),
      })),

      setAgentThinking: (thinking, agent) => set((state) => ({
        agentState: {
          ...state.agentState,
          isThinking: thinking,
          currentAgent: thinking ? agent : undefined,
        },
      })),

      addToolCall: (tool) => set((state) => ({
        agentState: {
          ...state.agentState,
          toolCalls: [
            ...state.agentState.toolCalls,
            { ...tool, id: generateId() },
          ],
        },
      })),

      updateToolCall: (id, updates) => set((state) => ({
        agentState: {
          ...state.agentState,
          toolCalls: state.agentState.toolCalls.map((t) =>
            t.id === id ? { ...t, ...updates } : t
          ),
        },
      })),

      clearToolCalls: () => set((state) => ({
        agentState: { ...state.agentState, toolCalls: [] },
      })),

      addSubAgentActivity: (activity) => set((state) => ({
        agentState: {
          ...state.agentState,
          subAgents: [
            ...state.agentState.subAgents,
            { ...activity, id: generateId(), startTime: new Date() },
          ],
        },
      })),

      updateSubAgentActivity: (id, updates) => set((state) => ({
        agentState: {
          ...state.agentState,
          subAgents: state.agentState.subAgents.map((a) =>
            a.id === id ? { ...a, ...updates } : a
          ),
        },
      })),

      clearSubAgents: () => set((state) => ({
        agentState: { ...state.agentState, subAgents: [] },
      })),

      setLoading: (loading) => set({ isLoading: loading }),
      setStreamingContent: (content) => set({ streamingContent: content }),
      setError: (error) => set({ error }),

      reset: () => set({
        projects: [],
        currentProjectId: null,
        isAnalyzingProject: false,
        sessions: [],
        currentSessionId: null,
        agentState: initialAgentState,
        isLoading: false,
        streamingContent: '',
        error: null,
      }),
    }),
    {
      name: 'kubetofu-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        projects: state.projects,
        sessions: state.sessions.map((s) => ({
          ...s,
          messages: s.messages.slice(-100),
        })),
        currentProjectId: state.currentProjectId,
        currentSessionId: state.currentSessionId,
      }),
    }
  )
);

export async function createProjectFromFiles(
  name: string,
  files: File[]
): Promise<Project> {
  const projectFiles: ProjectFile[] = [];
  
  for (const file of files) {
    if (
      file.name.startsWith('.') ||
      file.webkitRelativePath?.includes('node_modules') ||
      file.webkitRelativePath?.includes('.git') ||
      file.webkitRelativePath?.includes('__pycache__') ||
      file.webkitRelativePath?.includes('.venv')
    ) {
      continue;
    }
    
    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    const textExtensions = [
      'js', 'jsx', 'ts', 'tsx', 'py', 'go', 'rs', 'java', 'rb', 'php',
      'html', 'css', 'scss', 'sass', 'less',
      'json', 'yaml', 'yml', 'toml', 'xml',
      'md', 'txt', 'rst',
      'sh', 'bash', 'zsh',
      'sql', 'graphql', 'prisma',
      'dockerfile', 'tf', 'hcl', 'makefile',
    ];
    
    if (textExtensions.includes(ext) || file.name.toLowerCase() === 'dockerfile' || file.name.toLowerCase() === 'makefile') {
      try {
        const content = await file.text();
        projectFiles.push({
          name: file.name,
          path: file.webkitRelativePath || file.name,
          language: getLanguageFromExtension(ext),
          content: content.slice(0, 10000),
        });
      } catch {
      }
    }
  }
  
  const analysis = analyzeProjectFiles(projectFiles);
  
  return {
    id: generateId(),
    name,
    files: projectFiles,
    analysis,
    createdAt: new Date(),
    updatedAt: new Date(),
  };
}

export function analyzeProjectFiles(files: ProjectFile[]): ProjectAnalysis {
  const analysis: ProjectAnalysis = {
    language: 'unknown',
    framework: 'none',
    serviceType: 'unknown',
    databases: [],
    ports: [],
    hasDockerfile: false,
    hasKubernetes: false,
    hasTerraform: false,
    suggestions: [],
  };
  
  const fileNames = files.map((f) => f.name.toLowerCase());
  const filePaths = files.map((f) => f.path.toLowerCase());
  const allContent = files.map((f) => f.content || '').join('\n').toLowerCase();
  
  if (fileNames.includes('requirements.txt') || fileNames.includes('setup.py') || fileNames.includes('pyproject.toml')) {
    analysis.language = 'python';
  } else if (fileNames.includes('package.json')) {
    const pkgFile = files.find((f) => f.name === 'package.json');
    if (pkgFile?.content?.includes('typescript')) {
      analysis.language = 'typescript';
    } else {
      analysis.language = 'javascript';
    }
  } else if (fileNames.includes('go.mod')) {
    analysis.language = 'go';
  } else if (fileNames.includes('cargo.toml')) {
    analysis.language = 'rust';
  } else if (fileNames.includes('pom.xml') || fileNames.includes('build.gradle')) {
    analysis.language = 'java';
  } else if (fileNames.includes('gemfile')) {
    analysis.language = 'ruby';
  }
  
  if (analysis.language === 'python') {
    if (allContent.includes('django')) analysis.framework = 'django';
    else if (allContent.includes('fastapi')) analysis.framework = 'fastapi';
    else if (allContent.includes('flask')) analysis.framework = 'flask';
  } else if (analysis.language === 'javascript' || analysis.language === 'typescript') {
    if (allContent.includes('"next"') || allContent.includes('next.config')) analysis.framework = 'next';
    else if (allContent.includes('"react"')) analysis.framework = 'react';
    else if (allContent.includes('"express"')) analysis.framework = 'express';
    else if (allContent.includes('"nestjs"') || allContent.includes('@nestjs')) analysis.framework = 'nestjs';
  } else if (analysis.language === 'go') {
    if (allContent.includes('gin-gonic')) analysis.framework = 'gin';
    else if (allContent.includes('echo')) analysis.framework = 'echo';
  }
  
  if (analysis.framework === 'next' || analysis.framework === 'react') {
    analysis.serviceType = 'web';
  } else if (analysis.framework === 'express' || analysis.framework === 'fastapi' || analysis.framework === 'flask' || analysis.framework === 'django') {
    analysis.serviceType = 'api';
  } else if (allContent.includes('celery') || allContent.includes('worker')) {
    analysis.serviceType = 'worker';
  }
  
  if (allContent.includes('postgres') || allContent.includes('postgresql') || allContent.includes('psycopg')) {
    analysis.databases.push('postgresql');
  }
  if (allContent.includes('mysql')) {
    analysis.databases.push('mysql');
  }
  if (allContent.includes('mongodb') || allContent.includes('mongo')) {
    analysis.databases.push('mongodb');
  }
  if (allContent.includes('redis')) {
    analysis.databases.push('redis');
  }
  
  const portMatches = allContent.match(/port[=:]\s*(\d{4})/gi);
  if (portMatches) {
    portMatches.forEach((match) => {
      const port = parseInt(match.replace(/[^0-9]/g, ''));
      if (port >= 1024 && port <= 65535 && !analysis.ports.includes(port)) {
        analysis.ports.push(port);
      }
    });
  }
  
  analysis.hasDockerfile = fileNames.some((f) => f === 'dockerfile' || f.includes('dockerfile'));
  analysis.hasKubernetes = filePaths.some((p) => p.includes('k8s') || p.includes('kubernetes') || p.includes('deployment.yaml'));
  analysis.hasTerraform = fileNames.some((f) => f.endsWith('.tf'));
  
  if (!analysis.hasDockerfile) {
    analysis.suggestions.push(`یک Dockerfile برای پروژه ${analysis.language} بسازید`);
  }
  if (!analysis.hasKubernetes) {
    analysis.suggestions.push('مانیفست‌های Kubernetes برای استقرار ایجاد کنید');
  }
  if (!analysis.hasTerraform && analysis.databases.length > 0) {
    analysis.suggestions.push('تنظیمات Terraform برای زیرساخت دیتابیس بنویسید');
  }
  
  return analysis;
}

function getLanguageFromExtension(ext: string): string {
  const langMap: Record<string, string> = {
    js: 'javascript',
    jsx: 'javascript',
    ts: 'typescript',
    tsx: 'typescript',
    py: 'python',
    go: 'go',
    rs: 'rust',
    java: 'java',
    rb: 'ruby',
    php: 'php',
    html: 'html',
    css: 'css',
    scss: 'scss',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    tf: 'terraform',
    hcl: 'hcl',
    sql: 'sql',
    md: 'markdown',
    sh: 'shell',
    bash: 'shell',
  };
  return langMap[ext] || ext;
}
