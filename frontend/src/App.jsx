import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import ManusHeader from './components/ManusHeader';
import ChatWindow from './components/ChatWindow';
import CitationGraphView from './components/CitationGraphView';
import StatuteLibraryView from './components/StatuteLibraryView';
import AuditLedgerView from './components/AuditLedgerView';
import HardwareForm from './components/HardwareForm';
import McpToolsView from './components/McpToolsView';
import SettingsView from './components/SettingsView';
import LoginView from './components/LoginView';
import { apiClient, getAuthToken, setAuthToken } from './api/client';

const newSessionId = () =>
  (window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `s-${Date.now()}-${Math.random().toString(36).slice(2)}`);

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('dfrag_theme') || 'dark');
  const [sessionId, setSessionId] = useState(newSessionId);
  const [messages, setMessages] = useState([]);
  const [activeView, setActiveView] = useState('chat');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [user, setUser] = useState(null);
  // Authenticated ONLY with a server-verified token. There is no token-less "first run" state.
  const [authState, setAuthState] = useState('checking'); // checking | authenticated | anonymous
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeVaultId, setActiveVaultId] = useState(null);
  // Bumped after an upload finishes so the sidebar re-reads the vault's documents and counts.
  const [docsVersion, setDocsVersion] = useState(0);
  const [graphInitialQuery, setGraphInitialQuery] = useState(null);
  const [models, setModels] = useState({ installed: [], active: null, runtimeOnline: false, loading: true });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.body.classList.toggle('light-theme', theme === 'light');
    localStorage.setItem('dfrag_theme', theme);
  }, [theme]);

  // Session bootstrap: verify the stored token; otherwise show sign-in / first-account registration.
  useEffect(() => {
    let active = true;
    const token = getAuthToken();
    if (!token) {
      setAuthState('anonymous');
    } else {
      apiClient.me()
        .then((u) => { if (active) { setUser(u); setAuthState('authenticated'); } })
        .catch(() => { if (active) { setAuthToken(null); setAuthState('anonymous'); } });
    }
    const onUnauthorized = () => {
      setAuthToken(null);
      setUser(null);
      setAuthState('anonymous');
    };
    window.addEventListener('dfrag:unauthorized', onUnauthorized);
    return () => { active = false; window.removeEventListener('dfrag:unauthorized', onUnauthorized); };
  }, []);

  const refreshModels = useCallback(async () => {
    try {
      const data = await apiClient.getInstalledModels();
      setModels({
        installed: data.models || [],
        active: data.active_model || null,
        runtimeOnline: !!data.runtime_online,
        loading: false,
      });
    } catch {
      setModels((m) => ({ ...m, runtimeOnline: false, loading: false }));
    }
  }, []);

  useEffect(() => {
    if (authState === 'authenticated') refreshModels();
  }, [authState, refreshModels]);

  const handleActivateModel = useCallback(async (name) => {
    await apiClient.activateModel(name);
    await refreshModels();
  }, [refreshModels]);

  const handleLoginSuccess = useCallback((u) => {
    setUser(u);
    setAuthState('authenticated');
  }, []);

  const handleLogout = useCallback(async () => {
    await apiClient.logout();
    setAuthToken(null);
    setUser(null);
    setMessages([]);
    setAuthState('anonymous');
  }, []);

  const handleNewTask = () => {
    setSessionId(newSessionId());
    setMessages([]);
    setActiveView('chat');
  };

  // Reopen a persisted conversation (messages, citations and vault binding survive restarts).
  const handleSelectSession = async (sid) => {
    setSessionId(sid);
    setActiveView('chat');
    try {
      const conv = await apiClient.getConversation(sid);
      setMessages((conv.messages || []).map((m) => ({
        role: m.role,
        content: m.content,
        sources: m.citations || [],
        citations_parsed: m.citations_json || null,
        model_used: m.model_used || null,
        reasoning_trace: m.reasoning_trace || null,
      })));
      setActiveVaultId(conv.project_vault_id || null);
    } catch {
      setMessages([]);
    }
  };

  const handleClearThread = () => setMessages([]);

  const handleSendMessage = async (inputMessage, reasoningEffort = 'medium') => {
    if (!inputMessage || !inputMessage.trim()) return;
    setMessages((prev) => [...prev, { role: 'user', content: inputMessage }]);
    setIsGenerating(true);
    try {
      // No model is sent: the server answers with the ACTIVE model and reports which one it used.
      const response = await apiClient.chat(inputMessage, sessionId, true, null, activeVaultId, reasoningEffort);
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: response.answer,
        sources: response.sources || [],
        blocked_by: response.blocked_by || null,
        block_reason: response.block_reason || null,
        failure_kind: response.failure_kind || null,
        correlation_id: response.correlation_id || null,
        grounding_score: response.grounding_score,
        reasoning_trace: response.reasoning_trace,
        citations_parsed: response.citations_parsed,
        model_used: response.model_used,
        runtime_used: response.runtime_used,
        metrics: response.metrics || null,
      }]);
    } catch (err) {
      const modelProblem = err.code === 'no_active_model' || err.code === 'model_not_installed';
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: modelProblem
          ? `${err.message}`
          : err.status
            ? `The request could not be completed: ${err.message}`
            : 'The workspace service could not be reached. Check that the backend is running.',
        failure_kind: modelProblem ? 'model_unavailable' : 'request_failed',
        action: modelProblem ? { label: 'Open Hardware & Models', view: 'hardware' } : null,
      }]);
      if (modelProblem) refreshModels();
    } finally {
      setIsGenerating(false);
    }
  };

  const handleAskCopilotFromView = (queryPrompt) => {
    setActiveView('chat');
    handleSendMessage(queryPrompt);
  };

  if (authState === 'checking') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100vw', height: '100vh', background: 'var(--bg-app)', color: 'var(--text-muted)', fontFamily: 'var(--font-serif)' }}>
        Verifying session…
      </div>
    );
  }

  if (authState !== 'authenticated') {
    return <LoginView onLoginSuccess={handleLoginSuccess} theme={theme} setTheme={setTheme} />;
  }

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden', background: 'var(--bg-app)', color: 'var(--text-primary)' }}>
      <Sidebar
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewTask={handleNewTask}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        user={user}
        onLogout={handleLogout}
        activeView={activeView}
        setActiveView={setActiveView}
        shieldOn
        activeVaultId={activeVaultId}
        docsVersion={docsVersion}
        onSelectVault={(vid) => setActiveVaultId(vid)}
      />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        <ManusHeader
          activeView={activeView}
          onClearThread={handleClearThread}
          models={models}
          onActivateModel={handleActivateModel}
          onOpenModels={() => setActiveView('hardware')}
        />

        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          {activeView === 'chat' && (
            <ChatWindow
              messages={messages}
              onSendMessage={handleSendMessage}
              sessionId={sessionId}
              onUploadSuccess={() => setDocsVersion((v) => v + 1)}
              isGenerating={isGenerating}
              onClearThread={handleClearThread}
              activeVaultId={activeVaultId}
              activeModel={models.active}
              onNavigate={setActiveView}
            />
          )}

          {activeView === 'graph' && (
            <CitationGraphView
              onAskCopilot={handleAskCopilotFromView}
              sessionId={sessionId}
              activeVaultId={activeVaultId}
              initialQuery={graphInitialQuery}
            />
          )}

          {activeView === 'statutes' && (
            <StatuteLibraryView
              onAskCopilot={handleAskCopilotFromView}
              onViewInGraph={(statuteSlug) => {
                setGraphInitialQuery(statuteSlug);
                setActiveView('graph');
              }}
            />
          )}

          {activeView === 'security' && <AuditLedgerView sessionId={sessionId} user={user} />}

          {activeView === 'hardware' && (
            <HardwareForm
              isFullView
              activeModel={models.active}
              onModelsChanged={refreshModels}
              onActivateModel={handleActivateModel}
            />
          )}

          {activeView === 'sources' && <McpToolsView />}

          {activeView === 'settings' && <SettingsView theme={theme} setTheme={setTheme} />}
        </div>
      </div>
    </div>
  );
}
