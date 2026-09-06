import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ManusHeader from './components/ManusHeader';
import ChatWindow from './components/ChatWindow';
import CitationGraphView from './components/CitationGraphView';
import StatuteLibraryView from './components/StatuteLibraryView';
import AuditLedgerView from './components/AuditLedgerView';
import HardwareForm from './components/HardwareForm';
import McpToolsView from './components/McpToolsView';
import { apiClient } from './api/client';

export default function App() {
  const [sessionId, setSessionId] = useState(() => 'WKD' + Math.random().toString(36).substring(2, 6).toUpperCase());
  const [messages, setMessages] = useState([]);
  const [shieldOn, setShieldOn] = useState(true);
  const [selectedModel, setSelectedModel] = useState('gemma2:2b');
  const [recommendedModels, setRecommendedModels] = useState([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [hardwareDrawerOpen, setHardwareDrawerOpen] = useState(false);
  const [activeView, setActiveView] = useState('chat'); // chat | graph | statutes | audit | hardware | mcp
  const [user, setUser] = useState({ username: 'Dinol Castelino', email: 'dinol@dfrag.ai' });
  const [isGenerating, setIsGenerating] = useState(false);

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


  // Select existing session from sidebar task list
  const handleSelectSession = (sid) => {
    setSessionId(sid);
    setMessages([]);
    setActiveView('chat');
  };

  // Clear current thread
  const handleClearThread = () => {
    setMessages([]);
  };

  // Send message in Legal Copilot
  const handleSendMessage = async (inputMessage) => {
    if (!inputMessage || !inputMessage.trim()) return;
    const userMsg = { role: 'user', content: inputMessage };
    setMessages((prev) => [...prev, userMsg]);
    setIsGenerating(true);

    try {
      const response = await apiClient.chat(inputMessage, sessionId, shieldOn, selectedModel);
      const assistantMsg = {
        role: 'assistant',
        content: response.answer,
        sources: response.sources || [],
        blocked_by: response.blocked_by || null,
        block_reason: response.block_reason || null,
        confidence_score: response.confidence_score || null,
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
        onLogout={() => setUser(null)}
        activeView={activeView}
        setActiveView={setActiveView}
        shieldOn={shieldOn}
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
            />
          )}

          {activeView === 'graph' && (
            <CitationGraphView onAskCopilot={handleAskCopilotFromView} />
          )}

          {activeView === 'statutes' && (
            <StatuteLibraryView onAskCopilot={handleAskCopilotFromView} />
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
              onModelRecommended={(m) => setSelectedModel(m)}
            />
          )}

          {activeView === 'mcp' && (
            <McpToolsView />
          )}
        </div>
      </div>

      {/* Slide-out Quick Hardware Drawer Panel */}
      <HardwareForm
        isOpen={hardwareDrawerOpen}
        onClose={() => setHardwareDrawerOpen(false)}
        selectedModel={selectedModel}
        setSelectedModel={setSelectedModel}
        setRecommendedModels={setRecommendedModels}
        onModelRecommended={(m) => setSelectedModel(m)}
      />
    </div>
  );
}
