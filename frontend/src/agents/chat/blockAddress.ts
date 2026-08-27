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

export function addressBlocks(messages: ChatMessage[]): AddressedBlock[] {
  const result: AddressedBlock[] = [];
  messages.forEach((message, messageIndex) => {
    message.blocks.forEach((block, blockIndex) => {
      result.push({
        id: `${messageIndex}:${blockIndex}`,
        messageIndex,
        message,
        block,
        tags: { kind: block.kind, ...block.tags },
      });
    });
  });
  return result;
}
