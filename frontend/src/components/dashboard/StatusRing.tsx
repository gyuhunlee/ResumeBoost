import { useState } from "react";
import type { ApplicationStatus, StatusCounts } from "../../types";
import { Card, STATUS_COLOR, STATUS_ORDER, STATUS_TEXT, STATUS_TINT, statusLabel } from "../ui";

const SIZE = 220;
const STROKE = 22;
const R = (SIZE - STROKE) / 2;
const CIRC = 2 * Math.PI * R;
const GAP = 4; // px of empty ring between slices

/** LeetCode-style donut: one slice per status, total in the middle. Hover a slice or legend row for its numbers. */
export default function StatusRing({ counts }: { counts: StatusCounts }) {
  const [focus, setFocus] = useState<ApplicationStatus | null>(null);
  const total = STATUS_ORDER.reduce((sum, s) => sum + counts[s], 0);
  const nonZero = STATUS_ORDER.filter((s) => counts[s] > 0);
  const gap = nonZero.length > 1 ? GAP : 0;

  let offset = 0;
  const slices = nonZero.map((s) => {
    const len = (counts[s] / total) * CIRC;
    const slice = { status: s, dash: Math.max(len - gap, 0.5), offset };
    offset += len;
    return slice;
  });

  const pct = (n: number) => (total ? Math.round((n / total) * 100) : 0);
  const summary = STATUS_ORDER.map((s) => `${statusLabel(s)} ${counts[s]}`).join(", ");

  return (
    <Card className="flex flex-col gap-5 p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="m-0 text-[17px] font-semibold">Application pipeline</h2>
        <span className="text-[13px] text-slate-500">All time</span>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-10">
        <div className="relative shrink-0" style={{ width: SIZE, height: SIZE }}>
          <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={`Applications by status: ${summary}`}>
            <g transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}>
              <circle cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none" stroke="#F1F5F9" strokeWidth={STROKE} />
              {slices.map((sl) => (
                <circle
                  key={sl.status}
                  cx={SIZE / 2}
                  cy={SIZE / 2}
                  r={R}
                  fill="none"
                  stroke={focus && focus !== sl.status ? STATUS_TINT[sl.status] : STATUS_COLOR[sl.status]}
                  strokeWidth={focus === sl.status ? STROKE + 4 : STROKE}
                  strokeDasharray={`${sl.dash} ${CIRC}`}
                  strokeDashoffset={-sl.offset}
                  className="cursor-default transition-[stroke,stroke-width] duration-150"
                  onMouseEnter={() => setFocus(sl.status)}
                  onMouseLeave={() => setFocus(null)}
                />
              ))}
            </g>
          </svg>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center" aria-hidden="true">
            <span className="text-[44px] leading-tight font-bold" style={{ color: focus ? STATUS_TEXT[focus] : "#0F172A" }}>
              {focus ? counts[focus] : total}
            </span>
            <span className="text-sm font-medium text-slate-700">{focus ? statusLabel(focus) : "Total applications"}</span>
            {focus && <span className="text-xs text-slate-500">{pct(counts[focus])}% of {total}</span>}
          </div>
        </div>

        <ul className="m-0 flex max-w-[360px] min-w-[240px] flex-1 list-none flex-col gap-1 p-0">
          {STATUS_ORDER.map((s) => (
            <li key={s}>
              <button
                type="button"
                onMouseEnter={() => setFocus(s)}
                onMouseLeave={() => setFocus(null)}
                onFocus={() => setFocus(s)}
                onBlur={() => setFocus(null)}
                className={`flex min-h-11 w-full cursor-default items-center gap-3 rounded-lg px-3 text-left ${
                  focus === s ? "bg-slate-100" : ""
                }`}
              >
                <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: STATUS_COLOR[s] }} aria-hidden="true" />
                <span className="flex-1 text-[15px]">{statusLabel(s)}</span>
                <span className="min-w-6 text-right text-[15px] font-semibold">{counts[s]}</span>
                <span className="min-w-10 text-right text-[13px] text-slate-500">{pct(counts[s])}%</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}
