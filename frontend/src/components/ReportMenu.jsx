import { useEffect, useRef, useState } from 'react';
import { ChevronDown, FileDown, FileStack, Film, Image as ImageIcon } from 'lucide-react';
import { api } from '../api';
import { useI18n } from '../i18n';

const VIDEO_LIMIT = 8;

/**
 * PDF report dropdown: image report, video report (pick one of the user's
 * analysed videos) or the full report. Images and videos are reported
 * separately by the API, so each choice maps to /api/report?type=...
 */
export default function ReportMenu({ loading, onDownload, refreshKey }) {
  const { t, formatShort } = useI18n();
  const [open, setOpen] = useState(false);
  const [videos, setVideos] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => !ref.current?.contains(e.target) && setOpen(false);
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  // Fetch the video list when the menu opens (and again after a new analysis).
  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    setVideos(null);
    api
      .history({ type: 'video', limit: VIDEO_LIMIT })
      .then((data) => !cancelled && setVideos(data.predictions || []))
      .catch(() => !cancelled && setVideos([]));
    return () => {
      cancelled = true;
    };
  }, [open, refreshKey]);

  const choose = (options) => {
    setOpen(false);
    onDownload(options);
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={loading}
        aria-haspopup="menu"
        aria-expanded={open}
        className="btn-primary btn-primary--auto whitespace-nowrap !rounded-lg !px-3.5 !py-2"
      >
        {loading ? (
          <span className="bs-mono">{t('app.generating')}</span>
        ) : (
          <>
            <FileDown className="w-4 h-4" /> <span className="hidden sm:inline">{t('app.reportPdf')}</span>
            <ChevronDown className={`h-3.5 w-3.5 opacity-70 transition-transform ${open ? 'rotate-180' : ''}`} />
          </>
        )}
      </button>

      {open && (
        <div className="menu !w-72" role="menu">
          <button type="button" role="menuitem" className="menu__item" onClick={() => choose({ type: 'image' })}>
            <ImageIcon className="h-4 w-4 text-[#0D9488] dark:text-[#5EEAD4]" />
            <span>
              <span className="block font-semibold">{t('report.images')}</span>
              <span className="block text-[11px] text-[#5B6B74] dark:text-gray-500">{t('report.imagesHint')}</span>
            </span>
          </button>
          <button
            type="button"
            role="menuitem"
            className="menu__item"
            onClick={() => choose({ type: 'all', includeVideo: true })}
          >
            <FileStack className="h-4 w-4 text-[#0D9488] dark:text-[#5EEAD4]" />
            <span>
              <span className="block font-semibold">{t('report.full')}</span>
              <span className="block text-[11px] text-[#5B6B74] dark:text-gray-500">{t('report.fullHint')}</span>
            </span>
          </button>

          <p className="bs-mono border-t border-[#E3EBED] px-4 pb-1 pt-3 text-[10px] uppercase tracking-wider text-[#5B6B74] dark:border-[#1E2733] dark:text-gray-500">
            {t('report.videoSection')}
          </p>
          {videos === null && <p className="px-4 py-2 text-xs text-[#5B6B74] dark:text-gray-500">{t('report.loadingVideos')}</p>}
          {videos?.length === 0 && <p className="px-4 py-2 text-xs text-[#5B6B74] dark:text-gray-500">{t('report.noVideos')}</p>}
          <div className="max-h-56 overflow-y-auto pb-1">
            {videos?.map((video) => (
              <button
                key={video.id}
                type="button"
                role="menuitem"
                className="menu__item"
                title={video.filename}
                onClick={() => choose({ type: 'video', videoId: video.id })}
              >
                <Film className="h-4 w-4 shrink-0 text-violet-500" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{video.filename}</span>
                  <span className="bs-mono block text-[10px] text-[#5B6B74] dark:text-gray-500">{formatShort(video.timestamp)}</span>
                </span>
                <span
                  className={`h-2 w-2 shrink-0 rounded-full ${video.has_bug ? 'bg-red-500' : 'bg-emerald-500'}`}
                  aria-label={video.has_bug ? t('report.withBugs') : t('report.clean')}
                />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
