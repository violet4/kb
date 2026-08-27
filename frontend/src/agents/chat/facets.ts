import type { AddressedBlock } from './blockAddress';

export interface FacetValue {
  value: string;
  count: number;
}

export interface Facet {
  key: string;
  values: FacetValue[];
}

// Unions every (tag key -> tag value) pair actually present across the given blocks into a
// sorted facet list -- this is the entire "legend," built generically from whatever keys the
// backend's tags happened to carry rather than a fixed field list. A key present on every
// block (e.g. "role" with only two values) is just as valid a facet as one that appears once;
// the caller decides what's worth showing prominently.
export function computeFacets(blocks: AddressedBlock[]): Facet[] {
  const byKey = new Map<string, Map<string, number>>();
  for (const { tags } of blocks) {
    for (const [key, value] of Object.entries(tags)) {
      let values = byKey.get(key);
      if (!values) {
        values = new Map();
        byKey.set(key, values);
      }
      values.set(value, (values.get(value) ?? 0) + 1);
    }
  }
  return Array.from(byKey.entries())
    .map(([key, values]) => ({
      key,
      values: Array.from(values.entries())
        .map(([value, count]) => ({ value, count }))
        .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value)),
    }))
    .sort((a, b) => a.key.localeCompare(b.key));
}

// A filter is a set of active (key, value) selections, ANDed across keys and ORed within a
// key -- e.g. {kind: [tool_use, tool_result], is_error: [true]} means "(tool_use OR
// tool_result) AND is_error=true". An empty set for a key means "no restriction on that key."
export type FacetFilter = Map<string, Set<string>>;

export function blockMatchesFilter(block: AddressedBlock, filter: FacetFilter): boolean {
  for (const [key, allowedValues] of filter) {
    if (allowedValues.size === 0) continue;
    if (!allowedValues.has(block.tags[key] ?? '')) return false;
  }
  return true;
}
