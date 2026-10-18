import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import en from './locales/en';
import fr from './locales/fr';

const DICTS = { en, fr };
const LOCALES = { en: 'en-US', fr: 'fr-FR' };
const STORAGE_KEY = 'bugsight_lang';

// Exact API error texts -> translation key.
const API_MESSAGES = {
  'Invalid credentials': 'api.invalidCredentials',
  'Email already registered': 'api.emailTaken',
  'Password must be 6+ characters': 'api.passwordShort',
  'Email, name and password required': 'api.fieldsRequired',
  'No image provided': 'api.noImage',
  'No video provided': 'api.noVideo',
  'Empty filename': 'api.emptyFilename',
  'Could not decode image': 'api.decodeFailed',
  'Model not available': 'api.modelUnavailable',
  'Prediction failed': 'api.predictionFailed',
  'Video analysis failed': 'api.videoFailed',
  'Could not read any frame from the video': 'api.noFrames',
  'Admin access required': 'api.adminRequired',
  'User not found': 'api.userNotFound',
  'You cannot delete your own account': 'api.cannotDeleteSelf',
  'You cannot remove your own admin role': 'api.cannotDemoteSelf',
  'Role must be admin or tester': 'api.badRole',
  'confidence must be a number': 'api.badNumber',
  'confidence and max_frames must be numbers': 'api.badNumber',
};

function getInitialLang() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'en' || saved === 'fr') return saved;
  } catch {
    // storage unavailable (private mode): fall through to browser language
  }
  return (navigator.language || 'en').toLowerCase().startsWith('fr') ? 'fr' : 'en';
}

const I18nContext = createContext(null);

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(getInitialLang);

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // ignore: the choice just won't persist
    }
  }, [lang]);

  const setLang = useCallback((next) => {
    if (next in DICTS) setLangState(next);
  }, []);

  const value = useMemo(() => {
    const dict = DICTS[lang];
    const locale = LOCALES[lang];

    const t = (key, vars) => {
      const template = dict[key] ?? en[key] ?? key;
      return vars
        ? template.replace(/\{(\w+)\}/g, (_, name) => (name in vars ? vars[name] : `{${name}}`))
        : template;
    };

    // Translate a bug class id like "screen_tear"; unknown ids are prettified.
    const tClass = (name = '') => {
      const key = `class.${name}`;
      return dict[key] ?? en[key] ?? name.replace(/_/g, ' ');
    };

    // Turn an API message (or a {key, vars} object) into text in the current language.
    const tError = (err) => {
      if (!err) return null;
      if (typeof err === 'object' && err.key) return t(err.key, err.vars);
      const message = typeof err === 'string' ? err : String(err.raw ?? '');
      if (API_MESSAGES[message]) return t(API_MESSAGES[message]);
      const tooLarge = message.match(/^File too large \(max (\d+) MB\)/);
      if (tooLarge) return t('api.tooLarge', { n: tooLarge[1] });
      if (/^Unsupported image type/.test(message)) return t('api.badImageType');
      if (/^Unsupported video type/.test(message)) return t('api.badVideoType');
      if (/^429|rate limit|too many requests/i.test(message)) return t('api.rateLimited');
      return message;
    };

    return {
      lang,
      locale,
      setLang,
      t,
      tClass,
      tError,
      formatDateTime: (v) => (v ? new Date(v).toLocaleString(locale) : '—'),
      formatTime: (v) => new Date(v).toLocaleTimeString(locale),
      formatShort: (v) =>
        v ? new Date(v).toLocaleString(locale, { dateStyle: 'short', timeStyle: 'short' }) : '—',
    };
  }, [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within an I18nProvider');
  return ctx;
}
