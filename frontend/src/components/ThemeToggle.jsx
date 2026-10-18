import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../ThemeContext';
import { useI18n } from '../i18n';

export default function ThemeToggle({ className = '' }) {
  const { theme, toggleTheme } = useTheme();
  const { t } = useI18n();
  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? t('theme.toLight') : t('theme.toDark')}
      title={isDark ? t('theme.light') : t('theme.dark')}
      className={
        'relative flex items-center justify-center w-9 h-9 rounded-md border transition-colors ' +
        'bg-white hover:bg-gray-100 border-gray-200 text-gray-600 ' +
        'dark:bg-[#111826] dark:hover:bg-[#161D28] dark:border-[#243040] dark:text-gray-400 dark:hover:text-[#5EEAD4] ' +
        className
      }
    >
      <Sun className={`w-4 h-4 transition-all ${isDark ? 'scale-0 opacity-0 absolute' : 'scale-100 opacity-100'}`} />
      <Moon className={`w-4 h-4 transition-all ${isDark ? 'scale-100 opacity-100' : 'scale-0 opacity-0 absolute'}`} />
    </button>
  );
}