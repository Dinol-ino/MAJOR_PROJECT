/**
 * One registration for the whole run.
 *
 * /auth/register is rate limited to 5/minute, so registering per test (or even per
 * worker) makes the suite fail with 429. Here a single throwaway practitioner is
 * created and its session token written as a Playwright storageState, which every
 * spec then reuses.
 */
import fs from 'fs';
import path from 'path';
import { registerUser } from './fixtures/auth';

const STATE_PATH = path.join(process.cwd(), 'e2e', '.auth', 'state.json');
const ORIGIN = process.env.E2E_BASE_URL || 'http://localhost:3000';

export default async function globalSetup() {
  const { token, username } = await registerUser();
  fs.mkdirSync(path.dirname(STATE_PATH), { recursive: true });
  fs.writeFileSync(
    STATE_PATH,
    JSON.stringify(
      {
        cookies: [],
        origins: [
          { origin: ORIGIN, localStorage: [{ name: 'dfrag_auth_token', value: token }] },
        ],
      },
      null,
      2,
    ),
  );
  console.log(`[e2e] authenticated as ${username}`);
}
