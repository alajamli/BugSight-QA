import { RadialBarChart, RadialBar, ResponsiveContainer, PolarAngleAxis } from 'recharts';
import { Gauge } from 'lucide-react';
import { useTheme } from '../ThemeContext';
import { useI18n } from '../i18n';

export default function MetricsPanel({ metrics }) {
  const { theme } = useTheme();
  const { t } = useI18n();
  const trackColor = theme === 'dark' ? '#1E2733' : '#E3EBED';
  const m = metrics || { precision: 0, recall: 0, mAP50: 0, mAP50_95: 0 };

  const gauges = [
    { name: 'Precision', value: m.precision, fill: '#2DD4BF', hint: t('metrics.precisionHint') },
    { name: 'Recall', value: m.recall, fill: '#34D399', hint: t('metrics.recallHint') },
    { name: 'mAP50', value: m.mAP50, fill: '#FBBF24', hint: t('metrics.map50Hint') },
    { name: 'mAP50-95', value: m.mAP50_95, fill: '#F472B6', hint: t('metrics.map5095Hint') },
  ];

  return (
    <section className="panel panel-enter">
      <h2 className="panel-title">
        <span className="panel-icon"><Gauge className="h-4 w-4" /></span> {t('metrics.title')}
      </h2>
      <div className="grid grid-cols-2 gap-3">
        {gauges.map((g) => (
          <div key={g.name} className="tile text-center" title={g.hint}>
            <div className="relative h-28">
              <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart innerRadius="74%" outerRadius="100%" data={[g]} startAngle={90} endAngle={-270}>
                  <PolarAngleAxis type="number" domain={[0, 1]} tick={false} />
                  <RadialBar background={{ fill: trackColor }} dataKey="value" cornerRadius={10} fill={g.fill} />
                </RadialBarChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold tracking-tight text-[#0F1B24] dark:text-white">{(g.value * 100).toFixed(1)}%</span>
              </div>
            </div>
            <p className="tile-label mt-1">{g.name}</p>
            <p className="mt-1 text-[10.5px] leading-snug text-[#5B6B74] dark:text-gray-500">{g.hint}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
