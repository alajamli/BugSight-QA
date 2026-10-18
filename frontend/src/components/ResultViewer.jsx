import { useEffect, useRef } from 'react';
import { AlertTriangle, CheckCircle, Bug } from 'lucide-react';
import { useI18n } from '../i18n';

export default function ResultViewer({ result, imageUrl }) {
  const { t, tClass } = useI18n();
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!imageUrl || !canvasRef.current) return;
    const img = new Image();
    img.onload = () => {
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);

      if (result?.detections) {
        result.detections.forEach((det) => {
          const [x1, y1, x2, y2] = det.bbox_xyxy;
          ctx.strokeStyle = '#ef4444';
          ctx.lineWidth = 3;
          ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
          const label = `${tClass(det.class_name)} ${(det.confidence * 100).toFixed(1)}%`;
          ctx.font = 'bold 16px sans-serif';
          const tw = ctx.measureText(label).width;
          ctx.fillStyle = '#ef4444';
          ctx.fillRect(x1, y1 - 24, tw + 12, 24);
          ctx.fillStyle = '#fff';
          ctx.fillText(label, x1 + 6, y1 - 6);
        });
      }
    };
    img.src = imageUrl;
  }, [imageUrl, result, tClass]);

  if (!result) {
    return (
      <div className="panel panel-enter min-h-[26rem] flex items-center justify-center">
        <div className="text-center">
          <div className="bs-reticle mx-auto mb-4 grid h-20 w-20 place-items-center rounded-xl border border-[#DCE6E8] bg-[#F4F7F7] dark:border-[#243040] dark:bg-[#111826]">
            <div className="bs-scan" />
            <Bug className="w-8 h-8 text-[#0D9488] dark:text-[#5EEAD4] opacity-70" />
          </div>
          <p className="text-sm font-medium text-[#0F1B24] dark:text-gray-200">{t('result.awaiting')}</p>
          <p className="mt-1 text-xs text-[#5B6B74] dark:text-gray-500">{t('result.awaitingHint')}</p>
        </div>
      </div>
    );
  }

  const classColors = ['bg-red-400', 'bg-amber-400', 'bg-violet-400', 'bg-blue-400', 'bg-emerald-400', 'bg-pink-400'];

  return (
    <div className="panel panel-enter">
      <div className="flex items-center justify-between mb-5">
        <h2 className="panel-title !mb-0">
          <span className="panel-icon"><Bug className="w-4 h-4" /></span> {t('result.title')}
        </h2>
        {result.has_bug ? (
          <span className="badge badge-bug">
            <AlertTriangle className="w-3.5 h-3.5" /> {t('result.bug')}
          </span>
        ) : (
          <span className="badge badge-ok">
            <CheckCircle className="w-3.5 h-3.5" /> {t('result.noBug')}
          </span>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-[#DCE6E8] bg-[#F4F7F7] dark:border-[#1E2733] dark:bg-black/40 flex justify-center">
        <canvas ref={canvasRef} className="max-w-full h-auto" />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        <div className="tile">
          <p className="tile-label">{t('result.detections')}</p>
          <p className="tile-value">{result.num_detections}</p>
        </div>
        <div className="tile">
          <p className="tile-label">{t('result.image')}</p>
          <p className="tile-value">{result.image_width}×{result.image_height}</p>
        </div>
        <div className="tile">
          <p className="tile-label">{t('result.file')}</p>
          <p className="tile-value truncate bs-mono">{result.filename}</p>
        </div>
      </div>

      {result.detections.length > 0 && (
        <div className="mt-5">
          <h3 className="tile-label mb-2">{t('result.objects')}</h3>
          <div className="space-y-2">
            {result.detections.map((d, i) => (
              <div key={i} className="tile flex items-center justify-between !py-2.5 text-sm">
                <span className="flex items-center gap-2.5 text-[#0F1B24] dark:text-gray-200">
                  <span className={`h-2 w-2 rounded-full ${classColors[d.class_id % classColors.length]}`} />
                  {tClass(d.class_name)}
                </span>
                <span className="flex items-center gap-3">
                  <span className="hidden sm:block h-1.5 w-20 overflow-hidden rounded-full bg-[#DCE6E8] dark:bg-[#1E2733]">
                    <span className="block h-full rounded-full bg-[#0D9488] dark:bg-[#5EEAD4]" style={{ width: `${d.confidence * 100}%` }} />
                  </span>
                  <span className="bs-mono text-xs text-[#5B6B74] dark:text-gray-400">{(d.confidence * 100).toFixed(1)}%</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}