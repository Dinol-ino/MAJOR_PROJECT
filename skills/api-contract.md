# API Contract

Frozen in Phase 0.

### 1. POST `/chat`
Sends a user query and returns the answer with citation sources, or flags indicating defense layer blockage.

- **Request body**:
```json
{
  "message": "What is punishment under Section 66 IT Act?",
  "session_id": "abc",
  "shield_on": true
}
```

- **Response body**:
```json
{
  "answer": "Under Section 66 of the IT Act, any person who commits computer-related offences shall be punished with imprisonment for a term which may extend to three years or with fine which may extend to five lakh rupees, or with both.",
  "sources": [
    {
      "act": "IT Act",
      "section": "66",
      "text": "Section 66: If any person, dishonestly or fraudulently, does any act referred to in section 43..."
    }
  ],
  "blocked_by": null, 
  "block_reason": null
}
```
*Note: `blocked_by` can be `null`, `"layer1"`, `"layer2"`, or `"layer3"`. If blocked, `answer` is replaced with standard quarantine/block messages.*

---

### 2. POST `/upload`
Uploads a user PDF document for Tier-2 session-based context retrieval.

- **Request (multipart/form-data)**:
  - `file`: PDF file content
  - `session_id`: String identifier for user session

- **Response body**:
```json
{
  "status": "ok",
  "chunks_added": 42,
  "filename": "contract.pdf",
  "reason": null
}
```
*Or, if rejected:*
```json
{
  "status": "rejected",
  "chunks_added": 0,
  "filename": "contract.pdf",
  "reason": "File size exceeds limits or type is not a valid PDF"
}
```

---

### 3. POST `/recommend`
Provides local Ollama model recommendations based on client hardware specs.

- **Request body**:
```json
{
  "ram_gb": 8,
  "vram_gb": 0
}
```

- **Response body**:
```json
{
  "recommended": [
    {
      "model": "qwen2.5:3b",
      "pull": "ollama pull qwen2.5:3b"
    }
  ]
}
```

---

### 4. GET `/audit/{session_id}`
Retrieves the append-only logs with cryptographic hash-chaining verification for the demo dashboard.

- **Response body**:
```json
{
  "rows": [
    {
      "ts": "2026-07-13T14:00:00Z",
      "action": "chat",
      "layer": null,
      "hash": "abc123hash...",
      "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000"
    }
  ]
}
```
