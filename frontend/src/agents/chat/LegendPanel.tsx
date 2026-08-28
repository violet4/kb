import { useState } from 'react';
import { tokens } from '../../shared/tokens';
import type { AddressedBlock } from './blockAddress';
import { blockMatchesFilter, computeFacets, type FacetFilter } from './facets';

interface LegendPanelProps {
  allBlocks: AddressedBlock[];
  visibleBlocks: AddressedBlock[];
  filter: FacetFilter;
  onToggleFilterValue: (key: string, value: string) => void;
  onClearFilter: () => void;
  onCollapseVisible: () => void;
  onExpandVisible: () => void;
  onCollapsePanel: () => void;
}

// Keys shown expanded by default -- everything else starts collapsed under its own
// disclosure. This is a display-order/prominence hint only; every key that occurs is still a
// real, usable facet regardless of whether it's in this list.
const PROMINENT_KEYS = ['kind', 'role', 'is_error', 'name', 'mcp.server'];

export default function LegendPanel({
  allBlocks,
  visibleBlocks,
  filter,
  onToggleFilterValue,
  onClearFilter,
  onCollapseVisible,
  onExpandVisible,
  onCollapsePanel,
}: LegendPanelProps) {
  const facets = computeFacets(allBlocks);
  const activeFilterCount = Array.from(filter.values()).reduce((sum, values) => sum + values.size, 0);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set(PROMINENT_KEYS));

  function toggleKeyExpanded(key: string) {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    // height: 100% (not position: sticky + a viewport-relative maxHeight) so this panel
    // always fills exactly its flex-item slot, whatever that happens to be in a given parent
    // layout -- a hardcoded `calc(100vh - Npx)` here was wrong the moment this component got
    // reused inside ChannelsView's own chrome height, and made the *page* scroll instead of
    // just this panel whenever its content (a session with many distinct facet values) was
    // taller than the viewport (confirmed live 2026-08-28). The parent is responsible for
    // giving this flex item a real bounded height (flex: 1 + min-height: 0 down the chain);
    // this component only needs to respect whatever height it's given and scroll internally.
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: 12,
        background: tokens.color.surface,
        border: `1px solid ${tokens.color.border}`,
        borderRadius: 8,
        fontSize: 12,
        overflowY: 'auto',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <span style={{ color: tokens.color.textMuted }}>
            {visibleBlocks.length} / {allBlocks.length} blocks
            {activeFilterCount > 0 && ` (${activeFilterCount} filter${activeFilterCount === 1 ? '' : 's'} active)`}
          </span>
          <button
            type="button"
            onClick={onCollapsePanel}
            aria-label="Collapse filter legend"
            title="Collapse filter legend"
            style={{ ...buttonStyle, padding: '2px 6px' }}
          >
            ▸
          </button>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {activeFilterCount > 0 && (
            <button type="button" onClick={onClearFilter} style={buttonStyle}>
              Clear filters
            </button>
          )}
          <button type="button" onClick={onCollapseVisible} style={buttonStyle}>
            Collapse shown
          </button>
          <button type="button" onClick={onExpandVisible} style={buttonStyle}>
            Expand shown
          </button>
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {facets.map((facet) => {
          const isExpanded = expandedKeys.has(facet.key);
          const activeValues = filter.get(facet.key);
          return (
            <div key={facet.key}>
              <button
                type="button"
                onClick={() => toggleKeyExpanded(facet.key)}
                aria-expanded={isExpanded}
                aria-label={`Toggle ${facet.key} filter options`}
                style={{
                  ...buttonStyle,
                  width: '100%',
                  textAlign: 'left',
                  display: 'flex',
                  justifyContent: 'space-between',
                }}
              >
                <span>
                  {facet.key} ({facet.values.length})
                </span>
                <span>{isExpanded ? '▾' : '▸'}</span>
              </button>
              {isExpanded && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '6px 4px' }}>
                  {facet.values.map(({ value, count }) => {
                    const isActive = activeValues?.has(value) ?? false;
                    return (
                      <label
                        key={value}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 4,
                          padding: '2px 6px',
                          borderRadius: 4,
                          border: `1px solid ${isActive ? tokens.color.accent : tokens.color.border}`,
                          color: isActive ? tokens.color.accent : tokens.color.text,
                          cursor: 'pointer',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isActive}
                          onChange={() => onToggleFilterValue(facet.key, value)}
                          style={{ margin: 0 }}
                        />
                        {value} ({count})
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const buttonStyle: React.CSSProperties = {
  padding: '3px 8px',
  borderRadius: 6,
  border: `1px solid ${tokens.color.border}`,
  background: tokens.color.background,
  color: tokens.color.text,
  fontSize: 12,
  cursor: 'pointer',
};

export function filterBlocks(blocks: AddressedBlock[], filter: FacetFilter): AddressedBlock[] {
  return blocks.filter((block) => blockMatchesFilter(block, filter));
}
