import type { DragEvent } from 'react';

// Dragging a kb record (a row on a context page, a search hit) onto a context in the
// sidebar moves it there. The record travels in the drag's dataTransfer under its own MIME
// type, so a drop target can tell a record drag apart from any other drag during dragover,
// when the payload itself isn't readable yet.
const RECORD_MIME = 'application/x-kb-record';

export interface DraggedRecord {
  type: string; // model name, e.g. "Todo"; "Context" means re-parent rather than re-place
  id: number;
  label: string;
}

export function recordDragProps(record: DraggedRecord) {
  return {
    draggable: true,
    onDragStart: (e: DragEvent) => {
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData(RECORD_MIME, JSON.stringify(record));
      e.dataTransfer.setData('text/plain', `${record.type}:${record.id} ${record.label}`);
    },
  };
}

export function isRecordDrag(e: DragEvent): boolean {
  return isRecordDragEvent(e.nativeEvent);
}

// The same check for a native (window-level) event, e.g. to react to any record drag starting.
export function isRecordDragEvent(e: globalThis.DragEvent): boolean {
  return e.dataTransfer?.types.includes(RECORD_MIME) ?? false;
}

export function draggedRecord(e: DragEvent): DraggedRecord | null {
  const raw = e.dataTransfer.getData(RECORD_MIME);
  return raw ? (JSON.parse(raw) as DraggedRecord) : null;
}
