import type { ReactNode } from 'react';
import { tokens } from '../shared/tokens';
import { RAW_STRING, isBoolean, isHexColor, isNonNegativeNumber, useStoredState } from '../shared/useStoredState';
import { TranscriptSettingsContext } from './hooks/useTranscriptSettings';

const DEFAULT_HUNG_CALL_SECONDS = 2;

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
  const [expandBash, setExpandBash] = useStoredState('kb-agents-transcript-expand-bash', false, isBoolean);
  const [hungCallSeconds, setHungCallSeconds] = useStoredState(
    'kb-agents-transcript-hung-call-seconds',
    DEFAULT_HUNG_CALL_SECONDS,
    isNonNegativeNumber,
  );
  const [keepHungCallsOpen, setKeepHungCallsOpen] = useStoredState(
    'kb-agents-transcript-keep-hung-calls-open',
    true,
    isBoolean,
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
        expandBash,
        setExpandBash,
        hungCallSeconds,
        setHungCallSeconds,
        keepHungCallsOpen,
        setKeepHungCallsOpen,
      }}
    >
      {children}
    </TranscriptSettingsContext.Provider>
  );
}
