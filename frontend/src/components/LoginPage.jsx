import { useEffect, useMemo, useRef, useState } from 'react';
import {
  LogIn,
  UserPlus,
  Loader2,
  Eye,
  EyeOff,
  ScanSearch,
  Lightbulb,
  Power,
  Mail,
  Lock,
  User,
  TriangleAlert,
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import LanguageToggle from './LanguageToggle';
import { useI18n } from '../i18n';

// 0-4: length, upper+lower, digit, symbol
function passwordScore(value) {
  if (!value) return 0;
  let score = 0;
  if (value.length >= 8) score += 1;
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
  if (/\d/.test(value)) score += 1;
  if (/[^A-Za-z0-9]/.test(value) || value.length >= 14) score += 1;
  return score;
}

const STRENGTH_KEYS = ['', 'login.strengthWeak', 'login.strengthFair', 'login.strengthGood', 'login.strengthStrong'];

// Dust motes drifting in the lamplight (positions are random once per mount).
function useDust(count = 26) {
  return useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        id: i,
        left: 4 + Math.random() * 62,
        top: 12 + Math.random() * 70,
        size: 2 + Math.random() * 3,
        drift: 10 + Math.random() * 26,
        duration: 7 + Math.random() * 9,
        delay: -Math.random() * 12,
      })),
    [count],
  );
}

export default function LoginPage({ onLogin }) {
  const { t, tError } = useI18n();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLit, setIsLit] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [pulling, setPulling] = useState(false);
  const [shake, setShake] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const emailRef = useRef(null);
  const nameRef = useRef(null);
  const dust = useDust();

  const score = passwordScore(password);

  const handleLampToggle = () => {
    setIsLit((current) => !current);
    setError(null);
    // Brief cord-pull animation; purely visual, the toggle logic is unchanged.
    setPulling(true);
    setTimeout(() => setPulling(false), 340);
  };

  // Once the lamp is on and the card has faded in, put the cursor in the first field.
  useEffect(() => {
    if (!isLit) return undefined;
    const timer = setTimeout(() => (mode === 'register' ? nameRef : emailRef).current?.focus(), 900);
    return () => clearTimeout(timer);
  }, [isLit, mode]);

  const failWith = (value) => {
    setError(value);
    setShake(true);
    setTimeout(() => setShake(false), 500);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const body = mode === 'login'
        ? { email, password }
        : { email, name, password };

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      // A dead backend (e.g. the dev proxy answering 500 with an empty body) is not JSON.
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw Object.assign(new Error(data.error || ''), {
          missing: !data.error,
          unreachable: !data.error && response.status >= 500,
        });
      }

      localStorage.setItem('bugsight_token', data.token);
      if (data.refresh_token) {
        localStorage.setItem('bugsight_refresh_token', data.refresh_token);
      }
      localStorage.setItem('bugsight_user', JSON.stringify(data.user));
      onLogin(data.user);
    } catch (submissionError) {
      // fetch() rejects with a TypeError when the server cannot be reached
      if (submissionError instanceof TypeError || submissionError.unreachable) {
        failWith({ key: 'app.apiUnreachable' });
      }
      else if (submissionError.missing) failWith({ key: 'login.authFailed' });
      else failWith(submissionError.message);
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (nextMode) => {
    setMode(nextMode);
    setError(null);
  };

  const trackCapsLock = (event) => setCapsLock(event.getModifierState?.('CapsLock') ?? false);

  return (
    <main className={`auth-shell ${isLit ? 'auth-shell--lit' : 'auth-shell--dark'}`}>
      {/* The room the lamp lights up: warm wash, floor grid and drifting dust */}
      <div className="auth-room" aria-hidden="true">
        <div className="auth-room__wash" />
        <div className="auth-room__floor" />
        {dust.map((mote) => (
          <i
            key={mote.id}
            className="auth-dust"
            style={{
              left: `${mote.left}%`,
              top: `${mote.top}%`,
              width: mote.size,
              height: mote.size,
              '--drift': `${mote.drift}px`,
              animationDuration: `${mote.duration}s`,
              animationDelay: `${mote.delay}s`,
            }}
          />
        ))}
      </div>

      <div className="auth-topbar">
        <span className="auth-topbar__status">
          <span className="auth-status-dot" /> {t('login.topbar')}
        </span>
        <div className="flex items-center gap-2">
          <LanguageToggle />
          <ThemeToggle />
        </div>
      </div>

      <div className="auth-scene">
        <div className="auth-brand" aria-hidden={!isLit}>
          <div className="auth-brand__mark">BS</div>
          <div>
            <p className="auth-brand__name">
              BugSight <span>QA</span>
            </p>
            <p className="auth-brand__tagline">{t('login.tagline')}</p>
          </div>
        </div>

        <div className="lamp-stage">
          <div className="lamp-halo" aria-hidden="true" />
          <div className="lamp-floor" aria-hidden="true" />
          <div className="auth-ray" aria-hidden="true" />
          <button
            type="button"
            className={`lamp-button ${isLit ? 'lamp-button--on' : ''} ${pulling ? 'lamp-button--pulling' : ''}`}
            onClick={handleLampToggle}
            aria-label={isLit ? t('login.lampOff') : t('login.lampOn')}
            aria-pressed={isLit}
          >
            <span className="lamp-shade">
              <span className="lamp-shade__inner" />
            </span>
            <span className="lamp-bulb" />
            <span className="lamp-neck" />
            <span className="lamp-switch">
              <span className="lamp-switch__cord" />
              <span className="lamp-switch__handle" />
            </span>
            <span className="lamp-base" />
          </button>

          <p className="lamp-hint">
            <Power className="h-3.5 w-3.5" />
            {isLit ? t('login.hintOff') : t('login.hintOn')}
          </p>
        </div>

        <section
          className={`auth-card ${isLit ? 'auth-card--visible' : ''} ${shake ? 'auth-card--shake' : ''}`}
          aria-hidden={!isLit}
          // keeps the hidden form out of the tab order until the lamp is on
          {...(isLit ? {} : { inert: '' })}
        >
          <div className="auth-card__header auth-stagger" style={{ '--s': 0 }}>
            <div className="auth-card__icon">
              <Lightbulb className="h-5 w-5" />
            </div>
            <div>
              <p className="auth-card__eyebrow">
                <span className="auth-card__live" /> {t('login.eyebrow')}
              </p>
              <h1>{mode === 'login' ? t('login.welcomeBack') : t('login.createAccount')}</h1>
              <p className="auth-card__subtitle">
                {mode === 'login'
                  ? t('login.subtitleLogin')
                  : t('login.subtitleRegister')}
              </p>
            </div>
          </div>

          <div className="auth-tabs auth-stagger" style={{ '--s': 1 }} role="tablist" aria-label={t('login.tabsLabel')}>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'login'}
              className={mode === 'login' ? 'auth-tab auth-tab--active' : 'auth-tab'}
              onClick={() => switchMode('login')}
            >
              {t('login.signIn')}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'register'}
              className={mode === 'register' ? 'auth-tab auth-tab--active' : 'auth-tab'}
              onClick={() => switchMode('register')}
            >
              {t('login.register')}
            </button>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            {mode === 'register' && (
              <label className="auth-field auth-stagger" style={{ '--s': 2 }}>
                <span>{t('login.name')}</span>
                <span className="auth-input">
                  <User className="auth-input__icon" aria-hidden="true" />
                  <input
                    ref={nameRef}
                    type="text"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    required
                    autoComplete="name"
                    placeholder={t('login.namePh')}
                  />
                </span>
              </label>
            )}

            <label className="auth-field auth-stagger" style={{ '--s': 3 }}>
              <span>{t('login.email')}</span>
              <span className="auth-input">
                <Mail className="auth-input__icon" aria-hidden="true" />
                <input
                  ref={emailRef}
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  autoComplete="email"
                  placeholder={t('login.emailPh')}
                />
              </span>
            </label>

            <label className="auth-field auth-stagger" style={{ '--s': 4 }}>
              <span>{t('login.password')}</span>
              <span className="auth-password auth-input">
                <Lock className="auth-input__icon" aria-hidden="true" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  onKeyDown={trackCapsLock}
                  onKeyUp={trackCapsLock}
                  onBlur={() => setCapsLock(false)}
                  required
                  minLength={6}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  className="auth-password__toggle"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? t('login.hidePassword') : t('login.showPassword')}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </span>
              {capsLock && (
                <span className="auth-hint auth-hint--warn" role="status">
                  <TriangleAlert className="h-3 w-3" /> {t('login.capsLock')}
                </span>
              )}
              {mode === 'register' && password && (
                <span className="auth-strength" data-score={score} aria-live="polite">
                  <span className="auth-strength__bars" aria-hidden="true">
                    {[1, 2, 3, 4].map((level) => (
                      <i key={level} className={score >= level ? 'is-on' : ''} />
                    ))}
                  </span>
                  <span className="auth-strength__label">{t(STRENGTH_KEYS[score] || STRENGTH_KEYS[1])}</span>
                </span>
              )}
            </label>

            {error && (
              <div className="auth-error" role="alert">
                <span className="auth-error__bar" />
                {tError(error)}
              </div>
            )}

            <button type="submit" className="auth-submit auth-stagger" style={{ '--s': 5 }} disabled={loading}>
              {loading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> {t('login.wait')}</>
              ) : mode === 'login' ? (
                <><LogIn className="h-4 w-4" /> {t('login.signIn')}</>
              ) : (
                <><UserPlus className="h-4 w-4" /> {t('login.createAccount')}</>
              )}
            </button>
          </form>

          <div className="auth-card__footer auth-stagger" style={{ '--s': 6 }}>
            <ScanSearch className="h-3.5 w-3.5" />
            <span>{t('login.cardFooter')}</span>
          </div>
        </section>
      </div>

      <footer className="auth-footer">
        BugSight QA <span>•</span> YOLOv8 + Flask + React <span>•</span> PFA Project by Ala Jamli
      </footer>
    </main>
  );
}
