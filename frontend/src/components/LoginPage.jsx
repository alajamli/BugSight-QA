import { useState } from 'react';
import {
  LogIn,
  UserPlus,
  Loader2,
  Eye,
  EyeOff,
  ScanSearch,
  Lightbulb,
  Power,
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import LanguageToggle from './LanguageToggle';
import { useI18n } from '../i18n';

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

  const handleLampToggle = () => {
    setIsLit((current) => !current);
    setError(null);
    // Brief cord-pull animation; purely visual, the toggle logic is unchanged.
    setPulling(true);
    setTimeout(() => setPulling(false), 340);
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

      const data = await response.json();
      if (!response.ok) {
        throw Object.assign(new Error(data.error || ''), { missing: !data.error });
      }

      localStorage.setItem('bugsight_token', data.token);
      if (data.refresh_token) {
        localStorage.setItem('bugsight_refresh_token', data.refresh_token);
      }
      localStorage.setItem('bugsight_user', JSON.stringify(data.user));
      onLogin(data.user);
    } catch (submissionError) {
      // fetch() rejects with a TypeError when the server cannot be reached
      if (submissionError instanceof TypeError) setError({ key: 'app.apiUnreachable' });
      else if (submissionError.missing) setError({ key: 'login.authFailed' });
      else setError(submissionError.message);
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (nextMode) => {
    setMode(nextMode);
    setError(null);
  };

  return (
    <main className={`auth-shell ${isLit ? 'auth-shell--lit' : 'auth-shell--dark'}`}>
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

        <section className={`auth-card ${isLit ? 'auth-card--visible' : ''}`} aria-hidden={!isLit}>
          <div className="auth-card__header">
            <div className="auth-card__icon">
              <Lightbulb className="h-5 w-5" />
            </div>
            <div>
              <p className="auth-card__eyebrow">{t('login.eyebrow')}</p>
              <h1>{mode === 'login' ? t('login.welcomeBack') : t('login.createAccount')}</h1>
              <p className="auth-card__subtitle">
                {mode === 'login'
                  ? t('login.subtitleLogin')
                  : t('login.subtitleRegister')}
              </p>
            </div>
          </div>

          <div className="auth-tabs" role="tablist" aria-label={t('login.tabsLabel')}>
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
              <label className="auth-field">
                <span>{t('login.name')}</span>
                <input
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                  autoComplete="name"
                  placeholder={t('login.namePh')}
                />
              </label>
            )}

            <label className="auth-field">
              <span>{t('login.email')}</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                autoComplete="email"
                placeholder={t('login.emailPh')}
              />
            </label>

            <label className="auth-field">
              <span>{t('login.password')}</span>
              <span className="auth-password">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
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
            </label>

            {error && (
              <div className="auth-error" role="alert">
                <span className="auth-error__bar" />
                {tError(error)}
              </div>
            )}

            <button type="submit" className="auth-submit" disabled={loading}>
              {loading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> {t('login.wait')}</>
              ) : mode === 'login' ? (
                <><LogIn className="h-4 w-4" /> {t('login.signIn')}</>
              ) : (
                <><UserPlus className="h-4 w-4" /> {t('login.createAccount')}</>
              )}
            </button>
          </form>

          <div className="auth-card__footer">
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
