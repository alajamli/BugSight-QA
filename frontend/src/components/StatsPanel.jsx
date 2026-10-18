import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import { BarChart3, TrendingUp } from 'lucide-react';
import { useTheme } from '../ThemeContext';
import { useI18n } from '../i18n';

const CLASS_COLORS = ['#F87171', '#FBBF24', '#A78BFA', '#60A5FA', '#34D399', '#F472B6'];

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
  const gridStroke = isDark ? '#1E2733' : '#E3EBED';
  const axisStroke = isDark ? '#6b7280' : '#5B6B74';

  const header = (
    <h2 className="panel-title">
      <span className="panel-icon"><BarChart3 className="w-4 h-4" /></span> {t('stats.title')}
    </h2>
  );

  if (!stats || stats.total_analyses === 0) {
    return (
      <div className="panel panel-enter">
        {header}
        <div className="empty-state">
          <BarChart3 className="w-8 h-8 opacity-40" />
          {t('stats.empty')}
        </div>
      </div>
    );
  }

  const pieData = [
    { name: t('stats.pieBug'), value: stats.bug_detected, color: '#F87171' },
    { name: t('stats.pieClean'), value: stats.clean, color: '#34D399' },
  ];

  const classData = stats.class_distribution
    ? Object.entries(stats.class_distribution)
        .filter(([, v]) => v > 0)
        .map(([name, value]) => ({ name: tClass(name), value }))
    : [];

  return (
    <div className="panel panel-enter">
      {header}

      <div className="grid grid-cols-3 gap-2.5 mb-4">
        <div className="tile text-center">
          <p className="text-2xl font-bold text-[#0F1B24] dark:text-white">{stats.total_analyses}</p>
          <p className="tile-label">{t('stats.total')}</p>
        </div>
        <div className="tile text-center">
          <p className="text-2xl font-bold text-red-500 dark:text-red-400">{stats.bug_detected}</p>
          <p className="tile-label">{t('stats.bugs')}</p>
        </div>
        <div className="tile text-center">
          <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{stats.clean}</p>
          <p className="tile-label">{t('stats.clean')}</p>
        </div>
      </div>

      <div className="relative mb-5 overflow-hidden rounded-xl border border-red-200/70 bg-gradient-to-br from-red-50 to-white p-4 dark:border-red-500/20 dark:from-red-500/10 dark:to-transparent">
        <div className="flex items-center justify-between">
          <div>
            <p className="tile-label">{t('stats.rate')}</p>
            <p className="mt-1 text-3xl font-bold text-red-500 dark:text-red-400">
              {(stats.bug_rate * 100).toFixed(1)}%
            </p>
          </div>
          <TrendingUp className="w-9 h-9 text-red-400/50" />
        </div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-red-100 dark:bg-red-500/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-red-400 to-red-500 transition-all duration-700"
            style={{ width: `${Math.min(100, stats.bug_rate * 100)}%` }}
          />
        </div>
      </div>

      <div className="h-44 mb-4">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={pieData} cx="50%" cy="50%" innerRadius={48} outerRadius={70} paddingAngle={4} dataKey="value" stroke="none">
              {pieData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
        <div className="-mt-1 flex justify-center gap-4 text-xs text-[#5B6B74] dark:text-gray-400">
          {pieData.map((d) => (
            <span key={d.name} className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: d.color }} /> {d.name}
            </span>
          ))}
        </div>
      </div>

      {classData.length > 0 && (
        <div className="mt-8">
          <h3 className="tile-label mb-3">{t('stats.byClass')}</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={classData} layout="vertical" margin={{ left: 10, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} horizontal={false} />
                <XAxis type="number" stroke={axisStroke} fontSize={11} allowDecimals={false} />
                <YAxis type="category" dataKey="name" stroke={axisStroke} fontSize={11} width={95} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: isDark ? '#ffffff08' : '#0d948810' }} />
                <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                  {classData.map((_, i) => (
                    <Cell key={i} fill={CLASS_COLORS[i % CLASS_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
