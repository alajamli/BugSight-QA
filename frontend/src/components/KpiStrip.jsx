import { Activity, AlertTriangle, CheckCircle2, Crosshair, Percent } from 'lucide-react';
import CountUp from './CountUp';
import { useI18n } from '../i18n';

/** Headline numbers for the session, always visible at the top of the dashboard. */
export default function KpiStrip({ stats, metrics }) {
  const { t } = useI18n();
  const total = stats?.total_analyses ?? 0;
  const bugs = stats?.bug_detected ?? 0;
  const clean = stats?.clean ?? 0;
  const rate = (stats?.bug_rate ?? 0) * 100;
  const share = (n) => (total ? Math.round((n / total) * 100) : 0);
  const map50 = (metrics?.mAP50 ?? 0) * 100;

  const cards = [
    { key: 'total', color: '#38bdf8', Icon: Activity, value: total, hint: t('kpi.totalHint') },
    { key: 'bugs', color: '#f87171', Icon: AlertTriangle, value: bugs, hint: t('kpi.bugsHint', { pct: share(bugs) }), bar: share(bugs) },
    { key: 'clean', color: '#34d399', Icon: CheckCircle2, value: clean, hint: t('kpi.cleanHint', { pct: share(clean) }), bar: share(clean) },
    { key: 'rate', color: '#fbbf24', Icon: Percent, value: rate, decimals: 1, suffix: '%', hint: t('kpi.rateHint'), bar: Math.min(100, rate) },
    { key: 'model', color: '#a78bfa', Icon: Crosshair, value: map50, decimals: 1, suffix: '%', hint: t('kpi.modelHint'), bar: Math.min(100, map50) },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
      {cards.map(({ key, color, Icon, value, decimals, suffix, hint, bar }, i) => (
        <div key={key} className={`kpi ${key === 'total' ? 'col-span-2 md:col-span-1' : ''}`} style={{ '--k': color, '--i': i }}>
          <div className="kpi__head">
            <span className="kpi__label">{t(`kpi.${key}`)}</span>
            <span className="kpi__icon"><Icon className="h-4 w-4" /></span>
          </div>
          <p className="kpi__value">
            <CountUp value={value} decimals={decimals} suffix={suffix} />
          </p>
          <div>
            {bar !== undefined && (
              <div className="kpi__bar mb-1.5" aria-hidden="true">
                <span style={{ width: `${bar}%` }} />
              </div>
            )}
            <p className="kpi__hint">{hint}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
