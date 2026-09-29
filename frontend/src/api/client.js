export const BASE_URL = '/api';

const TOKEN_KEY = 'dfrag_auth_token';

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

/**
 * Central fetch wrapper: injects the Bearer session token and, on 401,
 * broadcasts a 'dfrag:unauthorized' event so the app can show the login screen.
 */
export async function authFetch(url, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const token = getAuthToken();
  if (token && !url.includes('/auth/login') && !url.includes('/auth/register')) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(url, { ...opts, headers });
  if (response.status === 401 && !url.includes('/auth/')) {
    window.dispatchEvent(new Event('dfrag:unauthorized'));
  }
  return response;
}

/** Builds an Error from a FastAPI error body; keeps a machine-readable `code` when the server sends one. */
async function errorFrom(response, fallback) {
  const body = await response.json().catch(() => ({}));
  const detail = body.detail;
  const message = (detail && typeof detail === 'object' ? detail.message : detail) || body.message || fallback;
  const err = new Error(message);
  err.status = response.status;
  err.code = detail && typeof detail === 'object' ? detail.code : undefined;
  return err;
}

/**
 * Reads a text/event-stream over fetch (so the Authorization header is sent — EventSource cannot).
 * Returns an AbortController. Calls onEvent(parsedJson) per `data:` block.
 */
export function openAuthedStream(url, { onEvent, onOpen, onError, onClose }) {
  const controller = new AbortController();
  const headers = { Accept: 'text/event-stream' };
  const token = getAuthToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  fetch(url, { headers, signal: controller.signal })
    .then(async (response) => {
      if (!response.ok) {
        if (response.status === 401) window.dispatchEvent(new Event('dfrag:unauthorized'));
        throw Object.assign(new Error(`Stream failed: ${response.status}`), { status: response.status });
      }
      if (onOpen) onOpen();
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split('\n\n');
        buffer = blocks.pop() || '';
        for (const block of blocks) {
          const line = block.trim();
          if (!line.startsWith('data:')) continue;
          try { onEvent(JSON.parse(line.replace(/^data:\s*/, ''))); } catch { /* partial or non-JSON block */ }
        }
      }
      if (onClose) onClose();
    })
    .catch((err) => {
      if (err.name === 'AbortError') return;
      if (onError) onError(err);
    });
  return controller;
}

export const apiClient = {
  /** Base prefix for all API calls (Vite dev proxy strips it; prod serves same-origin). */
  BASE_URL,
  /**
   * POST /auth/login
   */
  async login(username, password) {
    const response = await authFetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Login failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /auth/register
   */
  async register(username, email, password, fullName) {
    const response = await authFetch(`${BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password, full_name: fullName || undefined }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Registration failed with status: ${response.status}`);
    }
    return response.json();
  },

  /** GET /auth/status (public): whether to show sign-in or first-account registration. */
  async authStatus() {
    const response = await fetch(`${BASE_URL}/auth/status`);
    if (!response.ok) throw await errorFrom(response, `Auth status failed (${response.status})`);
    return response.json();
  },

  /** POST /auth/logout: revokes the current session token server-side. */
  async logout() {
    try {
      await authFetch(`${BASE_URL}/auth/logout`, { method: 'POST' });
    } catch { /* logging out locally regardless */ }
  },

  /**
   * GET /auth/me
   */
  async me() {
    const response = await authFetch(`${BASE_URL}/auth/me`);
    if (!response.ok) {
      throw new Error(`Not authenticated (status ${response.status})`);
    }
    return response.json();
  },

  /**
   * POST /chat
   */
  async chat(message, sessionId, shieldOn, model, vaultId = null, reasoningEffort = 'medium') {
    const response = await authFetch(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        shield_on: shieldOn,
        model: model || undefined,
        vault_id: vaultId || undefined,
        reasoning_effort: reasoningEffort || 'medium',
      }),
    });
    if (!response.ok) {
      throw await errorFrom(response, `Chat request failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /messages/{messageId}/grounding
   */
  async getMessageGrounding(messageId) {
    const response = await authFetch(`${BASE_URL}/messages/${messageId}/grounding`);
    if (!response.ok) {
      throw new Error(`Failed to fetch grounding breakdown for message: ${messageId}`);
    }
    return response.json();
  },

  /**
   * GET /chat/sessions
   */
  async getSessions() {
    const response = await authFetch(`${BASE_URL}/chat/sessions`, {
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
    const response = await authFetch(`${BASE_URL}/chat/sessions/${sessionId}`, {
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

    const response = await authFetch(`${BASE_URL}/upload`, {
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

    const response = await authFetch(`${BASE_URL}/upload/batch`, {
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

    const response = await authFetch(`${BASE_URL}/recommend`, {
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
    const response = await authFetch(`${BASE_URL}/health`, {
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
    const response = await authFetch(`${BASE_URL}/models/pull`, {
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
    const response = await authFetch(`${BASE_URL}/models/pull/progress/${taskId}`, {
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
    const response = await authFetch(`${BASE_URL}/audit/${sessionId}`, {
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
    const response = await authFetch(`${BASE_URL}/mcp/status`, {
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
    const response = await authFetch(`${BASE_URL}/statutes/catalog?${params.toString()}`, {
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
    const response = await authFetch(`${BASE_URL}/statutes/${encodeURIComponent(slug)}`, {
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
    const response = await authFetch(`${BASE_URL}/statutes/${encodeURIComponent(slug)}/sections/${encodeURIComponent(number)}`, {
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
    const response = await authFetch(`${BASE_URL}/statutes/sync`, {
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
    const response = await authFetch(`${BASE_URL}/statutes/${actId}/tree`, {
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
    const response = await authFetch(`${BASE_URL}/statutes/graph?${params.toString()}`, {
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
    const response = await authFetch(`${BASE_URL}/statutes/graph/expand`, {
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
    const response = await authFetch(`${BASE_URL}/mcp/servers/${encodeURIComponent(serverName)}/reconnect`, {
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
    const response = await authFetch(`${BASE_URL}/mcp/discover`, {
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
  async getVaults() {
    const url = `${BASE_URL}/vaults`;
    const response = await authFetch(url, {
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
  async createVault(vaultName, description) {
    const response = await authFetch(`${BASE_URL}/vaults`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vault_name: vaultName, description }),
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
    const response = await authFetch(`${BASE_URL}/vaults/${vaultId}`, {
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
    const response = await authFetch(`${BASE_URL}/vaults/${vaultId}`, {
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
    const response = await authFetch(`${BASE_URL}/vaults/${vaultId}`, {
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
    const response = await authFetch(`${BASE_URL}/vaults/${vaultId}/documents`, {
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
    const response = await authFetch(`${BASE_URL}/vaults/${vaultId}/documents`, {
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
    const response = await authFetch(`${BASE_URL}/vaults/${vaultId}/documents/${docId}/status`, {
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
    const response = await authFetch(`${BASE_URL}/vaults/${vaultId}/documents/${docId}`, {
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
    const response = await authFetch(url, {
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
    const response = await authFetch(`${BASE_URL}/conversations`, {
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
    const response = await authFetch(`${BASE_URL}/conversations/${conversationId}`, {
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
    const response = await authFetch(`${BASE_URL}/conversations/${conversationId}`, {
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
    const response = await authFetch(`${BASE_URL}/conversations/${conversationId}`, {
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
    const response = await authFetch(`${BASE_URL}/settings/fallback`, {
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
    const response = await authFetch(`${BASE_URL}/settings/fallback`, {
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
    const response = await authFetch(`${BASE_URL}/settings/fallback/test`, {
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
    const response = await authFetch(`${BASE_URL}/telemetry/sample`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Telemetry sample failed: ${response.status}`);
    }
    return response.json();
  },

  /** GET /models/installed: models actually present in the local runtime (top selector source). */
  async getInstalledModels() {
    const response = await authFetch(`${BASE_URL}/models/installed`);
    if (!response.ok) throw await errorFrom(response, `Installed models failed (${response.status})`);
    return response.json();
  },

  /** GET /models/active */
  async getActiveModel() {
    const response = await authFetch(`${BASE_URL}/models/active`);
    if (!response.ok) throw await errorFrom(response, `Active model failed (${response.status})`);
    return response.json();
  },

  /** POST /models/activate: verify, warm up, health-check and persist the answering model. */
  async activateModel(model) {
    const response = await authFetch(`${BASE_URL}/models/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model }),
    });
    if (!response.ok) throw await errorFrom(response, `Activation failed (${response.status})`);
    return response.json();
  },

  /** GET /research/mode: the server-side network mode (OFFLINE/ONLINE) and allowlisted sources. */
  async getNetworkMode() {
    const response = await authFetch(`${BASE_URL}/research/mode`);
    if (!response.ok) throw await errorFrom(response, `Network mode failed (${response.status})`);
    return response.json();
  },

  /** POST /research/mode: explicit, audited switch between OFFLINE and ONLINE. */
  async setNetworkMode(mode) {
    const response = await authFetch(`${BASE_URL}/research/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, reason: 'Changed from Settings' }),
    });
    if (!response.ok) throw await errorFrom(response, `Mode change failed (${response.status})`);
    return response.json();
  },

  /** GET /statutes/corpus-status */
  async getCorpusStatus() {
    const response = await authFetch(`${BASE_URL}/statutes/corpus-status`);
    if (!response.ok) throw await errorFrom(response, `Corpus status failed (${response.status})`);
    return response.json();
  },

  /** GET /audit/verify: live hash-chain verification of the security ledger. */
  async verifyAudit() {
    const response = await authFetch(`${BASE_URL}/audit/verify`);
    if (!response.ok) throw await errorFrom(response, `Audit verification failed (${response.status})`);
    return response.json();
  },

  /** Authenticated telemetry stream (replaces the header-less EventSource). */
  streamTelemetry(handlers) {
    return openAuthedStream(`${BASE_URL}/telemetry/stream`, handlers);
  },

  /**
   * GET /models/recommended
   */
  async getRecommendedModels() {
    const response = await authFetch(`${BASE_URL}/models/recommended`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new Error(`Get recommended models failed: ${response.status}`);
    }
    return response.json();
  },

  /**
   * POST /models/provision - Triggers idempotent one-click model provisioning.
   * Single /api prefix: Vite dev proxy strips it, prod serves same-origin.
   */
  async startProvisioning(modelId = null, auto = true, activate = false) {
    const response = await authFetch(`${BASE_URL}/models/provision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId, auto, activate }),
    });
    if (!response.ok) {
      throw await errorFrom(response, `Provisioning failed with status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /models/provision/active - Returns currently running or recent provisioning job
   */
  async getActiveProvisioningJob() {
    const response = await authFetch(`${BASE_URL}/models/provision/active`);
    if (!response.ok) return null;
    return response.json();
  },

  /**
   * GET /models/provision/{job_id} - Polls job metrics
   */
  async getProvisioningStatus(jobId) {
    const response = await authFetch(`${BASE_URL}/models/provision/${jobId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch job status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /models/provision/{job_id}/stream - SSE live progress stream (authenticated).
   */
  streamProvisioningProgress(jobId, onProgress, onComplete, onError) {
    const controller = new AbortController();
    const headers = { Accept: 'text/event-stream' };
    const token = getAuthToken();
    // Header auth only: tokens are kept out of URLs (and therefore out of proxy/access logs).
    const streamUrl = `${BASE_URL}/models/provision/${jobId}/stream`;
    if (token) headers.Authorization = `Bearer ${token}`;
    fetch(streamUrl, {
      signal: controller.signal,
      headers,
    })
      .then(async (response) => {
        if (!response.ok) {
          if (response.status === 401) window.dispatchEvent(new Event('dfrag:unauthorized'));
          throw new Error(`SSE request failed: ${response.status}`);
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
                if (parsed.status === 'ready') {
                  if (onComplete) onComplete(parsed);
                  return;
                }
                if (parsed.status === 'failed' || parsed.status === 'cancelled') {
                  if (onError) onError(new Error(parsed.error || parsed.message || 'Provisioning stopped'));
                  return;
                }
              } catch (e) {
                // Ignore parse errors
              }
            }
          }
        }
        // The stream ended without a terminal status: report it instead of assuming success.
        if (onError) onError(new Error('Progress stream ended before the download finished; reload to resume tracking.'));
      })
      .catch((err) => {
        if (err.name === 'AbortError') {
          if (onError) onError(new Error('Stream closed'));
        } else {
          if (onError) onError(err);
        }
      });

    return controller;
  },

  /**
   * POST /api/models/provision/{job_id}/cancel
   */
  async cancelProvisioningJob(jobId) {
    const response = await authFetch(`${BASE_URL}/models/provision/${jobId}/cancel`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(`Failed to cancel job: ${response.status}`);
    }
    return response.json();
  },

  /**
   * GET /api/models/hf/search
   */
  async searchHfModels(query = 'legal gguf') {
    const response = await authFetch(`${BASE_URL}/models/hf/search?query=${encodeURIComponent(query)}`);
    if (!response.ok) return [];
    return response.json();
  },
};

