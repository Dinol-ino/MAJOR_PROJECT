const BASE_URL = '/api';

export const apiClient = {
  /**
   * POST /chat
   */
  async chat(message, sessionId, shieldOn, model) {
    const response = await fetch(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        shield_on: shieldOn,
        model: model || undefined,
      }),
    });
    if (!response.ok) {
      throw new Error(`Chat request failed with status: ${response.status}`);
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
};
