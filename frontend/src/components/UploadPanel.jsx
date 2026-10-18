import { useEffect, useRef, useState } from 'react';
import { Upload, Image as ImageIcon, Loader2, X } from 'lucide-react';
import { useI18n } from '../i18n';
import ConfidenceControl from './ConfidenceControl';

const formatSize = (bytes) =>
  bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;

/** Screenshot form: dropzone, selected-file chip, confidence and submit. Rendered inside AnalyzePanel. */
export default function UploadPanel({ onPredict, loading }) {
  const { t } = useI18n();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [confidence, setConfidence] = useState(0.25);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  // Release the object URL when the file changes or the form unmounts.
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  const handleFile = (f) => {
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const clearFile = () => {
    setFile(null);
    setPreview(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const openPicker = () => !loading && inputRef.current?.click();

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleFile(e.dataTransfer.files[0]);
  };

  return (
    <div className="space-y-5">
      {file ? (
        <div className="file-chip">
          <span className="file-chip__thumb">
            {preview ? <img src={preview} alt={t('upload.previewAlt')} /> : <ImageIcon className="h-5 w-5" />}
          </span>
          <div className="min-w-0 flex-1">
            <p className="file-chip__name" title={file.name}>{file.name}</p>
            <p className="file-chip__meta">{formatSize(file.size)} · {t('upload.ready')}</p>
          </div>
          <button type="button" className="icon-btn" onClick={clearFile} disabled={loading} aria-label={t('upload.remove')} title={t('upload.remove')}>
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <div
          role="button"
          tabIndex={0}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={openPicker}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), openPicker())}
          className={`dropzone ${dragOver ? 'dropzone--active' : ''}`}
        >
          <div className="dropzone__icon"><ImageIcon className="h-6 w-6" /></div>
          <p className="text-sm font-semibold text-[#0F1B24] dark:text-gray-100">{t('upload.drop')}</p>
          <p className="mt-1 text-xs text-[#5B6B74] dark:text-gray-500">{t('upload.browse')}</p>
        </div>
      )}
      <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={(e) => handleFile(e.target.files[0])} />

      <ConfidenceControl id="image-confidence" value={confidence} onChange={setConfidence} disabled={loading} />

      <button onClick={() => file && onPredict(file, confidence)} disabled={!file || loading} className="btn-primary">
        {loading ? (
          <><Loader2 className="h-4 w-4 animate-spin" /> {t('upload.analyzing')}</>
        ) : (
          <><Upload className="h-4 w-4" /> {t('upload.detect')}</>
        )}
      </button>
    </div>
  );
}
