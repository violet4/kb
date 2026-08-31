import { useEffect, useState } from 'react';

const STORAGE_KEY = 'kb-events-today-highlight';

// Glowy dark royal purple default: a bright, saturated hue at low alpha so it reads
// as a gentle wash over the day cell rather than an opaque block -- brightness and
// alpha are separate knobs (see UseTodayHighlightResult) specifically so a color that
// looks right at one alpha can be tuned without also having to re-pick the hue.
const DEFAULT_RGB = '124, 58, 237'; // royal purple, as an "r, g, b" triplet for rgba() interpolation
const DEFAULT_ALPHA = 0.35;

interface StoredHighlight {
  rgb: string;
  alpha: number;
}

interface UseTodayHighlightResult {
  rgb: string;
  alpha: number;
  color: string;
  setRgb: (rgb: string) => void;
  setAlpha: (alpha: number) => void;
}

export function useTodayHighlight(): UseTodayHighlightResult {
  const [{ rgb, alpha }, setState] = useState<StoredHighlight>(() => readStored());

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ rgb, alpha }));
  }, [rgb, alpha]);

  return {
    rgb,
    alpha,
    color: `rgba(${rgb}, ${alpha})`,
    setRgb: (value) => setState((s) => ({ ...s, rgb: value })),
    setAlpha: (value) => setState((s) => ({ ...s, alpha: value })),
  };
}

function readStored(): StoredHighlight {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return { rgb: DEFAULT_RGB, alpha: DEFAULT_ALPHA };
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed.rgb === 'string' && typeof parsed.alpha === 'number') return parsed;
  } catch {
    // fall through to default
  }
  return { rgb: DEFAULT_RGB, alpha: DEFAULT_ALPHA };
}
