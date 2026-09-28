import React, { useState } from 'react';
import { apiClient, setAuthToken } from '../api/client';

/**
 * LoginView — Luxury / Editorial Authentication Gate for DFrag Legal Engine.
 * Architectural precision (0px border-radius), Playfair Display serif typography,
 * grayscale-to-color Lady Justice artwork with 1800ms hover reward,
 * underline-only inputs, and sliding gold button animation.
 */
export default function LoginView({ onLoginSuccess, theme, setTheme }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let result;
      if (mode === 'login') {
        result = await apiClient.login(username, password);
      } else {
        if (!email.trim()) {
          setError('Email is required for practitioner registration.');
          setLoading(false);
          return;
        }
        result = await apiClient.register(username, email, password, fullName || undefined);
      }

      if (result && result.token) {
        setAuthToken(result.token);
        onLoginSuccess(result.user || { username });
      } else {
        setError('Authentication succeeded but no authorization token was issued.');
      }
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify practitioner credentials.');
    } finally {
      setLoading(false);
    }
  };

  const toggleTheme = () => {
    if (setTheme) {
      setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
    }
  };

  return (
    <div style={styles.pageContainer}>
      {/* Top Utility Bar: Edition Marker & Theme Switcher */}
      <div style={styles.topBar}>
        <div style={styles.topBarLeft}>
          <span style={styles.editionTag}>JURISPRUDENCE / VOL. 01</span>
          <span style={styles.editionDivider}>—</span>
          <span style={styles.systemTag}>AUTONOMOUS DEFENSIVE RAG</span>
        </div>
        <div style={styles.topBarRight}>
          {setTheme && (
            <button
              type="button"
              onClick={toggleTheme}
              style={styles.themeToggleBtn}
              title="Toggle Editorial Palette (Alabaster Paper / Rich Charcoal)"
            >
              {theme === 'light' ? '✦ DARK CHARCOAL' : '✦ WARM ALABASTER'}
            </button>
          )}
        </div>
      </div>

      {/* Main Editorial 2-Column Split */}
      <div style={styles.mainGrid}>
        {/* Left Column: Lady Justice Editorial Showcase */}
        <div style={styles.leftShowcase}>
          <div className="editorial-image-container" style={styles.imageFrame}>
            <div style={styles.verticalWatermark} className="editorial-vertical-label">
              JUSTICE &bull; RATIO DECIDENDI
            </div>
            <img
              src="/justice-poster.jpg"
              alt="Lady Justice Editorial Poster"
              className="editorial-image"
              style={styles.heroPosterImg}
              onError={(e) => {
                // Fallback to landscape if poster not found
                e.target.src = '/justice-bg.jpg';
              }}
            />
            {/* Subtle Overlay Badge on Image */}
            <div style={styles.imageCaptionBar}>
              <span style={styles.captionLatin}>FIAT JUSTITIA RUAT CAELUM</span>
              <span style={styles.captionSub}>Moral clarity in legal AI</span>
            </div>
          </div>

          {/* Editorial Quote Block */}
          <div style={styles.leftQuoteBlock}>
            <p className="editorial-drop-cap" style={styles.dropCapParagraph}>
              Yield not to the influence of power, but let each act rest on the unwavering balance of truth and ethical reckoning. Where algorithms parse human liberty, defense must be absolute.
            </p>
          </div>
        </div>

        {/* Right Column: Architectural Login Card */}
        <div style={styles.rightCard}>
          {/* Header Title with Mixed Italics */}
          <div style={styles.cardHeader}>
            <div style={styles.brandBadge}>
              <span style={{ color: 'var(--accent-gold)', fontSize: '0.8rem' }}>✦</span>
              <span style={styles.brandBadgeText}>LEGAL VERIFICATION GATE</span>
            </div>

            <h1 className="editorial-title" style={styles.cardTitle}>
              JUSTICE <span className="editorial-italic">Copilot</span>
            </h1>
            <p style={styles.cardSubtitle}>
              Access the high-integrity statutory research & citation engine.
            </p>
          </div>

          {/* Mode Switcher (Underline Architectural Tabs) */}
          <div style={styles.tabsRow}>
            <button
              type="button"
              onClick={() => { setMode('login'); setError(''); }}
              style={mode === 'login' ? styles.tabActive : styles.tab}
            >
              SIGN IN
            </button>
            <button
              type="button"
              onClick={() => { setMode('register'); setError(''); }}
              style={mode === 'register' ? styles.tabActive : styles.tab}
            >
              REGISTER PRACTITIONER
            </button>
          </div>

          {/* Interactive Form */}
          <form onSubmit={handleSubmit} style={styles.form}>
            <div style={styles.inputGroup}>
              <label style={styles.inputLabel}>PRACTITIONER USERNAME</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. advocate_castelino"
                required
                minLength={3}
                className="luxury-input"
                autoComplete="username"
              />
            </div>

            {mode === 'register' && (
              <>
                <div style={styles.inputGroup}>
                  <label style={styles.inputLabel}>EMAIL ADDRESS</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="e.g. counsel@supremecourt.in"
                    required
                    className="luxury-input"
                    autoComplete="email"
                  />
                </div>
                <div style={styles.inputGroup}>
                  <label style={styles.inputLabel}>FULL LEGAL NAME</label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Advocate Dinol Castelino"
                    className="luxury-input"
                    autoComplete="name"
                  />
                </div>
              </>
            )}

            <div style={styles.inputGroup}>
              <label style={styles.inputLabel}>CONFIDENTIAL KEY / PASSWORD</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === 'register' ? 'Minimum 6 characters' : 'Enter passkey'}
                required
                minLength={mode === 'register' ? 6 : 1}
                className="luxury-input"
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              />
            </div>

            {error && (
              <div style={styles.errorBox}>
                <span style={{ color: 'var(--status-red)', fontWeight: 700 }}>&sect; ERROR:</span> {error}
              </div>
            )}

            {/* Luxury Gold Slide Button */}
            <button
              type="submit"
              disabled={loading}
              className="luxury-btn-primary"
              style={{ marginTop: '14px', width: '100%', height: '48px' }}
            >
              <span>{loading ? 'AUTHENTICATING ENCRYPTED LEDGER…' : (mode === 'login' ? 'ENTER WORKSPACE ✦' : 'CREATE PRACTITIONER ACCOUNT ✦')}</span>
            </button>

            {/* Quick Demo Access Button */}
            {mode === 'login' && (
              <button
                type="button"
                onClick={() => {
                  setUsername('admin');
                  setPassword('AdminPass123!');
                }}
                className="luxury-btn-secondary"
                style={{ width: '100%', height: '40px', marginTop: '10px' }}
              >
                <span>DEMO CREDENTIALS (ADMIN / ADMINPASS123!)</span>
              </button>
            )}
          </form>

          {/* Footer Note */}
          <div style={styles.cardFooter}>
            <div style={styles.footerRule} />
            <p style={styles.footerNote}>
              {mode === 'login'
                ? 'Statutory compliance ensured via cryptographic audit trails.'
                : 'Account creation registers your public key in the local immutable ledger.'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

const styles = {
  pageContainer: {
    minHeight: '100vh',
    width: '100vw',
    backgroundColor: 'var(--bg-app)',
    color: 'var(--text-primary)',
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
    overflowY: 'auto',
    overflowX: 'hidden',
    padding: '24px 32px',
    boxSizing: 'border-box',
    zIndex: 10,
  },
  topBar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: '20px',
    borderBottom: '1px solid var(--border-subtle)',
    maxWidth: '1400px',
    width: '100%',
    margin: '0 auto 32px',
  },
  topBarLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  editionTag: {
    fontFamily: 'var(--font-mono)',
    fontSize: '0.72rem',
    letterSpacing: '0.22em',
    color: 'var(--accent-gold)',
    fontWeight: 600,
  },
  editionDivider: {
    color: 'var(--text-dim)',
  },
  systemTag: {
    fontFamily: 'var(--font-sans)',
    fontSize: '0.72rem',
    letterSpacing: '0.15em',
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
  },
  topBarRight: {
    display: 'flex',
    alignItems: 'center',
  },
  themeToggleBtn: {
    background: 'transparent',
    border: '1px solid var(--border-medium)',
    color: 'var(--text-secondary)',
    padding: '6px 14px',
    fontSize: '0.68rem',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.18em',
    borderRadius: '0px',
    cursor: 'pointer',
    transition: 'all 0.3s ease',
  },
  mainGrid: {
    display: 'grid',
    gridTemplateColumns: 'minmax(320px, 1.1fr) minmax(340px, 1fr)',
    gap: '48px',
    maxWidth: '1400px',
    width: '100%',
    margin: '0 auto',
    alignItems: 'center',
  },
  leftShowcase: {
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
  },
  imageFrame: {
    position: 'relative',
    height: '460px',
    width: '100%',
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-medium)',
  },
  verticalWatermark: {
    position: 'absolute',
    left: '12px',
    top: '20px',
    zIndex: 5,
    color: 'var(--accent-gold)',
    background: 'rgba(20, 20, 20, 0.75)',
    padding: '8px 4px',
    borderLeft: '1px solid var(--accent-gold)',
  },
  heroPosterImg: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    objectPosition: 'center 20%',
  },
  imageCaptionBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    background: 'linear-gradient(to top, rgba(17, 17, 17, 0.95) 0%, rgba(17, 17, 17, 0) 100%)',
    padding: '24px 20px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    zIndex: 4,
  },
  captionLatin: {
    fontFamily: 'var(--font-serif)',
    fontSize: '0.86rem',
    letterSpacing: '0.14em',
    color: 'var(--accent-gold)',
    fontStyle: 'italic',
  },
  captionSub: {
    fontFamily: 'var(--font-mono)',
    fontSize: '0.64rem',
    letterSpacing: '0.08em',
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
  },
  leftQuoteBlock: {
    borderLeft: '2px solid var(--accent-gold)',
    paddingLeft: '20px',
    paddingTop: '6px',
    paddingBottom: '6px',
  },
  dropCapParagraph: {
    fontFamily: 'var(--font-sans)',
    fontSize: '0.88rem',
    color: 'var(--text-secondary)',
    lineHeight: 1.65,
    margin: 0,
  },
  rightCard: {
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    borderTop: '2px solid var(--accent-gold)',
    padding: '44px 44px 36px',
    boxShadow: 'var(--shadow-md)',
  },
  cardHeader: {
    marginBottom: '28px',
  },
  brandBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '12px',
  },
  brandBadgeText: {
    fontFamily: 'var(--font-mono)',
    fontSize: '0.68rem',
    letterSpacing: '0.22em',
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
  },
  cardTitle: {
    fontSize: '2.5rem',
    margin: '0 0 8px 0',
    color: 'var(--text-primary)',
  },
  cardSubtitle: {
    fontFamily: 'var(--font-sans)',
    fontSize: '0.86rem',
    color: 'var(--text-secondary)',
    lineHeight: 1.5,
    margin: 0,
  },
  tabsRow: {
    display: 'flex',
    gap: '24px',
    borderBottom: '1px solid var(--border-subtle)',
    marginBottom: '26px',
  },
  tab: {
    background: 'none',
    border: 'none',
    borderBottom: '2px solid transparent',
    padding: '8px 0',
    fontFamily: 'var(--font-sans)',
    fontSize: '0.74rem',
    letterSpacing: '0.18em',
    color: 'var(--text-muted)',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.3s ease',
  },
  tabActive: {
    background: 'none',
    border: 'none',
    borderBottom: '2px solid var(--accent-gold)',
    padding: '8px 0',
    fontFamily: 'var(--font-sans)',
    fontSize: '0.74rem',
    letterSpacing: '0.18em',
    color: 'var(--accent-gold)',
    fontWeight: 700,
    cursor: 'pointer',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  inputLabel: {
    fontFamily: 'var(--font-mono)',
    fontSize: '0.65rem',
    letterSpacing: '0.18em',
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
  },
  errorBox: {
    padding: '12px 16px',
    backgroundColor: 'rgba(239, 35, 60, 0.08)',
    borderLeft: '2px solid var(--status-red)',
    color: 'var(--text-primary)',
    fontSize: '0.82rem',
    fontFamily: 'var(--font-mono)',
    lineHeight: 1.4,
  },
  cardFooter: {
    marginTop: '28px',
  },
  footerRule: {
    height: '1px',
    backgroundColor: 'var(--border-subtle)',
    marginBottom: '14px',
  },
  footerNote: {
    fontFamily: 'var(--font-sans)',
    fontSize: '0.74rem',
    color: 'var(--text-muted)',
    margin: 0,
    textAlign: 'center',
    letterSpacing: '0.02em',
  },
};
