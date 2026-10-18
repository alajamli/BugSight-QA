import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';
import { useI18n } from './i18n';

const ToastContext = createContext(null);

const ICONS = {
  error: <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />,
  success: <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />,
  info: <Info className="mt-0.5 h-4 w-4 shrink-0 text-[#0D9488] dark:text-[#5EEAD4]" />,
};

export function ToastProvider({ children }) {
  const { t, tError } = useI18n();
  const [toasts, setToasts] = useState([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id) => {
    setToasts((list) => list.filter((item) => item.id !== id));
  }, []);

  // `message` is an API string or a { key, vars } object; it is translated when
  // rendered, so switching language also updates toasts that are still visible.
  const push = useCallback(
    (kind, message, ttl = kind === 'error' ? 7000 : 4000) => {
      const id = nextId.current++;
      setToasts((list) => [...list.slice(-3), { id, kind, message }]);
      if (ttl) setTimeout(() => dismiss(id), ttl);
      return id;
    },
    [dismiss],
  );

  const api = useMemo(
    () => ({
      error: (message) => push('error', message),
      success: (message) => push('success', message),
      info: (message) => push('info', message),
      dismiss,
    }),
    [push, dismiss],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-region" aria-live="polite">
        {toasts.map((item) => (
          <div
            key={item.id}
            role={item.kind === 'error' ? 'alert' : 'status'}
            className={`toast toast--${item.kind}`}
          >
            {ICONS[item.kind]}
            <span className="min-w-0 break-words">{tError(item.message)}</span>
            <button
              type="button"
              className="toast__close"
              onClick={() => dismiss(item.id)}
              aria-label={t('toast.close')}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within a ToastProvider');
  return ctx;
}
