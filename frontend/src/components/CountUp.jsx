import { useEffect, useRef, useState } from 'react';

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/** Animates from the previous value to `value` (ease-out), e.g. for dashboard numbers. */
export default function CountUp({ value, decimals = 0, suffix = '', duration = 900 }) {
  const [shown, setShown] = useState(prefersReducedMotion() ? value : 0);
  const from = useRef(shown);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setShown(value);
      from.current = value;
      return undefined;
    }
    const start = performance.now();
    const origin = from.current;
    let frame;
    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - progress) ** 3;
      const current = origin + (value - origin) * eased;
      setShown(current);
      from.current = current;
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);

  return (
    <>
      {shown.toFixed(decimals)}
      {suffix}
    </>
  );
}
