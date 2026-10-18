import { AlertTriangle, CheckCircle2, Clock, Film } from 'lucide-react';
import { useI18n } from '../i18n';
import { classColor } from '../classColors';

const formatTime = (seconds = 0) => {
  const min = Math.floor(seconds / 60);
  const sec = Math.floor(seconds % 60);
  return `${min}:${sec.toString().padStart(2, '0')}`;
};

export default function VideoResultPanel({ result }) {
  const { t, tClass } = useI18n();
  if (!result) return null;
  const frames = result.frames || [];
  const buggyFrames = frames.filter((frame) => frame.has_bug);
  const distribution = Object.entries(result.class_distribution || {}).filter(([, count]) => count > 0).sort((a, b) => b[1] - a[1]);
  const maxCount = Math.max(...distribution.map(([, count]) => count), 1);
  const hasBugs = result.buggy_frames > 0;
  const verdictColor = hasBugs ? '#f87171' : '#34d399';
  const frameTitle = (frame) =>
    `${t('video.result.frame', { n: frame.frame })} | ${formatTime(frame.timestamp)} | ${t('video.result.bugs', { n: frame.num_detections })}`;

  const stats = [
    { label: t('video.result.framesAnalyzed'), value: result.analyzed_frames, color: '#38bdf8' },
    { label: t('video.result.framesBuggy'), value: result.buggy_frames, color: '#f87171' },
    { label: t('video.result.framesClean'), value: result.analyzed_frames - result.buggy_frames, color: '#34d399' },
    { label: t('video.result.bugRate'), value: `${(result.bug_rate * 100).toFixed(1)}%`, color: '#fbbf24' },
  ];

  return (
    <section className="panel panel-enter">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="panel-title !mb-0">
          <span className="panel-icon"><Film className="h-4 w-4" /></span> {t('video.result.title')}
        </h2>
        <span className="badge border-teal-500/30 bg-teal-500/10 text-[#0D9488] dark:text-[#5EEAD4]">{t('video.result.badge')}</span>
      </div>

      <div className="verdict mb-4" style={{ '--vc': verdictColor }}>
        <span className="verdict__icon">
          {hasBugs ? <AlertTriangle className="h-5 w-5" /> : <CheckCircle2 className="h-5 w-5" />}
        </span>
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide" style={{ color: verdictColor }}>
            {hasBugs ? t('video.result.bugsFound', { n: result.buggy_frames }) : t('video.result.noBugs')}
          </p>
          <p className="text-xs text-[#5B6B74] dark:text-gray-400">
            {t('video.result.analyzedOf', { analyzed: result.analyzed_frames, total: result.total_frames })}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="tile" style={{ borderTop: `2px solid ${s.color}` }}>
            <p className="tile-label">{s.label}</p>
            <p className="mt-1 text-xl font-bold tracking-tight" style={{ color: s.color }}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="tile mt-3 flex flex-wrap items-center justify-between gap-2 !py-2 text-xs text-[#5B6B74] dark:text-gray-400">
        <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> {t('video.result.duration', { time: formatTime(result.duration) })}</span>
        <span className="bs-mono">{result.fps} FPS</span>
        <span>{t('video.result.totalFrames', { n: result.total_frames })}</span>
      </div>

      <div className="mt-6">
        <h3 className="tile-label mb-2">{t('video.result.timeline')}</h3>
        <div className="flex gap-0.5 overflow-x-auto rounded-lg bg-[#F4F7F7] p-2 dark:bg-[#111826]">
          {frames.map((frame, index) => (
            <div
              key={index}
              className={`h-10 w-2.5 flex-shrink-0 rounded-sm transition-transform hover:scale-y-110 ${frame.has_bug ? 'bg-red-500' : 'bg-emerald-500/35'}`}
              title={frameTitle(frame)}
            />
          ))}
        </div>
        <div className="mt-2 flex gap-4 text-xs text-[#5B6B74] dark:text-gray-400">
          <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-red-500" />{t('video.result.legendBug')}</span>
          <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-emerald-500/35" />{t('video.result.legendClean')}</span>
        </div>
      </div>

      {distribution.length > 0 && (
        <div className="mt-6">
          <h3 className="tile-label mb-3">{t('video.result.types')}</h3>
          <ul className="space-y-3">
            {distribution.map(([name, count], i) => (
              <li key={name} className="cls-row" style={{ '--c': classColor(name), '--i': i }}>
                <div className="cls-row__head">
                  <span className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: classColor(name) }} />{tClass(name)}
                  </span>
                  <span className="bs-mono text-xs font-semibold" style={{ color: classColor(name) }}>{count}</span>
                </div>
                <div className="cls-row__track"><span className="cls-row__fill" style={{ width: `${(count / maxCount) * 100}%` }} /></div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {buggyFrames.length > 0 && (
        <div className="mt-6">
          <h3 className="tile-label mb-2">{t('video.result.details')}</h3>
          <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
            {buggyFrames.map((frame, index) => (
              <div key={index} className="tile !py-2.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="bs-mono font-medium text-[#0F1B24] dark:text-gray-200">{t('video.result.frame', { n: frame.frame })} · {formatTime(frame.timestamp)}</span>
                  <span className="text-red-500 dark:text-red-400">{t('video.result.bugs', { n: frame.num_detections })}</span>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {(frame.detections || []).map((detection, detectionIndex) => (
                    <span
                      key={detectionIndex}
                      className="rounded-full px-2 py-0.5 text-[11px] font-medium"
                      style={{ color: classColor(detection.class_name), background: `${classColor(detection.class_name)}1f` }}
                    >
                      {tClass(detection.class_name)} · {(detection.confidence * 100).toFixed(0)}%
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
