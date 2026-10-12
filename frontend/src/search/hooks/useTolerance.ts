import { useState } from 'react';
import { useDebounced } from '../../shared/useDebounced';
import { useSearchInfo } from './useSearchInfo';

// The semantic distance cutoff a search page lets the user loosen or tighten: `value` follows
// the slider as it moves (starting at the backend's default), `settled` is what a query should
// use -- the value once the slider has rested for a moment, so dragging it re-runs the search
// once rather than per pixel.
export function useTolerance(): { value: number | null; set: (value: number) => void; settled: number | null } {
  const info = useSearchInfo();
  const [chosen, setChosen] = useState<number | null>(null);
  const value = chosen ?? info?.max_dist ?? null;
  return { value, set: setChosen, settled: useDebounced(value, 300) };
}
