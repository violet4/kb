import type { ChatBlock, ChatMessage } from './types';

export interface AddressedBlock {
  id: string; // `${messageIndex}:${blockIndex}` -- stable within one loaded transcript
  messageIndex: number;
  message: ChatMessage;
  block: ChatBlock;
  // block.tags plus a synthetic "kind" entry -- folding kind into the same tag map means
  // the legend/filter panel treats "is this a tool_use" and "is this isSidechain=true" as
  // the same kind of facet, with no special-cased UI for kind alone.
  tags: Record<string, string>;
}

// Addressed once per message, when the message arrives: a live transcript appends messages
// without re-addressing the ones already shown, so their AddressedBlock objects keep their
// identity and memoized rows for them never re-render.
export function addressMessage(message: ChatMessage, messageIndex: number): AddressedBlock[] {
  return message.blocks.map((block, blockIndex) => ({
    id: `${messageIndex}:${blockIndex}`,
    messageIndex,
    message,
    block,
    tags: { kind: block.kind, ...block.tags },
  }));
}
