import type { ReactNode } from 'react';
import { tokens } from '../shared/tokens';
import { RAW_STRING, isBoolean, isHexColor, useStoredState } from '../shared/useStoredState';
import { TranscriptSettingsContext } from './hooks/useTranscriptSettings';

// The one owner of the transcript display settings. Each is a stored preference; holding them
// here, above every page that shows a transcript, means a change in the ⚙ popover reaches the
// transcript directly, with no component in between passing it along.
export default function TranscriptSettingsProvider({ children }: { children: ReactNode }) {
  const [showTags, setShowTags] = useStoredState('kb-agents-transcript-show-tags', false, isBoolean);
  const [showThinking, setShowThinking] = useStoredState('kb-agents-transcript-show-thinking', true, isBoolean);
  const [collapsedAsBars, setCollapsedAsBars] = useStoredState(
    'kb-agents-transcript-collapsed-as-bars',
    false,
    isBoolean,
  );
  const [barColor, setBarColor] = useStoredState(
    'kb-agents-transcript-bar-color',
    tokens.color.textMuted,
    isHexColor,
    RAW_STRING,
  );
  return (
    <TranscriptSettingsContext.Provider
      value={{
        showTags,
        setShowTags,
        showThinking,
        setShowThinking,
        collapsedAsBars,
        setCollapsedAsBars,
        barColor,
        setBarColor,
      }}
    >
      {children}
    </TranscriptSettingsContext.Provider>
  );
}
