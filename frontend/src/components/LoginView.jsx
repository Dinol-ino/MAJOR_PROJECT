import React, { useEffect, useState } from 'react';
import { apiClient, setAuthToken } from '../api/client';

/**
 * Sign-in / first-account registration.
 * The server decides whether registration is open (/auth/status). There are no demo
 * credentials and no token-less "guest" mode.
 */
export default function LoginView({ onLoginSuccess, theme, setTheme }) {
  const [status, setStatus] = useState(null); // { accounts_exist, registration_open, password_min_length }
  const [statusError, setStatusError] = useState('');
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    apiClient.authStatus()
      .then((s) => {
        if (!active) return;
        setStatus(s);
        if (!s.accounts_exist) setMode('register');
      })
      .catch((err) => active && setStatusError(err.message || 'The workspace service is not reachable.'));
    return () => { active = false; };
  }, []);

  const minLen = status?.password_min_length || 8;
  const firstAccount = status && !status.accounts_exist;
  const canRegister = !status || status.registration_open;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = mode === 'login'
        ? await apiClient.login(username, password)
        : await apiClient.register(username, email, password, fullName || undefined);
      if (!result?.token) throw new Error('Sign-in succeeded but no session was issued.');
      setAuthToken(result.token);
      onLoginSuccess(result.user);
    } catch (err) {
      setError(err.message || 'Sign-in failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={s.page}>
      <header style={s.top}>
        <span style={s.brand}>DFrag</span>
        <span style={s.brandSub}>Defensive legal research workspace</span>
        {setTheme && (
          <button type="button" style={s.link} onClick={() => setTheme((p) => (p === 'light' ? 'dark' : 'light'))}>
            {theme === 'light' ? 'Dark' : 'Light'} theme
          </button>
        )}
      </header>

      <main style={s.main}>
        <section style={s.card} aria-labelledby="auth-title">
          <h1 id="auth-title" style={s.title}>
            {firstAccount ? 'Create the workspace owner account' : mode === 'login' ? 'Sign in' : 'Create an account'}
          </h1>
          <p style={s.lede}>
            {firstAccount
              ? 'No accounts exist yet. The first account administers this workspace.'
              : 'Answers are drawn from your indexed statutes and documents, with citations you can inspect.'}
          </p>

          {statusError && <div role="alert" style={s.error}>{statusError}</div>}

          {!firstAccount && (
            <div style={s.tabs} role="tablist">
              <button type="button" role="tab" aria-selected={mode === 'login'} style={mode === 'login' ? s.tabOn : s.tab} onClick={() => { setMode('login'); setError(''); }}>Sign in</button>
              {canRegister && (
                <button type="button" role="tab" aria-selected={mode === 'register'} style={mode === 'register' ? s.tabOn : s.tab} onClick={() => { setMode('register'); setError(''); }}>Register</button>
              )}
            </div>
          )}

          <form onSubmit={handleSubmit} style={s.form}>
            <Field label="Username or email" hidden={mode !== 'login'}>
              <input style={s.input} value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required={mode === 'login'} />
            </Field>
            {mode === 'register' && (
              <>
                <Field label="Username">
                  <input style={s.input} value={username} onChange={(e) => setUsername(e.target.value)} minLength={3} maxLength={64} autoComplete="username" required />
                </Field>
                <Field label="Email">
                  <input style={s.input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
                </Field>
                <Field label="Full name (optional)">
                  <input style={s.input} value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" />
                </Field>
              </>
            )}
            <Field label="Password">
              <input
                style={s.input}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={mode === 'register' ? minLen : 1}
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                required
              />
              {mode === 'register' && <small style={s.hint}>At least {minLen} characters.</small>}
            </Field>

            {error && <div role="alert" style={s.error}>{error}</div>}

            <button type="submit" disabled={loading || !!statusError} style={s.primary}>
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}

function Field({ label, children, hidden }) {
  if (hidden) return null;
  return (
    <label style={s.field}>
      <span style={s.label}>{label}</span>
      {children}
    </label>
  );
}

const s = {
  page: { minHeight: '100vh', background: 'var(--bg-app)', color: 'var(--text-primary)', display: 'flex', flexDirection: 'column', overflowY: 'auto' },
  top: { display: 'flex', alignItems: 'baseline', gap: 12, padding: '20px 32px', borderBottom: '1px solid var(--border-subtle)' },
  brand: { fontFamily: 'var(--font-serif)', fontSize: '1.25rem', fontWeight: 600 },
  brandSub: { color: 'var(--text-muted)', fontSize: '0.85rem', flex: 1 },
  link: { background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.82rem', textDecoration: 'underline' },
  main: { flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '48px 16px' },
  card: { width: '100%', maxWidth: 440, borderTop: '2px solid var(--accent)', paddingTop: 28 },
  title: { fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: '1.9rem', lineHeight: 1.2, marginBottom: 10 },
  lede: { color: 'var(--text-secondary)', fontFamily: 'var(--font-serif)', fontSize: '1.02rem', lineHeight: 1.55, marginBottom: 24 },
  tabs: { display: 'flex', gap: 20, borderBottom: '1px solid var(--border-subtle)', marginBottom: 20 },
  tab: { background: 'none', border: 'none', borderBottom: '2px solid transparent', color: 'var(--text-muted)', padding: '8px 0', cursor: 'pointer', fontSize: '0.9rem' },
  tabOn: { background: 'none', border: 'none', borderBottom: '2px solid var(--accent)', color: 'var(--text-primary)', padding: '8px 0', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600 },
  form: { display: 'flex', flexDirection: 'column', gap: 16 },
  field: { display: 'flex', flexDirection: 'column', gap: 6 },
  label: { fontSize: '0.8rem', color: 'var(--text-secondary)' },
  input: { background: 'var(--bg-input)', border: '1px solid var(--border-medium)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', padding: '10px 12px', fontSize: '0.95rem', fontFamily: 'var(--font-sans)' },
  hint: { color: 'var(--text-muted)', fontSize: '0.75rem' },
  error: { border: '1px solid var(--status-red)', color: 'var(--status-red)', padding: '10px 12px', fontSize: '0.85rem', borderRadius: 'var(--radius-sm)' },
  primary: { marginTop: 8, background: 'var(--accent)', color: 'var(--bg-app)', border: 'none', borderRadius: 'var(--radius-sm)', padding: '12px 16px', fontSize: '0.95rem', fontWeight: 600, cursor: 'pointer' },
};
