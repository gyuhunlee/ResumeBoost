import { useState } from "react";
import type { Reminder } from "../../types";
import { formatTime, formatUpcomingDay } from "../../lib/dates";
import { Card, Pager, STATUS_COLOR, STATUS_TEXT, STATUS_TINT, paginate } from "../ui";

const PAGE_SIZE = 4;
import { CheckIcon, XIcon } from "../Icons";

const KIND_LABEL: Record<Reminder["kind"], string> = {
  interviewing: "Interview",
  follow_up: "Follow up",
  offer: "Offer",
};

function whenLabel(r: Reminder): string {
  const day = formatUpcomingDay(r.date);
  const time = r.time ? ` · ${formatTime(r.time)}` : "";
  if (r.kind === "follow_up") return day === "Today" ? "Due today" : `Due ${day}`;
  if (r.kind === "offer") return `Respond by ${day}`;
  return `${day}${time}`;
}

type Props = {
  reminders: Reminder[];
  onDismiss: (id: string) => void;
  onClearAll: () => void;
};

export default function RemindersPanel({ reminders, onDismiss, onClearAll }: Props) {
  const [pageNum, setPageNum] = useState(1);
  const { pageItems, page, pages } = paginate(reminders, pageNum, PAGE_SIZE);
  return (
    <Card className="flex min-w-0 flex-[1_1_340px] flex-col gap-4 p-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="m-0 text-[17px] font-semibold">Upcoming</h2>
          {reminders.length > 0 && (
            <span className="inline-flex h-[22px] min-w-[22px] items-center justify-center rounded-full bg-blue-50 px-1.5 text-xs font-semibold text-blue-700">
              {reminders.length}
            </span>
          )}
        </div>
        {reminders.length > 0 && (
          <button type="button" onClick={onClearAll} className="min-h-9 cursor-pointer px-2 text-sm font-medium text-blue-700 hover:text-blue-800">
            Clear all
          </button>
        )}
      </div>

      {reminders.length > 0 ? (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {pageItems.map((r) => (
            <li key={r.id} className="relative flex items-start gap-3 rounded-[10px] border border-slate-200 py-3.5 pr-11 pl-3.5">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" style={{ background: STATUS_TINT[r.kind] }} aria-hidden="true">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: STATUS_COLOR[r.kind] }} />
              </span>
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="text-xs font-semibold tracking-wide uppercase" style={{ color: STATUS_TEXT[r.kind] }}>
                  {KIND_LABEL[r.kind]}
                </span>
                <span className="text-sm font-semibold">
                  {r.company} · {r.role}
                </span>
                <span className="text-[13px] text-slate-600">{r.message}</span>
                <span className="mt-0.5 text-[13px] font-medium text-slate-700">{whenLabel(r)}</span>
              </div>
              <button
                type="button"
                onClick={() => onDismiss(r.id)}
                aria-label={`Dismiss ${KIND_LABEL[r.kind].toLowerCase()} reminder for ${r.company}`}
                className="absolute top-1.5 right-1.5 flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-700"
              >
                <XIcon size={16} />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="flex min-h-80 flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-green-50 text-green-600">
            <CheckIcon size={24} />
          </span>
          <span className="text-[17px] font-semibold">You're all caught up</span>
          <span className="max-w-60 text-sm text-slate-500">
            No upcoming interviews or reminders. New ones will show up here as your inbox updates.
          </span>
        </div>
      )}

      {/* Pinned to the bottom so the arrows stay put while paging */}
      <div className="mt-auto">
        <Pager page={page} pages={pages} total={reminders.length} size={PAGE_SIZE} onPage={setPageNum} label="Upcoming pages" />
      </div>
    </Card>
  );
}
