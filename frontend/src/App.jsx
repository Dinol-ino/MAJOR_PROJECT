import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ManusHeader from './components/ManusHeader';
import ChatWindow from './components/ChatWindow';
import CitationGraphView from './components/CitationGraphView';
import StatuteLibraryView from './components/StatuteLibraryView';
import AuditLedgerView from './components/AuditLedgerView';
import HardwareForm from './components/HardwareForm';
import McpToolsView from './components/McpToolsView';
import SettingsView from './components/SettingsView';
import { apiClient } from './api/client';

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
  const [user, setUser] = useState({ username: 'Dinol Castelino', email: 'dinol@dfrag.ai' });
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeVaultId, setActiveVaultId] = useState(null);

  useEffect(() => {
    localStorage.setItem('dfrag_theme', theme);
    if (theme === 'light') {
      document.body.classList.add('light-theme');
    } else {
      document.body.classList.remove('light-theme');
    }
  }, [theme]);

  useEffect(() => {
    // Initial fetch of hardware-recommended local models
    apiClient.recommend().then((data) => {
      if (data && data.recommended && data.recommended.length > 0) {
        setRecommendedModels(data.recommended);
        // Default to specialized legal model or highest accuracy model if available
        const preferred = data.recommended.find(m => m.model_id === 'dfrag-legal:7b' || m.model_id === 'qwen2.5:7b');
        if (preferred) {
          setSelectedModel(preferred.model_id);
        } else {
          setSelectedModel(data.recommended[0].model_id);
        }
      }
    }).catch((err) => {
      console.warn("Initial models fetch fallback:", err);
    });
  }, []);

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
        confidence_score: response.confidence_score || null,
        grounding_score: response.grounding_score,
        reasoning_trace: response.reasoning_trace,
        citations_parsed: response.citations_parsed,
        model_used: response.model_used,
        runtime_used: response.runtime_used,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Error: Failed to fetch response from backend inference engine.',
          blocked_by: 'system',
          block_reason: err.message,
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

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden', background: 'var(--bg-app)', color: 'var(--text-primary)' }}>
      {/* Consensus Left Sidebar Navigation */}
      <Sidebar
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewTask={handleNewTask}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        user={user}
        activeView={activeView}
        setActiveView={setActiveView}
        shieldOn={shieldOn}
        activeVaultId={activeVaultId}
        onSelectVault={(vid) => setActiveVaultId(vid)}
      />

      {/* Main Consensus Workspace Container */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
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
            />
          )}

          {activeView === 'statutes' && (
            <StatuteLibraryView
              onAskCopilot={handleAskCopilotFromView}
              onViewInGraph={(statuteSlug) => {
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

          {activeView === 'mcp' && (
            <McpToolsView />
          )}

          {activeView === 'settings' && (
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
