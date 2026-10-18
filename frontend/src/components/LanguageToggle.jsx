import { Languages } from 'lucide-react';
import { useI18n } from '../i18n';

const OPTIONS = ['en', 'fr'];

export default function LanguageToggle({ className = '' }) {
  const { lang, setLang, t } = useI18n();

  return (
    <div
      role="group"
      aria-label={t('lang.label')}
      className={
        'flex h-9 items-center gap-1 rounded-md border px-1.5 transition-colors ' +
        'bg-white border-gray-200 text-gray-600 ' +
        'dark:bg-[#111826] dark:border-[#243040] dark:text-gray-400 ' +
        className
      }
    >
      <Languages className="mx-0.5 h-4 w-4 opacity-60" aria-hidden="true" />
      {OPTIONS.map((code) => {
        const active = lang === code;
        return (
          <button
            key={code}
            type="button"
            onClick={() => setLang(code)}
            aria-pressed={active}
            title={t(`lang.${code}`)}
            lang={code}
            className={
              'bs-mono rounded px-1.5 py-1 text-[11px] font-semibold uppercase leading-none transition-colors ' +
              (active
                ? 'bg-[#0D9488] text-white dark:bg-[#5EEAD4] dark:text-[#0A0E14]'
                : 'hover:bg-gray-100 dark:hover:bg-[#161D28]')
            }
          >
            {code}
          </button>
        );
      })}
    </div>
  );
}
