import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Bug, ScanSearch } from 'lucide-react';
import { useI18n } from '../i18n';
import { classColor } from '../classColors';

const REVEAL_MS = 700;
const easeOut = (x) => 1 - (1 - x) ** 3;

function hexToRgba(hex, alpha) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

// Blips on the radar: [left %, top %, delay s]
const BLIPS = [
  [68, 28, 0.5],
  [30, 62, 1.6],
  [58, 74, 2.5],
  [24, 30, 3.1],
];

function Radar({ title, hint }) {
  return (
    <div className="text-center">
      <div className="radar" aria-hidden="true">
        <div className="radar__sweep" />
        {BLIPS.map(([left, top, delay]) => (
          <span key={`${left}-${top}`} className="radar__blip" style={{ left: `${left}%`, top: `${top}%`, animationDelay: `${delay}s` }} />
        ))}
        <div className="radar__core">
          <Bug className="h-6 w-6 text-[#0D9488] dark:text-[#5EEAD4]" />
        </div>
      </div>
      <p className="mt-6 text-sm font-semibold text-[#0F1B24] dark:text-gray-100">{title}</p>
      <p className="mt-1 text-xs text-[#5B6B74] dark:text-gray-500">{hint}</p>
    </div>
  );
}

export default function ResultViewer({ result, imageUrl, loading = false }) {
  const { t, tClass } = useI18n();
  const canvasRef = useRef(null);
  const imageRef = useRef(null);
  const hoverRef = useRef(null);
  const settledRef = useRef(false);
  const [hover, setHover] = useState(null);

  // Draws the screenshot plus neon corner-bracket boxes. `progress` (0..1) drives
  // the reveal animation; `active` dims every box except the hovered one.
  const draw = useCallback(
    (progress, active) => {
      const canvas = canvasRef.current;
      const img = imageRef.current;
      if (!canvas || !img) return;
      const ctx = canvas.getContext('2d');
      const W = img.naturalWidth;
      const H = img.naturalHeight;
      ctx.clearRect(0, 0, W, H);
      ctx.drawImage(img, 0, 0, W, H);

      const unit = Math.max(2, W / 360);
      const fontSize = Math.max(13, Math.round(W / 58));
      const detections = result?.detections || [];

      detections.forEach((det, index) => {
        const [x1, y1, x2, y2] = det.bbox_xyxy;
        const color = classColor(det.class_name);
        const stagger = Math.min(1, Math.max(0, progress * 1.5 - index * 0.12));
        const e = easeOut(stagger);
        if (e <= 0) return;

        const dim = active !== null && active !== index;
        const inset = (1 - e) * unit * 8;
        const x = x1 + inset;
        const y = y1 + inset;
        const w = x2 - x1 - inset * 2;
        const h = y2 - y1 - inset * 2;

        ctx.save();
        ctx.globalAlpha = e * (dim ? 0.3 : 1);
        ctx.fillStyle = hexToRgba(color, active === index ? 0.26 : 0.12);
        ctx.fillRect(x, y, w, h);

        ctx.lineWidth = Math.max(1, unit * 0.45);
        ctx.strokeStyle = hexToRgba(color, 0.7);
        ctx.strokeRect(x, y, w, h);

        // glowing corner brackets
        const len = Math.min(Math.max(unit * 5, Math.min(w, h) * 0.24), unit * 16);
        ctx.shadowColor = color;
        ctx.shadowBlur = unit * 5;
        ctx.strokeStyle = color;
        ctx.lineWidth = unit * 1.15;
        ctx.lineCap = 'round';
        ctx.beginPath();
        [
          [x, y, 1, 1],
          [x + w, y, -1, 1],
          [x, y + h, 1, -1],
          [x + w, y + h, -1, -1],
        ].forEach(([cx, cy, dx, dy]) => {
          ctx.moveTo(cx, cy + dy * len);
          ctx.lineTo(cx, cy);
          ctx.lineTo(cx + dx * len, cy);
        });
        ctx.stroke();

        // label pill
        ctx.shadowBlur = 0;
        ctx.font = `600 ${fontSize}px Inter, system-ui, sans-serif`;
        const label = `${tClass(det.class_name)}  ${(det.confidence * 100).toFixed(0)}%`;
        const padX = fontSize * 0.6;
        const pillH = fontSize * 1.7;
        const pillW = ctx.measureText(label).width + padX * 2;
        const pillX = Math.min(Math.max(0, x), Math.max(0, W - pillW));
        const pillY = y - pillH - unit * 1.5 >= 0 ? y - pillH - unit * 1.5 : y + unit * 1.5;
        ctx.fillStyle = color;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(pillX, pillY, pillW, pillH, pillH / 2);
        else ctx.rect(pillX, pillY, pillW, pillH);
        ctx.fill();
        ctx.fillStyle = '#0b1016';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, pillX + padX, pillY + pillH / 2 + 1);
        ctx.restore();
      });
    },
    [result, tClass],
  );

  // Load the image, then play the reveal animation.
  useEffect(() => {
    if (loading || !result || !imageUrl) return undefined;
    let frame;
    let cancelled = false;
    settledRef.current = false;
    const img = new Image();
    img.onload = () => {
      if (cancelled || !canvasRef.current) return;
      canvasRef.current.width = img.naturalWidth;
      canvasRef.current.height = img.naturalHeight;
      imageRef.current = img;
      const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      const start = performance.now();
      const step = (now) => {
        const progress = reduced ? 1 : Math.min(1, (now - start) / REVEAL_MS);
        draw(progress, hoverRef.current);
        if (progress < 1) frame = requestAnimationFrame(step);
        else settledRef.current = true;
      };
      frame = requestAnimationFrame(step);
    };
    img.src = imageUrl;
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
    };
  }, [imageUrl, result, loading, draw]);

  // Re-draw (no animation) when a list row is hovered.
  useEffect(() => {
    hoverRef.current = hover;
    if (settledRef.current) draw(1, hover);
  }, [hover, draw]);

  if (loading) {
    return (
      <div className="panel panel-enter">
        <h2 className="panel-title">
          <span className="panel-icon"><ScanSearch className="h-4 w-4" /></span> {t('result.scanning')}
        </h2>
        <div className="scan-frame flex justify-center bg-black/30">
          {imageUrl && <img src={imageUrl} alt="" className="block max-h-[28rem] w-full object-contain opacity-90" />}
          <div className="scan-frame__grid" />
          <div className="scan-frame__laser" />
        </div>
        <p className="mt-4 text-center text-xs text-[#5B6B74] dark:text-gray-500" role="status">{t('result.scanningHint')}</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="panel panel-enter flex min-h-[28rem] items-center justify-center">
        <Radar title={t('result.awaiting')} hint={t('result.awaitingHint')} />
      </div>
    );
  }

  const hasBug = result.has_bug;
  const verdictColor = hasBug ? '#f87171' : '#34d399';

  return (
    <div className="panel panel-enter">
      <h2 className="panel-title">
        <span className="panel-icon"><Bug className="h-4 w-4" /></span> {t('result.title')}
      </h2>

      <div className="verdict mb-4" style={{ '--vc': verdictColor }}>
        <span className="verdict__icon">
          {hasBug ? <AlertTriangle className="h-5 w-5" /> : <CheckCircle2 className="h-5 w-5" />}
        </span>
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide" style={{ color: verdictColor }}>
            {hasBug ? t('result.bug') : t('result.noBug')}
          </p>
          <p className="text-xs text-[#5B6B74] dark:text-gray-400">
            {hasBug ? t('result.verdictBug', { n: result.num_detections }) : t('result.verdictOk')}
          </p>
        </div>
      </div>

      <div className={`overflow-hidden rounded-xl bg-[#F4F7F7] dark:bg-black/40 flex justify-center ${hasBug ? 'result-frame--bug' : 'result-frame--ok'}`}>
        <canvas ref={canvasRef} className="h-auto max-w-full" />
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
          <div className="space-y-2" onMouseLeave={() => setHover(null)}>
            {result.detections.map((d, i) => {
              const color = classColor(d.class_name);
              return (
                <div
                  key={i}
                  className="det-row tile flex items-center justify-between !py-2.5 text-sm"
                  style={{ '--c': color, '--i': i }}
                  data-active={hover === i}
                  onMouseEnter={() => setHover(i)}
                  onFocus={() => setHover(i)}
                  onBlur={() => setHover(null)}
                  tabIndex={0}
                >
                  <span className="flex items-center gap-2.5 text-[#0F1B24] dark:text-gray-200">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: color, boxShadow: `0 0 10px ${color}` }} />
                    {tClass(d.class_name)}
                  </span>
                  <span className="flex items-center gap-3">
                    <span className="hidden h-1.5 w-24 overflow-hidden rounded-full bg-[#DCE6E8] dark:bg-[#1E2733] sm:block">
                      <span className="det-bar" style={{ width: `${d.confidence * 100}%` }} />
                    </span>
                    <span className="bs-mono w-12 text-right text-xs font-semibold" style={{ color }}>
                      {(d.confidence * 100).toFixed(1)}%
                    </span>
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
