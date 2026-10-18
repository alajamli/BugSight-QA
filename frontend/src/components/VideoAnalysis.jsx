import { useRef, useState } from 'react';
import axios from 'axios';
import { Loader2, Film, Play, X } from 'lucide-react';
import { api } from '../api';
import { useI18n } from '../i18n';
import { useToast } from '../ToastContext';
import VideoResultPanel from './VideoResultPanel';
import ConfidenceControl from './ConfidenceControl';

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
  const openPicker = () => !busy && document.getElementById('video-input')?.click();

  return (
    <div className="space-y-5">
      {file ? (
        <div className="file-chip">
          <span className="file-chip__thumb"><Film className="h-5 w-5" /></span>
          <div className="min-w-0 flex-1">
            <p className="file-chip__name" title={file.name}>{file.name}</p>
            <p className="file-chip__meta">{(file.size / 1024 / 1024).toFixed(1)} MB · {t('upload.ready')}</p>
          </div>
          <button type="button" className="icon-btn" onClick={() => setFile(null)} disabled={busy} aria-label={t('upload.remove')} title={t('upload.remove')}>
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <div
          role="button"
          tabIndex={0}
          onClick={openPicker}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), openPicker())}
          className={`dropzone ${busy ? 'dropzone--busy' : ''}`}
        >
          <div className="dropzone__icon"><Film className="h-6 w-6" /></div>
          <p className="text-sm font-semibold text-[#0F1B24] dark:text-gray-100">{t('video.upload')}</p>
          <p className="mt-1 text-xs text-[#5B6B74] dark:text-gray-500">{t('video.formats')}</p>
        </div>
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

      <ConfidenceControl id="video-confidence" value={confidence} onChange={setConfidence} disabled={busy} />

      <div>
        <span id="video-frames-label" className="form-label">{t('video.frames')}</span>
        <div className="seg seg--full mt-2" role="group" aria-labelledby="video-frames-label">
          {FRAME_OPTIONS.map((n) => (
            <button
              key={n}
              type="button"
              className="seg__btn !px-2"
              aria-pressed={maxFrames === n}
              disabled={busy}
              onClick={() => setMaxFrames(n)}
              title={t('video.framesOption', { n })}
            >
              {n}
            </button>
          ))}
        </div>
        <p className="form-help">{t('video.framesHint')}</p>
      </div>

      {busy && (
        <div role="status" aria-live="polite">
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

      <div className="space-y-2">
        <button onClick={handleAnalyze} disabled={!file || busy} className="btn-primary">
          {busy ? (
            <><Loader2 className="h-4 w-4 animate-spin" /> {phase === 'uploading' ? t('video.uploading') : t('video.analyzing')}</>
          ) : (
            <><Play className="h-4 w-4" /> {t('video.analyze')}</>
          )}
        </button>
        {busy && (
          <button type="button" onClick={handleCancel} className="btn-secondary">
            <X className="h-4 w-4" /> {t('video.cancel')}
          </button>
        )}
      </div>

      {result && !hideResult && (
        <div className="pt-1">
          <VideoResultPanel result={result} />
        </div>
      )}
    </div>
  );
}
