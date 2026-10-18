import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { BarChart3, PieChart as PieIcon } from 'lucide-react';
import { useTheme } from '../ThemeContext';
import { useI18n } from '../i18n';
import { CLASS_COLORS, classColor } from '../classColors';

const BUG = '#F87171';
const CLEAN = '#34D399';

/** Two cards: verdict split (donut) and bugs by class (bars coloured like the detection overlay). */
export default function StatsPanel({ stats }) {
  const { theme } = useTheme();
  const { t, tClass } = useI18n();
  const isDark = theme === 'dark';
  const tooltipStyle = {
    backgroundColor: isDark ? '#0D1219' : '#ffffff',
    border: `1px solid ${isDark ? '#243040' : '#DCE6E8'}`,
    borderRadius: '10px',
    color: isDark ? '#e5e7eb' : '#0F1B24',
    fontSize: '12px',
  };

  const hasData = stats && stats.total_analyses > 0;
  const total = stats?.total_analyses ?? 0;

  const pieData = [
    { name: t('stats.pieBug'), value: stats?.bug_detected ?? 0, color: BUG },
    { name: t('stats.pieClean'), value: stats?.clean ?? 0, color: CLEAN },
  ];

  // Every known class is listed (zeros included) so the ranking stays stable between sessions.
  const known = Object.keys(CLASS_COLORS);
  const distribution = stats?.class_distribution || {};
  const classes = [...new Set([...known, ...Object.keys(distribution)])]
    .map((name) => ({ name, value: distribution[name] || 0 }))
    .sort((a, b) => b.value - a.value);
  const maxCount = Math.max(1, ...classes.map((c) => c.value));
  const anyClass = classes.some((c) => c.value > 0);

  const empty = (
    <div className="empty-state">
      <BarChart3 className="h-8 w-8 opacity-40" />
      {t('stats.empty')}
    </div>
  );

  return (
    <>
      <section className="panel panel-enter">
        <h2 className="panel-title">
          <span className="panel-icon"><PieIcon className="h-4 w-4" /></span> {t('stats.distribution')}
        </h2>
        {!hasData ? empty : (
          <div className="flex flex-col items-center gap-5">
            <div className="relative h-44 w-44 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={56} outerRadius={78} paddingAngle={4} cornerRadius={6} dataKey="value" stroke="none">
                    {pieData.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-bold tracking-tight text-[#0F1B24] dark:text-white">{total}</span>
                <span className="tile-label">{t('stats.analysesLabel')}</span>
              </div>
            </div>
            <ul className="grid w-full grid-cols-2 gap-2.5">
              {pieData.map((d) => (
                <li key={d.name} className="tile flex flex-col gap-1 !py-2.5 text-sm">
                  <span className="flex items-center gap-2 text-[#0F1B24] dark:text-gray-200">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: d.color, boxShadow: `0 0 8px ${d.color}` }} />
                    {d.name}
                  </span>
                  <span className="bs-mono text-xs">
                    <b className="text-[#0F1B24] dark:text-white">{d.value}</b>
                    <span className="ml-1.5 text-[#5B6B74] dark:text-gray-500">{total ? Math.round((d.value / total) * 100) : 0}%</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="panel panel-enter">
        <h2 className="panel-title">
          <span className="panel-icon"><BarChart3 className="h-4 w-4" /></span> {t('stats.classesTitle')}
        </h2>
        {!hasData ? empty : !anyClass ? (
          <div className="empty-state">{t('stats.noClassData')}</div>
        ) : (
          <ul className="space-y-3.5">
            {classes.map(({ name, value }, i) => (
              <li key={name} className="cls-row" style={{ '--c': classColor(name), '--i': i }}>
                <div className="cls-row__head">
                  <span className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: classColor(name) }} />
                    <span className={value === 0 ? 'opacity-50' : ''}>{tClass(name)}</span>
                  </span>
                  <span className="bs-mono text-xs font-semibold" style={{ color: value ? classColor(name) : undefined }}>{value}</span>
                </div>
                <div className="cls-row__track">
                  <span className="cls-row__fill" style={{ width: `${(value / maxCount) * 100}%` }} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
