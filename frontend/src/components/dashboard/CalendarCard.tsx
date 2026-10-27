import { useMemo, useState } from "react";
import type { CalendarEvent } from "../../types";
import { formatTime, parseISODate, toISODate } from "../../lib/dates";
import { Card, STATUS_COLOR } from "../ui";
import { ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon } from "../Icons";

const MONTHS = Array.from({ length: 12 }, (_, i) => new Date(2000, i, 1).toLocaleDateString("en-US", { month: "long" }));
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS_BACK = 24; // how far back the user can browse
const MONTHS_AHEAD = 12;

// A month as a single number (year * 12 + month) so ranges are easy to compare.
const monthIndex = (d: Date) => d.getFullYear() * 12 + d.getMonth();

type Props = {
  /** Events to show. The dashboard already removed anything from before the user signed up. */
  events: CalendarEvent[];
  /** The user's sign-up date. Browsing never goes earlier than its month. */
  signedUpAt?: Date | null;
};

export default function CalendarCard({ events, signedUpAt }: Props) {
  const today = new Date();
  const todayISO = toISODate(today);
  const minMonth = Math.max(monthIndex(today) - MONTHS_BACK, signedUpAt ? monthIndex(signedUpAt) : -Infinity);
  const maxMonth = monthIndex(today) + MONTHS_AHEAD;

  const [view, setView] = useState<"days" | "months">("days");
  const [cursor, setCursor] = useState(monthIndex(today)); // month being shown
  const [selected, setSelected] = useState(todayISO);

  const year = Math.floor(cursor / 12);
  const month = cursor % 12;

  const byDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const e of events) map.set(e.date, [...(map.get(e.date) ?? []), e]);
    for (const list of map.values()) list.sort((a, b) => (a.time ?? "").localeCompare(b.time ?? ""));
    return map;
  }, [events]);

  // Always 6 rows so the card doesn't jump in height between months.
  const cells = useMemo(() => {
    const first = new Date(year, month, 1).getDay();
    return Array.from({ length: 42 }, (_, i) => new Date(year, month, 1 - first + i));
  }, [year, month]);

  const clamp = (m: number) => Math.min(Math.max(m, minMonth), maxMonth);
  const prevDisabled = view === "days" ? cursor <= minMonth : year * 12 - 1 < minMonth;
  const nextDisabled = view === "days" ? cursor >= maxMonth : (year + 1) * 12 > maxMonth;
  const step = (dir: -1 | 1) => setCursor((c) => clamp(view === "days" ? c + dir : c + dir * 12));

  const goToday = () => {
    setCursor(monthIndex(today));
    setSelected(todayISO);
    setView("days");
  };

  const pickDay = (d: Date) => {
    const m = monthIndex(d);
    if (m < minMonth || m > maxMonth) return;
    setSelected(toISODate(d));
    if (m !== cursor) setCursor(m);
  };

  const agenda = byDate.get(selected) ?? [];
  const selectedDate = parseISODate(selected);

  const navBtn =
    "flex h-10 w-10 cursor-pointer items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:cursor-default disabled:opacity-35";

  return (
    <Card className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="m-0 text-[17px] font-semibold">Calendar</h2>
        <button
          type="button"
          onClick={goToday}
          className="min-h-9 cursor-pointer rounded-full border border-slate-300 bg-white px-3.5 text-[13px] font-medium hover:bg-slate-50"
        >
          Today
        </button>
      </div>

      <div className="flex flex-wrap gap-6">
        <div className="flex min-w-0 flex-[1_1_340px] flex-col gap-3">
          <div className="flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => setView(view === "days" ? "months" : "days")}
              aria-label={view === "days" ? `${MONTHS[month]} ${year}, choose month` : `${year}, back to days`}
              className="-ml-2.5 inline-flex min-h-10 cursor-pointer items-center gap-1.5 rounded-lg px-2.5 text-base font-semibold hover:bg-slate-50"
            >
              {view === "days" ? `${MONTHS[month]} ${year}` : year}
              <ChevronDownIcon size={14} className={`text-slate-500 transition-transform ${view === "months" ? "rotate-180" : ""}`} />
            </button>
            <div className="flex gap-1">
              <button type="button" onClick={() => step(-1)} disabled={prevDisabled} aria-label={view === "days" ? "Previous month" : "Previous year"} className={navBtn}>
                <ChevronLeftIcon size={16} />
              </button>
              <button type="button" onClick={() => step(1)} disabled={nextDisabled} aria-label={view === "days" ? "Next month" : "Next year"} className={navBtn}>
                <ChevronRightIcon size={16} />
              </button>
            </div>
          </div>

          {view === "days" ? (
            <div className="grid grid-cols-7 gap-0.5" role="group" aria-label={`${MONTHS[month]} ${year}`}>
              {WEEKDAYS.map((w) => (
                <div key={w} className="pt-1 pb-2 text-center text-xs font-semibold text-slate-500" aria-hidden="true">
                  {w}
                </div>
              ))}
              {cells.map((d) => {
                const iso = toISODate(d);
                const outside = d.getMonth() !== month;
                const isToday = iso === todayISO;
                const isSelected = iso === selected;
                const dayEvents = byDate.get(iso) ?? [];
                const unavailable = monthIndex(d) < minMonth || monthIndex(d) > maxMonth;
                const label =
                  d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" }) +
                  (dayEvents.length ? `, ${dayEvents.length} event${dayEvents.length > 1 ? "s" : ""}` : "");
                return (
                  <button
                    key={iso}
                    type="button"
                    onClick={() => pickDay(d)}
                    disabled={unavailable}
                    aria-label={label}
                    aria-pressed={isSelected}
                    aria-current={isToday ? "date" : undefined}
                    className={`flex h-11 cursor-pointer flex-col items-center justify-center gap-[3px] rounded-lg text-sm disabled:cursor-default disabled:opacity-30 ${
                      isToday
                        ? "bg-blue-700 font-semibold text-white"
                        : isSelected
                          ? "bg-blue-50 font-semibold text-blue-700 ring-[1.5px] ring-blue-700 ring-inset"
                          : outside
                            ? "text-slate-500 hover:bg-slate-50"
                            : "text-slate-900 hover:bg-slate-50"
                    } ${isToday && isSelected ? "ring-2 ring-blue-200" : ""}`}
                  >
                    <span>{d.getDate()}</span>
                    <span className="flex h-[5px] gap-[3px]" aria-hidden="true">
                      {dayEvents.slice(0, 3).map((e) => (
                        <span
                          key={e.id}
                          className="h-[5px] w-[5px] rounded-full"
                          style={{ background: STATUS_COLOR[e.kind], boxShadow: isToday ? "0 0 0 1px #fff" : undefined }}
                        />
                      ))}
                    </span>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2 pt-2">
              {MONTHS.map((name, i) => {
                const m = year * 12 + i;
                const disabled = m < minMonth || m > maxMonth;
                const current = m === cursor;
                const isNow = m === monthIndex(today);
                return (
                  <button
                    key={name}
                    type="button"
                    disabled={disabled}
                    aria-pressed={current}
                    onClick={() => {
                      setCursor(m);
                      setView("days");
                    }}
                    className={`h-16 cursor-pointer rounded-xl text-[15px] disabled:cursor-default disabled:opacity-35 ${
                      current
                        ? "bg-blue-700 font-semibold text-white"
                        : isNow
                          ? "bg-blue-50 font-semibold text-slate-900 hover:bg-blue-100"
                          : "bg-slate-50 font-medium text-slate-900 hover:bg-slate-100"
                    }`}
                  >
                    {name.slice(0, 3)}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex min-w-0 flex-[1_1_220px] flex-col gap-3 border-slate-100 md:border-l md:pl-6" aria-live="polite">
          <h3 className="m-0 text-sm font-semibold text-slate-700">
            {selected === todayISO && "Today · "}
            {selectedDate.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" })}
          </h3>
          {agenda.length > 0 ? (
            <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
              {agenda.map((e) => (
                <li key={e.id} className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: STATUS_COLOR[e.kind] }} aria-hidden="true" />
                  <span className="flex flex-col gap-0.5">
                    <span className="text-sm font-medium">{e.title}</span>
                    <span className="text-[13px] text-slate-500">
                      {e.time ? `${formatTime(e.time)} · ` : ""}
                      {e.detail}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-sm text-slate-500">Nothing on this day.</p>
          )}
        </div>
      </div>
    </Card>
  );
}
