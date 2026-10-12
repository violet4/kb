import { useEffect, useState, type ReactNode } from 'react';
import Popover from '../../shared/Popover';
import { tokens } from '../../shared/tokens';
import { fetchSearchInfo } from '../api';
import type { SearchInfo } from '../types';

// A "?" explaining what kb search matches and how results are limited. The model lists and
// limit come from the backend's /search-all/info, so this text can't drift from the code.
export default function SearchHelp({ intro, align }: { intro?: ReactNode; align?: 'start' | 'end' }) {
  const [info, setInfo] = useState<SearchInfo | null>(null);
  useEffect(() => {
    fetchSearchInfo()
      .then(setInfo)
      .catch(() => setInfo(null));
  }, []);

  return (
    <Popover label="?" align={align} ariaLabel="How search works">
      <div style={{ maxWidth: 380, fontSize: 12, lineHeight: 1.5, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {intro && <div>{intro}</div>}
        {info ? (
          <>
            <div>
              <b>Substring</b>: case-insensitive match in {info.substring_fields.join('/')} of{' '}
              {info.substring_models.join(', ')}. Every match is kept and ranked first.
            </div>
            <div>
              <b>Semantic</b>: up to {info.default_limit} nearest rows per model within embedding cosine distance{' '}
              {info.max_dist} (smaller is closer), over {info.semantic_models.join(', ')}.
            </div>
            <div>
              <b>Merged</b>: done/dropped rows are excluded, duplicates keep their best score, and the top{' '}
              {info.default_limit} overall are shown.
            </div>
          </>
        ) : (
          <div style={{ color: tokens.color.textMuted }}>Search details unavailable.</div>
        )}
      </div>
    </Popover>
  );
}
