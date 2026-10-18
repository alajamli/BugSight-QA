import { useState, useRef } from 'react';
import { Upload, Image as ImageIcon, Loader2, ScanSearch } from 'lucide-react';
import { useI18n } from '../i18n';

export default function UploadPanel({ onPredict, loading }) {
  const { t } = useI18n();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [confidence, setConfidence] = useState(0.25);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const handleFile = (f) => {
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleFile(e.dataTransfer.files[0]);
  };

  return (
    <div className="panel panel-enter">
      <h2 className="panel-title">
        <span className="panel-icon"><ScanSearch className="w-4 h-4" /></span>
        {t('upload.title')}
      </h2>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`dropzone ${dragOver ? 'dropzone--active' : ''}`}
      >
        {preview ? (
          <div className="relative inline-block">
            <img src={preview} alt={t('upload.previewAlt')} className="max-h-48 mx-auto rounded-lg shadow-lg ring-1 ring-black/10 dark:ring-white/10" />
            <p className="bs-mono mt-3 text-[11px] text-[#5B6B74] dark:text-gray-500 truncate max-w-[16rem]">
              {file?.name} · {t('upload.clickReplace')}
            </p>
          </div>
        ) : (
          <>
            <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full bg-teal-500/10 text-[#0D9488] dark:bg-teal-300/10 dark:text-[#5EEAD4]">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="text-sm font-medium text-[#0F1B24] dark:text-gray-200">{t('upload.drop')}</p>
            <p className="text-xs text-[#5B6B74] dark:text-gray-500 mt-1">{t('upload.browse')}</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => handleFile(e.target.files[0])}
        />
      </div>

      <div className="mt-5">
        <label className="flex items-center justify-between">
          <span className="tile-label">{t('common.confidence')}</span>
          <span className="bs-mono rounded-md bg-teal-500/10 px-2 py-0.5 text-xs font-semibold text-[#0D9488] dark:bg-teal-300/10 dark:text-[#5EEAD4]">
            {confidence.toFixed(2)}
          </span>
        </label>
        <input
          type="range"
          min="0.05"
          max="0.95"
          step="0.05"
          value={confidence}
          onChange={(e) => setConfidence(parseFloat(e.target.value))}
          className="slider mt-3"
        />
      </div>

      <button
        onClick={() => file && onPredict(file, confidence)}
        disabled={!file || loading}
        className="btn-primary mt-5"
      >
        {loading ? (
          <><Loader2 className="w-4 h-4 animate-spin" /> {t('upload.analyzing')}</>
        ) : (
          <><Upload className="w-4 h-4" /> {t('upload.detect')}</>
        )}
      </button>
    </div>
  );
}
