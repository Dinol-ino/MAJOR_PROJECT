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

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('dfrag_theme') || 'dark');
  const [sessionId, setSessionId] = useState(() => 'WKD' + Math.random().toString(36).substring(2, 6).toUpperCase());
  const [messages, setMessages] = useState([]);
  const [shieldOn, setShieldOn] = useState(true);
  const [selectedModel, setSelectedModel] = useState('qwen2.5:3b');
  const [recommendedModels, setRecommendedModels] = useState([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [hardwareDrawerOpen, setHardwareDrawerOpen] = useState(false);
  const [activeView, setActiveView] = useState('chat'); // chat | graph | statutes | audit | hardware | mcp | settings
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(!!getAuthToken());
  const [authChecked, setAuthChecked] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeVaultId, setActiveVaultId] = useState(null);
  const [graphInitialQuery, setGraphInitialQuery] = useState(null);

  // Sync theme with HTML data-theme attribute
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('dfrag_theme', theme);
  }, [theme]);

  // On mount: verify stored token, listen for 401 events
  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      apiClient.me()
        .then((userData) => {
          setUser(userData);
          setIsAuthenticated(true);
        })
        .catch(() => {
          // Token is invalid or expired — clear it
          setAuthToken(null);
          setIsAuthenticated(false);
          setUser(null);
        })
        .finally(() => setAuthChecked(true));
    } else {
      // No stored token — check if first-run (no accounts exist)
      apiClient.getHealth()
        .then(() => {
          // Backend is reachable. Try calling /auth/me without token.
          // If no accounts exist, backend returns default user.
          return apiClient.me();
        })
        .then((userData) => {
          // First-run mode: backend returned default user without token
          setUser(userData);
          setIsAuthenticated(true);
        })
        .catch(() => {
          // Backend requires login
          setIsAuthenticated(false);
          setUser(null);
        })
        .finally(() => setAuthChecked(true));
    }

    // Listen for 401 events from authFetch
    const handleUnauthorized = () => {
      setAuthToken(null);
      setIsAuthenticated(false);
      setUser(null);
    };
    window.addEventListener('dfrag:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('dfrag:unauthorized', handleUnauthorized);
  }, []);

  // Handle successful login/register
  const handleLoginSuccess = useCallback((userData) => {
    setUser(userData);
    setIsAuthenticated(true);
  }, []);

  // Handle logout
  const handleLogout = useCallback(() => {
    setAuthToken(null);
    setIsAuthenticated(false);
    setUser(null);
  }, []);

  useEffect(() => {
    localStorage.setItem('dfrag_theme', theme);
    if (theme === 'light') {
      document.body.classList.add('light-theme');
    } else {
      document.body.classList.remove('light-theme');
    }
  }, [theme]);

  useEffect(() => {
    if (!isAuthenticated) return;
    // Initial fetch of hardware-recommended local models
    apiClient.getRecommendedModels().then((data) => {
      if (data && data.recommended && data.recommended.length > 0) {
        setRecommendedModels(data.recommended);
        // Default to installed model, or safe legal model that fits memory, or tier default
        const installed = data.recommended.find(m => m.installed);
        const preferred = data.recommended.find(m => (m.model_id === 'dfrag-legal:7b' || m.model_id === 'qwen2.5:7b') && m.fits_memory && m.safety_tier !== 'UNSUPPORTED');
        const fallback = data.recommended.find(m => m.recommended_for_tier && m.fits_memory) || data.recommended[0];
        const selected = installed || preferred || fallback;
        if (selected) {
          setSelectedModel(selected.model_id);
        }
      }
    }).catch((err) => {
      console.warn("Initial models fetch fallback:", err);
    });
  }, [isAuthenticated]);



  // Handle New Task Session
  const handleNewTask = () => {
    const newId = 'WKD' + Math.random().toString(36).substring(2, 6).toUpperCase();
    setSessionId(newId);
    setMessages([]);
    setActiveView('chat');
  };


  // Select existing session from sidebar task list & rehydrate persistent history
  const handleSelectSession = async (sid) => {
    setSessionId(sid);
    setActiveView('chat');
    try {
      const conv = await apiClient.getConversation(sid);
      if (conv && conv.messages && conv.messages.length > 0) {
        setMessages(conv.messages.map(m => ({
          role: m.role,
          content: m.content,
          sources: m.citations || [],
          blocked_by: m.blocked_by || null,
          confidence_score: m.confidence_score || null,
        })));
        if (conv.project_vault_id) {
          setActiveVaultId(conv.project_vault_id);
        }
        return;
      }
    } catch (e) {
      console.debug("Loading conversation fallback:", e);
    }
    setMessages([]);
  };

  // Clear current thread
  const handleClearThread = () => {
    setMessages([]);
  };

  // Send message in Legal Copilot
  const handleSendMessage = async (inputMessage, reasoningEffort = 'off') => {
    if (!inputMessage || !inputMessage.trim()) return;
    const userMsg = { role: 'user', content: inputMessage };
    setMessages((prev) => [...prev, userMsg]);
    setIsGenerating(true);

    try {
      const response = await apiClient.chat(inputMessage, sessionId, shieldOn, selectedModel, activeVaultId, reasoningEffort);
      const assistantMsg = {
        role: 'assistant',
        content: response.answer,
        sources: response.sources || [],
        blocked_by: response.blocked_by || null,
        block_reason: response.block_reason || null,
        failure_kind: response.failure_kind || null,
        correlation_id: response.correlation_id || sessionId,
        confidence_score: response.confidence_score || null,
        grounding_score: response.grounding_score,
        reasoning_trace: response.reasoning_trace,
        citations_parsed: response.citations_parsed,
        model_used: response.model_used,
        runtime_used: response.runtime_used,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error("Chat invocation error:", err);
      const isNetwork = err.message?.toLowerCase().includes('fetch') || err.message?.toLowerCase().includes('network') || err.message?.toLowerCase().includes('failed');
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: isNetwork
            ? 'The backend inference engine or Ollama daemon is temporarily unavailable. Please verify the local AI model service is active.'
            : `An unexpected processing error occurred: ${err.message}`,
          failure_kind: 'model_unavailable',
          blocked_by: null,
          block_reason: err.message,
          correlation_id: sessionId,
        },
      ]);
    } finally {
      setIsGenerating(false);
    }
  };

  // Switch to Copilot and research a given query (from Graph or Statute Library)
  const handleAskCopilotFromView = (queryPrompt) => {
    setActiveView('chat');
    handleSendMessage(queryPrompt);
  };

  const handleModelSelect = React.useCallback((m) => {
    setSelectedModel(m);
  }, []);

  if (!authChecked) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100vw', height: '100vh', background: 'var(--bg-app)', color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: 36, height: 36, border: '3px solid var(--border-subtle)', borderTopColor: 'var(--accent-primary)', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 14px' }} />
          <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)', fontWeight: 600 }}>DFrag Legal Workspace</div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>Verifying secure session...</div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <>
        <div className="editorial-paper-noise" />
        <div className="editorial-grid-overlay">
          <div className="editorial-grid-line" />
          <div className="editorial-grid-line" />
          <div className="editorial-grid-line" />
          <div className="editorial-grid-line" />
        </div>
        <LoginView onLoginSuccess={handleLoginSuccess} theme={theme} setTheme={setTheme} />
      </>
    );
  }

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden', background: 'var(--bg-app)', color: 'var(--text-primary)', position: 'relative' }}>
      {/* Paper grain and architectural grid */}
      <div className="editorial-paper-noise" />
      <div className="editorial-grid-overlay">
        <div className="editorial-grid-line" />
        <div className="editorial-grid-line" />
        <div className="editorial-grid-line" />
        <div className="editorial-grid-line" />
      </div>

      {/* Consensus Left Sidebar Navigation */}
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
        shieldOn={shieldOn}
        activeVaultId={activeVaultId}
        onSelectVault={(vid) => setActiveVaultId(vid)}
      />

      {/* Main Consensus Workspace Container */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', position: 'relative', zIndex: 10 }}>
        {/* Top Consensus Navigation Header */}
        <ManusHeader
          selectedModel={selectedModel}
          setSelectedModel={setSelectedModel}
          recommendedModels={recommendedModels}
          shieldOn={shieldOn}
          setShieldOn={setShieldOn}
          onToggleHardwareDrawer={() => setHardwareDrawerOpen(!hardwareDrawerOpen)}
          activeView={activeView}
          onClearThread={handleClearThread}
          theme={theme}
          setTheme={setTheme}
        />

        {/* Dynamic View Canvas */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          {activeView === 'chat' && (
            <ChatWindow
              messages={messages}
              onSendMessage={handleSendMessage}
              sessionId={sessionId}
              onUploadSuccess={() => {}}
              isGenerating={isGenerating}
              onClearThread={handleClearThread}
              activeVaultId={activeVaultId}
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

          {activeView === 'audit' && (
            <AuditLedgerView sessionId={sessionId} />
          )}

          {activeView === 'hardware' && (
            <HardwareForm
              isFullView={true}
              selectedModel={selectedModel}
              setSelectedModel={setSelectedModel}
              setRecommendedModels={setRecommendedModels}
              onModelRecommended={handleModelSelect}
            />
          )}

          {(activeView === 'settings' || activeView === 'mcp') && (
            <SettingsView
              theme={theme}
              setTheme={setTheme}
              defaultModel={selectedModel}
              setDefaultModel={setSelectedModel}
            />
          )}
        </div>
      </div>

      {/* Slide-out Quick Hardware Drawer Panel */}
      {hardwareDrawerOpen && (
        <HardwareForm
          isOpen={true}
          onClose={() => setHardwareDrawerOpen(false)}
          selectedModel={selectedModel}
          setSelectedModel={setSelectedModel}
          setRecommendedModels={setRecommendedModels}
          onModelRecommended={handleModelSelect}
        />
      )}
    </div>
  );
}
