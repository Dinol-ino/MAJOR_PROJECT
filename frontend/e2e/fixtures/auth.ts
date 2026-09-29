/**
 * E2E authentication helpers.
 *
 * Every business route requires a session token (backend app/routes/auth.py), so a
 * spec that navigates to "/" without one lands on the sign-in screen. The token is
 * provisioned once in e2e/global-setup.ts and injected into every page through
 * Playwright's storageState, so specs simply start inside the workspace.
 *
 * The backend must be reachable at E2E_API_URL (default http://127.0.0.1:8000).
 */
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API_URL || 'http://127.0.0.1:8000';

export interface RegisteredUser {
  username: string;
  token: string;
  user: Record<string, unknown>;
}

/** Registers a unique practitioner account and returns its session token. */
export async function registerUser(prefix = 'e2e'): Promise<RegisteredUser> {
  const username = `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
  const res = await fetch(`${API}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username,
      email: `${username}@dfrag.invalid`,
      password: 'e2e-password-123',
      full_name: 'E2E Practitioner',
    }),
  });
  if (!res.ok) {
    throw new Error(`E2E registration failed (${res.status}): ${await res.text()}`);
  }
  const body = await res.json();
  return { username, token: body.token, user: body.user };
}

export { test, expect };
