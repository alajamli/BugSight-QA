import { AlertTriangle, CheckCircle, Clock, Film } from 'lucide-react';
import { useI18n } from '../i18n';

const formatTime = (seconds = 0) => {
  const min = Math.floor(seconds / 60);
  const sec = Math.floor(seconds % 60);
  return `${min}:${sec.toString().padStart(2, '0')}`;
};

const classColors = ['bg-red-500', 'bg-amber-500', 'bg-purple-500', 'bg-blue-500', 'bg-green-500', 'bg-pink-500'];

export default function VideoResultPanel({ result }) {
  const { t, tClass } = useI18n();
  if (!result) return null;
  const buggyFrames = (result.frames || []).filter((frame) => frame.has_bug);
  const distribution = Object.entries(result.class_distribution || {}).filter(([, count]) => count > 0).sort((a, b) => b[1] - a[1]);
  const maxCount = Math.max(...distribution.map(([, count]) => count), 1);
  const hasBugs = result.buggy_frames > 0;
  const frameTitle = (frame) =>
    `${t('video.result.frame', { n: frame.frame })} | ${formatTime(frame.timestamp)} | ${t('video.result.bugs', { n: frame.num_detections })}`;

  return (
    <div className="panel panel-enter">
      <div className="flex items-center justify-between mb-4">
        <h2 className="panel-title !mb-0">
          <span className="panel-icon"><Film className="w-4 h-4" /></span> {t('video.result.title')}
        </h2>
        <span className="text-xs px-2 py-1 rounded-full bg-teal-500/10 text-[#0D9488] dark:bg-teal-300/10 dark:text-[#5EEAD4]">{t('video.result.badge')}</span>
      </div>

      <div className={`rounded-lg p-4 border ${hasBugs ? 'bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-700' : 'bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-700'}`}>
        <div className="flex items-center gap-2">
          {hasBugs ? <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400" /> : <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />}
          <div>
            <p className={`font-semibold ${hasBugs ? 'text-red-700 dark:text-red-300' : 'text-green-700 dark:text-green-300'}`}>
              {hasBugs ? t('video.result.bugsFound', { n: result.buggy_frames }) : t('video.result.noBugs')}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">{t('video.result.analyzedOf', { analyzed: result.analyzed_frames, total: result.total_frames })}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-4">
        <div className="bg-gray-100 dark:bg-gray-800 rounded-lg px-2 py-2 text-center"><p className="text-lg font-bold text-gray-900 dark:text-white">{result.analyzed_frames}</p><p className="text-xs text-gray-500">{t('video.result.framesAnalyzed')}</p></div>
        <div className="bg-gray-100 dark:bg-gray-800 rounded-lg px-2 py-2 text-center"><p className="text-lg font-bold text-red-600 dark:text-red-400">{result.buggy_frames}</p><p className="text-xs text-gray-500">{t('video.result.framesBuggy')}</p></div>
        <div className="bg-gray-100 dark:bg-gray-800 rounded-lg px-2 py-2 text-center"><p className="text-lg font-bold text-green-600 dark:text-green-400">{result.analyzed_frames - result.buggy_frames}</p><p className="text-xs text-gray-500">{t('video.result.framesClean')}</p></div>
        <div className="bg-gray-100 dark:bg-gray-800 rounded-lg px-2 py-2 text-center"><p className="text-lg font-bold text-amber-600 dark:text-amber-400">{(result.bug_rate * 100).toFixed(1)}%</p><p className="text-xs text-gray-500">{t('video.result.bugRate')}</p></div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500 dark:text-gray-400 bg-gray-100/70 dark:bg-gray-800/50 rounded-lg px-3 py-2 mt-4">
        <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {t('video.result.duration', { time: formatTime(result.duration) })}</span>
        <span>{result.fps} FPS</span><span>{t('video.result.totalFrames', { n: result.total_frames })}</span>
      </div>

      <div className="mt-5">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('video.result.timeline')}</h3>
        <div className="flex gap-0.5 overflow-x-auto pb-2">
          {(result.frames || []).map((frame, index) => <div key={index} className={`flex-shrink-0 w-3 h-10 rounded-sm ${frame.has_bug ? 'bg-red-500' : 'bg-green-500/40'}`} title={frameTitle(frame)} />)}
        </div>
        <div className="flex gap-4 text-xs text-gray-500"><span><span className="inline-block w-3 h-3 bg-red-500 rounded-sm mr-1 align-middle" />{t('video.result.legendBug')}</span><span><span className="inline-block w-3 h-3 bg-green-500/40 rounded-sm mr-1 align-middle" />{t('video.result.legendClean')}</span></div>
      </div>

      {distribution.length > 0 && <div className="mt-5"><h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('video.result.types')}</h3><div className="space-y-1.5">{distribution.map(([name, count], index) => <div key={name} className="flex items-center justify-between bg-gray-100 dark:bg-gray-800 rounded-lg px-3 py-2 text-sm"><span className="flex items-center gap-2 text-gray-700 dark:text-gray-200"><span className={`w-2.5 h-2.5 rounded-full ${classColors[index % classColors.length]}`} />{tClass(name)}</span><div className="flex items-center gap-2"><div className="w-20 bg-gray-200 dark:bg-gray-700 rounded-full h-1.5"><div className={`h-1.5 rounded-full ${classColors[index % classColors.length]}`} style={{ width: `${(count / maxCount) * 100}%` }} /></div><span className="font-mono text-gray-500 w-6 text-right">{count}</span></div></div>)}</div></div>}

      {buggyFrames.length > 0 && <div className="mt-5"><h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('video.result.details')}</h3><div className="max-h-56 overflow-y-auto space-y-1.5">{buggyFrames.map((frame, index) => <div key={index} className="bg-gray-100 dark:bg-gray-800 rounded-lg px-3 py-2 text-xs"><div className="flex items-center justify-between"><span className="font-medium text-gray-700 dark:text-gray-300">{t('video.result.frame', { n: frame.frame })} · {formatTime(frame.timestamp)}</span><span className="text-red-600 dark:text-red-400">{t('video.result.bugs', { n: frame.num_detections })}</span></div><div className="flex flex-wrap gap-1 mt-1">{(frame.detections || []).map((detection, detectionIndex) => <span key={detectionIndex} className="px-2 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded">{tClass(detection.class_name)} ({(detection.confidence * 100).toFixed(0)}%)</span>)}</div></div>)}</div></div>}
    </div>
  );
}
