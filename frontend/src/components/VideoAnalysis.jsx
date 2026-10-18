import { useRef, useState } from 'react';
import axios from 'axios';
import { Video, Loader2, Film, Play, X } from 'lucide-react';
import { api } from '../api';
import { useI18n } from '../i18n';
import { useToast } from '../ToastContext';
import VideoResultPanel from './VideoResultPanel';

// Keep in sync with the backend (ALLOWED_VIDEO_EXT, BUGSIGHT_MAX_UPLOAD_MB).
const VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv', '.webm'];
const MAX_VIDEO_MB = 200;
const FRAME_OPTIONS = [30, 60, 120, 300];

export default function VideoAnalysis({ onVideoReport, hideResult = false }) {
  const { t } = useI18n();
  const toast = useToast();
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [confidence, setConfidence] = useState(0.25);
  const [maxFrames, setMaxFrames] = useState(60);
  // idle -> uploading (with a percentage) -> analyzing (server is working)
  const [phase, setPhase] = useState('idle');
  const [uploadPct, setUploadPct] = useState(0);
  const abortRef = useRef(null);

  const busy = phase !== 'idle';

  const handleFile = (f) => {
    if (!f) return;
    const name = f.name.toLowerCase();
    if (!VIDEO_EXTENSIONS.some((ext) => name.endsWith(ext))) {
      toast.error({ key: 'video.badType', vars: { types: VIDEO_EXTENSIONS.join(', ') } });
      return;
    }
    if (f.size > MAX_VIDEO_MB * 1024 * 1024) {
      toast.error({ key: 'video.tooBig', vars: { n: MAX_VIDEO_MB } });
      return;
    }
    setFile(f);
    setResult(null);
  };

  const handleAnalyze = async () => {
    if (!file || busy) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setPhase('uploading');
    setUploadPct(0);
    try {
      const res = await api.predictVideo(file, confidence, maxFrames, {
        signal: controller.signal,
        onUploadProgress: (event) => {
          if (!event.total) return;
          const pct = Math.round((event.loaded / event.total) * 100);
          setUploadPct(pct);
          if (pct >= 100) setPhase('analyzing');
        },
      });
      setResult(res);
      if (onVideoReport) onVideoReport(res);
    } catch (e) {
      if (axios.isCancel(e)) toast.info({ key: 'video.cancelled' });
      else toast.error(e.response?.data?.error || { key: 'video.failed' });
    } finally {
      abortRef.current = null;
      setPhase('idle');
    }
  };

  const handleCancel = () => abortRef.current?.abort();

  return (
    <div className="panel panel-enter">
      <h2 className="panel-title">
        <span className="panel-icon"><Video className="w-4 h-4" /></span> {t('video.title')}
      </h2>

      {/* Upload zone */}
      <div
        onClick={() => !busy && document.getElementById('video-input')?.click()}
        className={`border-2 border-dashed border-[#C9D8DB] dark:border-[#2A3748] rounded-xl p-6 text-center transition-all ${
          busy
            ? 'opacity-60 cursor-not-allowed'
            : 'cursor-pointer hover:border-[#0D9488] dark:hover:border-[#5EEAD4] hover:bg-gray-50 dark:hover:bg-gray-800/50'
        }`}
      >
        {file ? (
          <div className="flex items-center justify-center gap-2 text-gray-600 dark:text-gray-300">
            <Film className="w-5 h-5" />
            <p className="text-sm truncate max-w-xs">{file.name}</p>
            <span className="text-gray-400 dark:text-gray-500 text-xs">({(file.size / 1024 / 1024).toFixed(1)} MB)</span>
          </div>
        ) : (
          <>
            <Film className="w-10 h-10 text-gray-400 dark:text-gray-500 mx-auto mb-2" />
            <p className="text-gray-500 dark:text-gray-400 text-sm">{t('video.upload')}</p>
            <p className="text-gray-400 dark:text-gray-600 text-xs mt-1">{t('video.formats')}</p>
          </>
        )}
        <input
          id="video-input"
          type="file"
          accept="video/*"
          className="hidden"
          disabled={busy}
          onChange={(e) => {
            handleFile(e.target.files[0]);
            e.target.value = ''; // allow re-selecting the same file after a rejection
          }}
        />
      </div>

      {/* Confidence slider */}
      <div className="mt-4">
        <label className="text-sm font-medium text-gray-600 dark:text-gray-300 flex items-center justify-between">
          <span>{t('common.confidence')}</span>
          <span className="text-[#0D9488] dark:text-[#5EEAD4] font-mono">{confidence.toFixed(2)}</span>
        </label>
        <input
          type="range"
          min="0.05"
          max="0.95"
          step="0.05"
          value={confidence}
          disabled={busy}
          onChange={(e) => setConfidence(parseFloat(e.target.value))}
          className="w-full mt-2 accent-[#0D9488] dark:accent-[#5EEAD4]"
        />
      </div>

      {/* Sampling depth */}
      <div className="mt-4 flex items-center justify-between gap-3">
        <label htmlFor="video-frames" className="text-sm font-medium text-gray-600 dark:text-gray-300">
          {t('video.frames')}
        </label>
        <select
          id="video-frames"
          className="field"
          value={maxFrames}
          disabled={busy}
          onChange={(e) => setMaxFrames(Number(e.target.value))}
        >
          {FRAME_OPTIONS.map((n) => (
            <option key={n} value={n}>{t('video.framesOption', { n })}</option>
          ))}
        </select>
      </div>
      <p className="mt-1 text-[11px] text-gray-400 dark:text-gray-500">{t('video.framesHint')}</p>

      {/* Progress */}
      {busy && (
        <div className="mt-4" role="status" aria-live="polite">
          <div className="mb-1.5 flex items-center justify-between text-xs text-[#5B6B74] dark:text-gray-400">
            <span>{phase === 'uploading' ? t('video.uploading') : t('video.analyzing')}</span>
            {phase === 'uploading' && <span className="bs-mono">{uploadPct}%</span>}
          </div>
          <div className="progress">
            {phase === 'uploading' ? (
              <div className="progress__bar" style={{ width: `${uploadPct}%` }} />
            ) : (
              <div className="progress__bar progress__bar--indeterminate" />
            )}
          </div>
        </div>
      )}

      <div className="mt-4 space-y-2">
        <button onClick={handleAnalyze} disabled={!file || busy} className="btn-primary">
          {busy ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> {phase === 'uploading' ? t('video.uploading') : t('video.analyzing')}</>
          ) : (
            <><Play className="w-4 h-4" /> {t('video.analyze')}</>
          )}
        </button>
        {busy && (
          <button type="button" onClick={handleCancel} className="btn-secondary">
            <X className="w-4 h-4" /> {t('video.cancel')}
          </button>
        )}
      </div>

      {result && !hideResult && (
        <div className="mt-6">
          <VideoResultPanel result={result} />
        </div>
      )}
    </div>
  );
}
