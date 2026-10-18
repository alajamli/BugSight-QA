import { useI18n } from '../i18n';

const PRESETS = [
  { key: 'conf.sensitive', value: 0.15 },
  { key: 'conf.balanced', value: 0.25 },
  { key: 'conf.strict', value: 0.5 },
];

const MIN = 0.05;
const MAX = 0.95;

/** Confidence threshold: filled slider, live value and three quick presets. */
export default function ConfidenceControl({ value, onChange, disabled = false, id = 'confidence' }) {
  const { t } = useI18n();
  const pct = ((value - MIN) / (MAX - MIN)) * 100;

  return (
    <div>
      <label htmlFor={id} className="form-label">
        <span>{t('common.confidence')}</span>
        <span className="value-pill">{value.toFixed(2)}</span>
      </label>
      <input
        id={id}
        type="range"
        min={MIN}
        max={MAX}
        step="0.05"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="range mt-2"
        style={{ '--pct': `${pct}%` }}
      />
      <div className="mt-1 flex flex-wrap gap-1.5">
        {PRESETS.map((preset) => (
          <button
            key={preset.key}
            type="button"
            className="chip"
            disabled={disabled}
            aria-pressed={Math.abs(value - preset.value) < 0.001}
            onClick={() => onChange(preset.value)}
          >
            {t(preset.key)}
          </button>
        ))}
      </div>
      <p className="form-help">{t('conf.hint')}</p>
    </div>
  );
}
