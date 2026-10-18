import { useEffect, useRef, useState } from 'react';
import { ChevronDown, LogOut, ShieldCheck } from 'lucide-react';
import { useI18n } from '../i18n';

/** Avatar dropdown: who is signed in, admin shortcut and logout (replaces three crowded header buttons). */
export default function UserMenu({ user, onAdmin, onLogout }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const isAdmin = user.role === 'admin';

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => !ref.current?.contains(e.target) && setOpen(false);
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        className="btn-ghost !gap-2 !py-1 !pl-1 !pr-2.5"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t('app.account')}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="avatar">{(user.name || user.email || '?').charAt(0).toUpperCase()}</span>
        <span className="hidden max-w-[8rem] truncate text-left sm:block">{user.name}</span>
        <ChevronDown className={`h-3.5 w-3.5 opacity-60 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="menu" role="menu">
          <div className="border-b border-[#E3EBED] px-4 py-3 dark:border-[#1E2733]">
            <p className="truncate text-sm font-semibold text-[#0F1B24] dark:text-white">{user.name}</p>
            <p className="bs-mono truncate text-[11px] text-[#5B6B74] dark:text-gray-500">{user.email}</p>
            <span className="badge mt-2 border-teal-500/30 bg-teal-500/10 !py-0.5 text-[#0D9488] dark:text-[#5EEAD4]">
              {t(`role.${user.role}`)}
            </span>
          </div>
          <button
            type="button"
            role="menuitem"
            className="menu__item"
            disabled={!isAdmin}
            title={isAdmin ? t('app.adminOpen') : t('app.adminOnly')}
            onClick={() => { setOpen(false); onAdmin(); }}
          >
            <ShieldCheck className="h-4 w-4 text-[#0D9488] dark:text-[#5EEAD4]" /> {t('app.admin')}
          </button>
          <button type="button" role="menuitem" className="menu__item menu__item--danger" onClick={onLogout}>
            <LogOut className="h-4 w-4" /> {t('app.logout')}
          </button>
        </div>
      )}
    </div>
  );
}
