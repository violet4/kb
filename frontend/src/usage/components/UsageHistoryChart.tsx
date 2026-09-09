import { useState } from 'react';
import { tokens } from '../../shared/tokens';
import type { UsageSample } from '../types';

type Metric = 'session' | 'week';

interface UsageHistoryChartProps {
  samples: UsageSample[];
  hours: number;
  cumulative: boolean;
  metric: Metric;
  // Per-slot bars are bucketed to this many minutes each -- 1 for the 5h session view (matches
  // recording resolution), 60 for the 7d week view (raw per-minute deltas over a week would be
  // hundreds of near-invisible bars; bucketing to hourly is the resolution actually asked for).
  bucketMinutes: number;
}

const WIDTH = 600;
const HEIGHT = 200;
const PAD_LEFT = 36;
const PAD_RIGHT = 8;
const PAD_TOP = 10;
const PAD_BOTTOM = 24;
const MIN_BAR_HEIGHT = 2; // keeps a 0-delta bar visible/hoverable instead of collapsing to nothing

function pctOf(s: UsageSample, metric: Metric): number {
  return metric === 'session' ? s.session_pct : s.week_pct;
}

interface Bucket {
  bucketStart: number;
  bucketEnd: number;
  value: number;
  pctAfter: number;
}

// The raw pct only ever increases within its own reset window, so the raw reading at each
// sample is already the cumulative curve. "Per time slot" instead plots the delta consumed
// within each bucket -- which is what actually shows a burst (e.g. 14 subagents in 10 minutes)
// as a visible spike rather than just a steeper stretch of an otherwise-smooth line. Samples
// are bucketed by wall-clock time (not just consecutive-pairs) so a bucket with no recorded
// sample still shows as a real, empty gap rather than being silently skipped.
function toBuckets(samples: UsageSample[], metric: Metric, windowStart: number, now: number, bucketMs: number): Bucket[] {
  if (samples.length === 0) return [];
  const buckets: Bucket[] = [];
  const firstBucketStart = Math.floor(windowStart / bucketMs) * bucketMs;
  for (let bucketStart = firstBucketStart; bucketStart < now; bucketStart += bucketMs) {
    const bucketEnd = bucketStart + bucketMs;
    // Last sample at/before bucketStart, and last sample at/before bucketEnd -- the delta
    // between those two readings is how much was consumed during this bucket.
    let before: UsageSample | null = null;
    let through: UsageSample | null = null;
    for (const s of samples) {
      const t = new Date(s.sampled_at).getTime();
      if (t <= bucketStart) before = s;
      if (t <= bucketEnd) through = s;
    }
    if (before === null && through === null) continue;
    const startPct = before ? pctOf(before, metric) : pctOf(samples[0], metric);
    const endPct = through ? pctOf(through, metric) : startPct;
    buckets.push({ bucketStart, bucketEnd, value: Math.max(0, endPct - startPct), pctAfter: endPct });
  }
  return buckets;
}

function formatClock(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function formatDayClock(ms: number, multiDay: boolean): string {
  if (!multiDay) return formatClock(ms);
  return new Date(ms).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

interface TooltipState {
  x: number;
  y: number;
  lines: string[];
}

// Plain inline SVG, no charting library -- a handful of points on a fixed axis doesn't need
// more than a polyline/bars, a few gridlines, and a hand-rolled tooltip.
export default function UsageHistoryChart({ samples, hours, cumulative, metric, bucketMinutes }: UsageHistoryChartProps) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const plotW = WIDTH - PAD_LEFT - PAD_RIGHT;
  const plotH = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const multiDay = hours > 24;

  const now = Date.now();
  const windowStart = now - hours * 60 * 60 * 1000;
  const windowMs = now - windowStart;
  const bucketMs = bucketMinutes * 60 * 1000;

  const xFor = (t: number) => {
    const frac = Math.max(0, Math.min(1, (t - windowStart) / windowMs));
    return PAD_LEFT + frac * plotW;
  };

  const buckets = toBuckets(samples, metric, windowStart, now, bucketMs);
  const maxBucketValue = Math.max(1, ...buckets.map((b) => b.value));
  const yMax = cumulative ? 100 : maxBucketValue;
  const yFor = (value: number) => PAD_TOP + (1 - Math.max(0, Math.min(yMax, value)) / yMax) * plotH;

  // Cumulative gridlines are plain 0/25/50/75/100% fractions. Per-slot deltas are always
  // whole percentage-points (claude -p /usage never reports sub-1% -- see kb_cli/usage.py's
  // _SESSION_RE, and the session_pct/week_pct DB columns are Integer), so a fractional
  // gridline like "+0.3%" can never land on a real data point -- pick integer ticks instead,
  // deduped for a small maxBucketValue (e.g. 1 or 2) where 25%/50%/75% steps would collide.
  const gridValues = cumulative
    ? [0, yMax * 0.25, yMax * 0.5, yMax * 0.75, yMax]
    : Array.from(new Set([0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(yMax * f)))).sort((a, b) => a - b);
  const hasData = cumulative ? samples.length > 0 : buckets.some((b) => b.value > 0) || buckets.length > 0;

  const path = samples
    .map((s, i) => `${i === 0 ? 'M' : 'L'} ${xFor(new Date(s.sampled_at).getTime())} ${yFor(pctOf(s, metric))}`)
    .join(' ');

  const metricLabel = metric === 'session' ? 'session' : 'week';

  return (
    <div style={{ position: 'relative' }}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        width="100%"
        height={HEIGHT}
        role="img"
        aria-label={
          cumulative
            ? `Cumulative ${metricLabel} usage percentage over the last ${hours} hours`
            : `${metricLabel} usage consumed per ${bucketMinutes >= 60 ? 'hour' : 'minute'} over the last ${hours} hours`
        }
        onMouseLeave={() => setTooltip(null)}
      >
        {gridValues.map((v) => (
          <g key={v}>
            <line x1={PAD_LEFT} x2={WIDTH - PAD_RIGHT} y1={yFor(v)} y2={yFor(v)} stroke={tokens.color.border} strokeWidth={1} />
            <text x={PAD_LEFT - 6} y={yFor(v) + 4} textAnchor="end" fontSize={10} fill={tokens.color.textMuted}>
              {cumulative ? `${Math.round(v)}%` : `+${v}%`}
            </text>
          </g>
        ))}

        {!hasData ? (
          <text x={PAD_LEFT + plotW / 2} y={PAD_TOP + plotH / 2} textAnchor="middle" fontSize={12} fill={tokens.color.textMuted}>
            No samples recorded yet in this window
          </text>
        ) : cumulative ? (
          <>
            <path d={path} fill="none" stroke={tokens.color.accent} strokeWidth={2} />
            {samples.map((s, i) => {
              const t = new Date(s.sampled_at).getTime();
              const pct = pctOf(s, metric);
              return (
                <g key={i}>
                  <circle cx={xFor(t)} cy={yFor(pct)} r={2.5} fill={tokens.color.accent} />
                  {/* Larger invisible hit area layered on top -- the visible dot (r=2.5) is too
                      small to hover reliably. */}
                  <circle
                    cx={xFor(t)}
                    cy={yFor(pct)}
                    r={8}
                    fill="transparent"
                    onMouseEnter={() =>
                      setTooltip({
                        x: xFor(t),
                        y: yFor(pct),
                        lines: [formatDayClock(t, multiDay), `session ${s.session_pct}%  ·  week ${s.week_pct}%`],
                      })
                    }
                    onMouseLeave={() => setTooltip(null)}
                  />
                </g>
              );
            })}
          </>
        ) : (
          buckets.map((b, i) => {
            // True width: the fraction of the time axis one bucket actually spans, not the
            // plot width divided by bucket count (that stretched bars to fill the axis even
            // when real data only covered a fraction of the window).
            const barW = Math.max(1, (bucketMs / windowMs) * plotW - 1);
            const barX = xFor(b.bucketStart);
            const barTop = Math.min(yFor(b.value), HEIGHT - PAD_BOTTOM - MIN_BAR_HEIGHT);
            return (
              <g
                key={i}
                onMouseEnter={() =>
                  setTooltip({
                    x: barX,
                    y: barTop,
                    lines: [
                      `${formatDayClock(b.bucketStart, multiDay)} – ${formatDayClock(b.bucketEnd, multiDay)}`,
                      `+${b.value}% this ${bucketMinutes >= 60 ? 'hour' : 'interval'}`,
                      `${metricLabel} ${b.pctAfter}%`,
                    ],
                  })
                }
                onMouseLeave={() => setTooltip(null)}
              >
                {/* Invisible full-height hit area so a 0-delta bar is still hoverable. */}
                <rect x={barX} y={PAD_TOP} width={barW} height={plotH} fill="transparent" />
                <rect x={barX} y={barTop} width={barW} height={HEIGHT - PAD_BOTTOM - barTop} fill={tokens.color.accent} />
              </g>
            );
          })
        )}

        <line
          x1={PAD_LEFT}
          x2={WIDTH - PAD_RIGHT}
          y1={HEIGHT - PAD_BOTTOM}
          y2={HEIGHT - PAD_BOTTOM}
          stroke={tokens.color.border}
          strokeWidth={1}
        />
        <text x={PAD_LEFT} y={HEIGHT - 6} fontSize={10} fill={tokens.color.textMuted}>
          {multiDay ? `${Math.round(hours / 24)}d ago` : `${hours}h ago`}
        </text>
        <text x={WIDTH - PAD_RIGHT} y={HEIGHT - 6} textAnchor="end" fontSize={10} fill={tokens.color.textMuted}>
          now
        </text>
      </svg>

      {tooltip && (
        <div
          style={{
            position: 'absolute',
            left: `${(tooltip.x / WIDTH) * 100}%`,
            top: `${(tooltip.y / HEIGHT) * 100}%`,
            transform: 'translate(-50%, -100%) translateY(-6px)',
            background: tokens.color.background,
            border: `1px solid ${tokens.color.border}`,
            borderRadius: 6,
            padding: '6px 8px',
            fontSize: 11,
            color: tokens.color.text,
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
            transition: 'none',
            zIndex: 1,
          }}
        >
          {tooltip.lines.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      )}
    </div>
  );
}
