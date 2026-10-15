import { createContext, useContext } from 'react';

// How a session transcript is displayed: the ⚙ popover on the agent page sets these, and every
// transcript (the agent page's, and Channels' session pane) reads them.
export interface TranscriptSettings {
  // Each block's raw transcript fields (kind, isSidechain, model, ...) under its content.
  showTags: boolean;
  setShowTags: (value: boolean) => void;
  // Off: thinking blocks start collapsed like tool calls, so they fold into collapsed runs.
  showThinking: boolean;
  setShowThinking: (value: boolean) => void;
  // On: every stretch of collapsed cards, a lone one included, is a small colored bar with no text.
  collapsedAsBars: boolean;
  setCollapsedAsBars: (value: boolean) => void;
  barColor: string; // #rrggbb, for those bars
  setBarColor: (value: string) => void;
}

export const TranscriptSettingsContext = createContext<TranscriptSettings | null>(null);

export function useTranscriptSettings(): TranscriptSettings {
  const settings = useContext(TranscriptSettingsContext);
  if (settings === null) throw new Error('useTranscriptSettings needs a TranscriptSettingsProvider above it');
  return settings;
}
