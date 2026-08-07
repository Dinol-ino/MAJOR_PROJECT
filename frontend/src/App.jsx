import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ManusHeader from './components/ManusHeader';
import ChatWindow from './components/ChatWindow';
import HardwareForm from './components/HardwareForm';
import { apiClient } from './api/client';

export default function App() {
  const [sessionId, setSessionId] = useState(() => 'WKD' + Math.random().toString(36).substring(2, 6).toUpperCase());
  const [messages, setMessages] = useState([]);
  const [shieldOn, setShieldOn] = useState(true);
  const [selectedModel, setSelectedModel] = useState('qwen2.5:3b');
  const [recommendedModels, setRecommendedModels] = useState([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [hardwareDrawerOpen, setHardwareDrawerOpen] = useState(false);
  const [user, setUser] = useState({ username: 'Dinol Castelino', email: 'dinol@dfrag.ai' });

  // Handle New Task
  const handleNewTask = () => {
    const newId = 'WKD' + Math.random().toString(36).substring(2, 6).toUpperCase();
    setSessionId(newId);
    setMessages([]);
  };

  // Select existing session from sidebar task list
  const handleSelectSession = (sid) => {
    setSessionId(sid);
    // In production, fetch session messages from API
    setMessages([]);
  };

  // Send message
  const handleSendMessage = async (inputMessage) => {
    const userMsg = { role: 'user', content: inputMessage };
    setMessages((prev) => [...prev, userMsg]);

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
          content: 'Error: Failed to fetch response from backend server.',
          blocked_by: 'system',
          block_reason: err.message,
        },
      ]);
    }
  };

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden', background: '#121214', color: '#f8fafc' }}>
      {/* Manus Left Sidebar Navigation */}
      <Sidebar
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewTask={handleNewTask}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        user={user}
        onLogout={() => setUser(null)}
      />

      {/* Main Manus Workspace Container */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        {/* Top Manus Navigation Header */}
        <ManusHeader
          selectedModel={selectedModel}
          setSelectedModel={setSelectedModel}
          recommendedModels={recommendedModels}
          shieldOn={shieldOn}
          setShieldOn={setShieldOn}
          onToggleHardwareDrawer={() => setHardwareDrawerOpen(!hardwareDrawerOpen)}
        />

        {/* Main Canvas & Chat Window */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <ChatWindow
            messages={messages}
            onSendMessage={handleSendMessage}
            sessionId={sessionId}
            onUploadSuccess={() => {}}
          />
        </div>
      </div>

      {/* Slide-out Hardware Drawer Panel */}
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
