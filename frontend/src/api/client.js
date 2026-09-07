const BASE_URL = '/api';

export const apiClient = {
  /**
   * POST /chat
   */
  async chat(message, sessionId, shieldOn, model, vaultId = null, reasoningEffort = 'off') {
    const response = await fetch(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        shield_on: shieldOn,
        model: model || undefined,
        vault_id: vaultId || undefined,
        reasoning_effort: reasoningEffort || 'off',
      }),
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      const errorMsg = errData.detail || errData.message || `Chat request failed with status: ${response.status}`;
      throw new Error(errorMsg);
    }
    return response.json();
  },

  /**
   * GET /messages/{messageId}/grounding
   */
  async getMessageGrounding(messageId) {
    const response = await fetch(`${BASE_URL}/messages/${messageId}/grounding`);
    if (!response.ok) {
      throw new Error(`Failed to fetch grounding breakdown for message: ${messageId}`);
    }
    return response.json();
  },

  /**
   * GET /chat/sessions
   */
  async getSessions() {
    const response = await fetch(`${BASE_URL}/chat/sessions`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Get sessions failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * DELETE /chat/sessions/{session_id}
   */
  async deleteSession(sessionId) {
    const response = await fetch(`${BASE_URL}/chat/sessions/${sessionId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`Delete session failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /upload
   */
  async upload(file, sessionId) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId);

    const response = await fetch(`${BASE_URL}/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`Upload request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /upload/batch
   */
  async uploadBatch(files, sessionId) {
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }
    formData.append('session_id', sessionId);

    const response = await fetch(`${BASE_URL}/upload/batch`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`Batch upload request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /recommend
   */
  async recommend(ramGb = null, vramGb = null) {
    const bodyPayload = {};
    if (ramGb !== null && ramGb !== undefined) bodyPayload.ram_gb = parseInt(ramGb);
    if (vramGb !== null && vramGb !== undefined) bodyPayload.vram_gb = parseInt(vramGb);

    const response = await fetch(`${BASE_URL}/recommend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyPayload),
    });
    if (!response.ok) {
      throw new Error(`Recommendation request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /health
   */
  async getHealth() {
    const response = await fetch(`${BASE_URL}/health`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Health request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /models/pull
   */
  async pullModel(modelId) {
    const response = await fetch(`${BASE_URL}/models/pull`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId }),
    });
    if (!response.ok) {
      throw new Error(`Model pull request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /models/pull/progress/{task_id}
   */
  async getPullProgress(taskId) {
    const response = await fetch(`${BASE_URL}/models/pull/progress/${taskId}`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Progress request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /audit/{session_id}
   */
  async getAuditLogs(sessionId) {
    const response = await fetch(`${BASE_URL}/audit/${sessionId}`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Audit log request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /mcp/status
   */
  async getMcpStatus() {
    const response = await fetch(`${BASE_URL}/mcp/status`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`MCP status request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /statutes/catalog
   */
  async getStatutesCatalog(domain = null, q = null, page = 1, limit = 50) {
    const params = new URLSearchParams();
    if (domain && domain !== 'All') params.append('domain', domain);
    if (q) params.append('q', q);
    params.append('page', page);
    params.append('limit', limit);
    const response = await fetch(`${BASE_URL}/statutes/catalog?${params.toString()}`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Statutes catalog request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /statutes/{slug}
   */
  async getStatute(slug) {
    const response = await fetch(`${BASE_URL}/statutes/${encodeURIComponent(slug)}`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Statute request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /statutes/{slug}/sections/{number}
   */
  async getStatuteSection(slug, number) {
    const response = await fetch(`${BASE_URL}/statutes/${encodeURIComponent(slug)}/sections/${encodeURIComponent(number)}`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Statute section request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /statutes/sync
   */
  async syncStatutes() {
    const response = await fetch(`${BASE_URL}/statutes/sync`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(`Statutes sync failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /statutes/{act_id}/tree
   */
  async getStatuteTree(actId) {
    const response = await fetch(`${BASE_URL}/statutes/${actId}/tree`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Statute tree request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /statutes/graph
   */
  async getStatuteGraph(scope = 'conversation', conversationId = null, vaultId = null, q = null) {
    const params = new URLSearchParams();
    params.append('scope', scope);
    if (conversationId) params.append('conversation_id', conversationId);
    if (vaultId) params.append('vault_id', vaultId);
    if (q) params.append('q', q);
    const response = await fetch(`${BASE_URL}/statutes/graph?${params.toString()}`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Statute graph request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /statutes/graph/expand
   */
  async expandGraphNode(nodeId, depth = 1) {
    const response = await fetch(`${BASE_URL}/statutes/graph/expand`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: nodeId, depth }),
    });
    if (!response.ok) {
      throw new Error(`Expand graph node failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /mcp/servers/{server_name}/reconnect
   */
  async reconnectMcpServer(serverName) {
    const response = await fetch(`${BASE_URL}/mcp/servers/${encodeURIComponent(serverName)}/reconnect`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(`Reconnect MCP server failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /mcp/discover
   */
  async discoverMcpTools() {
    const response = await fetch(`${BASE_URL}/mcp/discover`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(`Discover MCP tools failed: ${response.status}`);
    }
    return response.json();
  },

  // --- Project Vaults (Spec 01) ---
  /**
   * GET /vaults
   */
  async getVaults(userId = 'default_user') {
    const response = await fetch(`${BASE_URL}/vaults?user_id=${encodeURIComponent(userId)}`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Get vaults failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /vaults
   */
  async createVault(vaultName, description, userId = 'default_user') {
    const response = await fetch(`${BASE_URL}/vaults`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        vault_name: vaultName,
        description,
        user_id: userId,
      }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Create vault failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /vaults/{vault_id}
   */
  async getVault(vaultId) {
    const response = await fetch(`${BASE_URL}/vaults/${vaultId}`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Get vault failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * PATCH /vaults/{vault_id}
   */
  async updateVault(vaultId, data) {
    const response = await fetch(`${BASE_URL}/vaults/${vaultId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      throw new Error(`Update vault failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * DELETE /vaults/{vault_id}
   */
  async deleteVault(vaultId) {
    const response = await fetch(`${BASE_URL}/vaults/${vaultId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`Delete vault failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /vaults/{vault_id}/documents
   */
  async uploadVaultDocument(vaultId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${BASE_URL}/vaults/${vaultId}/documents`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Vault document upload failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /vaults/{vault_id}/documents
   */
  async getVaultDocuments(vaultId) {
    const response = await fetch(`${BASE_URL}/vaults/${vaultId}/documents`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Get vault documents failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /vaults/{vault_id}/documents/{doc_id}/status
   */
  async getVaultDocumentStatus(vaultId, docId) {
    const response = await fetch(`${BASE_URL}/vaults/${vaultId}/documents/${docId}/status`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Get document status failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * DELETE /vaults/{vault_id}/documents/{doc_id}
   */
  async deleteVaultDocument(vaultId, docId) {
    const response = await fetch(`${BASE_URL}/vaults/${vaultId}/documents/${docId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`Delete vault document failed: ${response.status}`);
    }
    return response.json();
  },

  // --- Conversations Management & Rename (Spec 01 §3.3) ---
  /**
   * GET /conversations
   */
  async getConversations(vaultId = null) {
    const url = vaultId ? `${BASE_URL}/conversations?vault_id=${encodeURIComponent(vaultId)}` : `${BASE_URL}/conversations`;
    const response = await fetch(url, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Get conversations failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /conversations
   */
  async createConversation(vaultId = null, title = 'New Legal Chat') {
    const response = await fetch(`${BASE_URL}/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_vault_id: vaultId || undefined,
        title,
      }),
    });
    if (!response.ok) {
      throw new Error(`Create conversation failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /conversations/{id}
   */
  async getConversation(conversationId) {
    const response = await fetch(`${BASE_URL}/conversations/${conversationId}`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Get conversation failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * PATCH /conversations/{id} (Rename Chat)
   */
  async renameConversation(conversationId, title) {
    const response = await fetch(`${BASE_URL}/conversations/${conversationId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    });
    if (!response.ok) {
      throw new Error(`Rename conversation failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * DELETE /conversations/{id}
   */
  async deleteConversation(conversationId) {
    const response = await fetch(`${BASE_URL}/conversations/${conversationId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`Delete conversation failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /settings/fallback
   */
  async getFallbackSettings() {
    const response = await fetch(`${BASE_URL}/settings/fallback`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Get fallback settings failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /settings/fallback
   */
  async updateFallbackSettings(payload) {
    const response = await fetch(`${BASE_URL}/settings/fallback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(`Update fallback settings failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /settings/fallback/test
   */
  async testFallbackKey(provider, key = null) {
    const response = await fetch(`${BASE_URL}/settings/fallback/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, key }),
    });
    return response.json();
  },

  /**
   * GET /telemetry/sample
   */
  async getTelemetrySample() {
    const response = await fetch(`${BASE_URL}/telemetry/sample`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Telemetry sample failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /models/recommended
   */
  async getRecommendedModels() {
    const response = await fetch(`${BASE_URL}/models/recommended`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Get recommended models failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /models/pull with SSE streaming progress reader
   */
  pullModelStream(modelName, onProgress, onComplete, onError) {
    const controller = new AbortController();

    fetch(`${BASE_URL}/models/pull?stream=true`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: modelName }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Pull request failed: ${response.status}`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const block of lines) {
            const trimmed = block.trim();
            if (trimmed.startsWith('data:')) {
              try {
                const parsed = JSON.parse(trimmed.replace(/^data:\s*/, ''));
                if (onProgress) onProgress(parsed);
                if (parsed.status === 'success' || parsed.percent >= 100) {
                  if (onComplete) onComplete(parsed);
                  return;
                }
                if (parsed.status === 'error') {
                  if (onError) onError(new Error(parsed.error || 'Pull failed'));
                  return;
                }
              } catch (e) {
                // Ignore parse errors for partial chunks
              }
            }
          }
        }
        if (onComplete) onComplete({ status: 'success', percent: 100 });
      })
      .catch((err) => {
        if (err.name === 'AbortError') {
          if (onError) onError(new Error('Pull cancelled by user'));
        } else {
          if (onError) onError(err);
        }
      });

    return controller;
  },
};

