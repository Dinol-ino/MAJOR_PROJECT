const BASE_URL = '/api';

export const apiClient = {
  /**
   * POST /chat
   */
  async chat(message, sessionId, shieldOn) {
    const response = await fetch(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        shield_on: shieldOn,
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
  async recommend(ramGb, vramGb) {
    const response = await fetch(`${BASE_URL}/recommend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ram_gb: parseInt(ramGb) || 0,
        vram_gb: parseInt(vramGb) || 0,
      }),
    });
    if (!response.ok) {
      throw new Error(`Recommendation request failed with status: ${response.status}`);
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
