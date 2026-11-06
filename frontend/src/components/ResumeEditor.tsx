import { useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent, type ReactNode } from "react";
import type { ResumeBullet, ResumeDoc, ResumeEntry, ResumeStyle } from "../types";
import { fieldKey, indexDoc, removedBullets, wordDiff } from "../lib/resumeDoc";

/** Used until a session has a style (sessions started before style extraction existed). */
export const DEFAULT_STYLE: ResumeStyle = {
  source: "text",
  font: "sans",
  fontName: "",
  nameSize: 17,
  headingSize: 11,
  bodySize: 10,
  nameAlign: "center",
  headingBold: true,
  headingUpper: true,
  headingRule: true,
  headingColor: "",
  dateAlign: "right",
  bullet: "•",
  contactSep: " | ",
  marginX: 0.6,
  marginY: 0.5,
};

const PAGE_WIDTH_PT = 612; // US Letter, 8.5in

type Props = {
  doc: ResumeDoc;
  original: ResumeDoc;
  style: ResumeStyle;
  /** Highlight what differs from the original resume. */
  showChanges: boolean;
  /** Field keys the user typed in themselves (shown in blue rather than green). */
  userKeys: Set<string>;
  /** Key of a field to open for editing right away (a line the user just added). */
  focusKey: string | null;
  onEdit: (key: string, text: string) => void;
  onAddLine: (entryId: string) => void;
  /** Bring back a removed line or entry. */
  onRestore: (id: string) => void;
};

/**
 * The tailored resume as a page that looks like the user's original (fonts, sizes,
 * alignment, rules, margins from the uploaded file). Click any line to edit it.
 *
 * Sizes are in container-width units, so the page wraps lines like the real
 * 8.5in page at any width, the way a PDF viewer zooms.
 */
export default function ResumeEditor({ doc, original, style, showChanges, userKeys, focusKey, onEdit, onAddLine, onRestore }: Props) {
  const orig = useMemo(() => indexDoc(original), [original]);
  const origEntries = useMemo(() => {
    const m = new Map<string, ResumeEntry>();
    for (const s of original.sections) for (const e of s.entries) m.set(e.id, e);
    return m;
  }, [original]);

  const pageRef = useRef<HTMLElement>(null);
  const [overflow, setOverflow] = useState(false);
  useLayoutEffect(() => {
    const el = pageRef.current;
    if (!el) return;
    const check = () => setOverflow(el.scrollHeight > el.clientWidth * (11 / 8.5) + 2);
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const size = (pt: number, minPx: number) => `max(${minPx}px, ${((pt / PAGE_WIDTH_PT) * 100).toFixed(3)}cqw)`;
  const fallback = style.font === "serif" ? 'Georgia, "Times New Roman", Times, serif' : 'Arial, Helvetica, sans-serif';
  const family = style.fontName ? `"${style.fontName.replace(/["\\;]/g, "")}", ${fallback}` : fallback;

  const pageStyle: CSSProperties = {
    fontFamily: family,
    fontSize: size(style.bodySize, 10),
    lineHeight: 1.26,
    padding: `${((style.marginY / 8.5) * 100).toFixed(2)}% ${((style.marginX / 8.5) * 100).toFixed(2)}%`,
    minHeight: "calc(100cqw * 11 / 8.5)",
  };

  const field = (key: string, value: string, opts: Partial<FieldProps> = {}) => (
    <Field
      key={key}
      fkey={key}
      value={value}
      before={orig.text.get(key)}
      isNew={!orig.text.has(key)}
      showChanges={showChanges}
      mine={userKeys.has(key)}
      autoEdit={focusKey === key}
      onCommit={(t) => onEdit(key, t)}
      label="Text"
      {...opts}
    />
  );

  const center = style.nameAlign === "center";
  const headingColor = style.headingColor || undefined;

  return (
    <div className="@container w-full">
      <article
        ref={pageRef}
        style={pageStyle}
        className="relative w-full bg-white text-black shadow-[0_1px_3px_rgba(15,23,42,0.12),0_8px_24px_rgba(15,23,42,0.08)]"
        aria-label="Tailored resume preview. Select any line to edit it."
      >
        {overflow && (
          <div
            aria-hidden
            className="pointer-events-none absolute right-0 left-0 border-t border-dashed border-amber-500"
            style={{ top: "calc(100cqw * 11 / 8.5)" }}
          >
            <span className="absolute right-2 -top-2.5 rounded bg-amber-50 px-1.5 font-sans text-[11px] font-medium text-amber-800">
              Page 1 ends here
            </span>
          </div>
        )}

        <header style={{ textAlign: center ? "center" : "left" }}>
          <div style={{ fontSize: size(style.nameSize, 18), fontWeight: 700, lineHeight: 1.2 }}>
            {field(fieldKey.name, doc.name, { label: "Name", placeholder: "Your name" })}
          </div>
          {doc.contact.length > 0 && (
            <div style={{ fontSize: size(style.bodySize - 0.8, 9), color: "#333" }}>
              {doc.contact.map((c, i) => (
                <span key={i}>
                  {i > 0 && <span aria-hidden>{style.contactSep}</span>}
                  {field(fieldKey.contact(i), c, { label: "Contact detail" })}
                </span>
              ))}
            </div>
          )}
        </header>

        {doc.sections.map((s) => {
          if (!s.entries.some((e) => e.heading || e.bullets.length) && !original.sections.some((o) => o.id === s.id)) return null;
          const lineList = s.kind === "summary" || s.kind === "skills";
          const removedEntries = showChanges
            ? (original.sections.find((o) => o.id === s.id)?.entries ?? []).filter((e) => !s.entries.some((x) => x.id === e.id))
            : [];
          return (
            <section key={s.id} style={{ marginTop: "0.55em" }}>
              <h3
                className="m-0"
                style={{
                  fontSize: size(style.headingSize, 11),
                  fontWeight: style.headingBold ? 700 : 400,
                  textTransform: style.headingUpper ? "uppercase" : undefined,
                  color: headingColor,
                  borderBottom: style.headingRule ? `0.6pt solid ${style.headingColor || "#888"}` : undefined,
                  paddingBottom: style.headingRule ? "0.1em" : undefined,
                  marginBottom: "0.25em",
                  lineHeight: 1.27,
                }}
              >
                {field(fieldKey.title(s.id), s.title, { label: "Section title" })}
              </h3>

              {s.entries.map((e) => {
                const isNewEntry = !origEntries.has(e.id);
                const ghosts = showChanges ? removedBullets(origEntries.get(e.id), e) : new Map<string, ResumeBullet[]>();
                const ghostAt = (after: string) =>
                  (ghosts.get(after) ?? []).map((b) => (
                    <Ghost key={b.id} glyph={lineList ? "" : style.bullet} text={b.text} onRestore={() => onRestore(b.id)} />
                  ));
                return (
                  <div
                    key={e.id}
                    className={`group/entry relative ${isNewEntry && showChanges ? "rounded-sm bg-emerald-50 outline outline-1 outline-emerald-200" : ""}`}
                    style={{ marginTop: "0.25em" }}
                  >
                    {(e.heading || e.dates || orig.text.get(fieldKey.heading(e.id))) && (
                      <div className={style.dateAlign === "right" ? "flex items-baseline justify-between gap-4" : ""}>
                        <span style={{ fontWeight: 700 }}>{field(fieldKey.heading(e.id), e.heading, { label: "Heading", placeholder: "Role — Organization" })}</span>
                        {(e.dates || orig.text.get(fieldKey.dates(e.id))) &&
                          (style.dateAlign === "right" ? (
                            <span className="shrink-0 text-right">{field(fieldKey.dates(e.id), e.dates, { label: "Dates" })}</span>
                          ) : (
                            <span>
                              <span aria-hidden>{style.contactSep}</span>
                              {field(fieldKey.dates(e.id), e.dates, { label: "Dates" })}
                            </span>
                          ))}
                      </div>
                    )}
                    {(e.subheading || orig.text.get(fieldKey.subheading(e.id))) && (
                      <div style={{ color: "#444" }}>{field(fieldKey.subheading(e.id), e.subheading, { label: "Subheading" })}</div>
                    )}

                    {lineList ? (
                      <div>
                        {ghostAt("")}
                        {e.bullets.map((b) => (
                          <div key={b.id}>
                            {field(b.id, b.text, { label: "Line", block: true })}
                            {ghostAt(b.id)}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <ul className="m-0 list-none p-0">
                        {ghostAt("")}
                        {e.bullets.map((b) => (
                          <li key={b.id}>
                            <div className="flex">
                              <span aria-hidden className="shrink-0 text-center" style={{ width: "1.1em", marginLeft: "0.2em" }}>
                                {style.bullet}
                              </span>
                              {field(b.id, b.text, { label: "Bullet", block: true })}
                            </div>
                            {ghostAt(b.id)}
                          </li>
                        ))}
                      </ul>
                    )}

                    <button
                      type="button"
                      onClick={() => onAddLine(e.id)}
                      className="mt-0.5 cursor-pointer rounded border border-dashed border-slate-300 bg-white px-1.5 font-sans text-[11px] leading-5 font-medium text-slate-500 opacity-0 transition-opacity group-focus-within/entry:opacity-100 group-hover/entry:opacity-100 hover:border-blue-400 hover:text-blue-700 focus-visible:opacity-100 [@media(hover:none)]:opacity-100"
                    >
                      + Add {lineList ? "line" : "bullet"}
                    </button>
                  </div>
                );
              })}

              {removedEntries.map((e) => (
                <div key={e.id} className="mt-1 flex items-baseline gap-2">
                  <span className="text-red-700 line-through decoration-red-500" style={{ fontWeight: 700 }}>
                    {e.heading || e.bullets[0]?.text || "Removed entry"}
                  </span>
                  <RestoreButton onClick={() => onRestore(e.id)} />
                </div>
              ))}
            </section>
          );
        })}
      </article>
    </div>
  );
}

// ---- one editable field ------------------------------------------------------------------

type FieldProps = {
  fkey: string;
  value: string;
  /** Text in the original resume (undefined: the field is new). */
  before: string | undefined;
  isNew: boolean;
  showChanges: boolean;
  mine: boolean;
  autoEdit: boolean;
  label: string;
  placeholder?: string;
  block?: boolean;
  onCommit: (text: string) => void;
};

function Field({ value, before, isNew, showChanges, mine, autoEdit, label, placeholder, block, onCommit }: FieldProps) {
  const [editing, setEditing] = useState(autoEdit);
  const ref = useRef<HTMLSpanElement>(null);
  const cancelled = useRef(false);

  useLayoutEffect(() => {
    if (!editing || !ref.current) return;
    const el = ref.current;
    el.textContent = value;
    el.focus();
    const range = document.createRange();
    range.selectNodeContents(el);
    range.collapse(false);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing]);

  const display = block ? "block" : "inline";
  const base = `${block ? "min-w-0 flex-1" : ""} rounded-[2px] outline-offset-1`;

  if (editing) {
    const finish = () => {
      const text = (ref.current?.textContent ?? "").replace(/\s*\n\s*/g, " ");
      setEditing(false);
      // An emptied line is always reported, so a just-added line left blank goes away.
      if (!cancelled.current && (text !== value || !text.trim())) onCommit(text);
      cancelled.current = false;
    };
    const onKeyDown = (e: KeyboardEvent<HTMLSpanElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        ref.current?.blur();
      } else if (e.key === "Escape") {
        e.preventDefault();
        cancelled.current = true;
        ref.current?.blur();
      }
    };
    return (
      <span
        key="editing" // a different element from the read-only view, so React never mixes the two
        ref={ref}
        role="textbox"
        aria-label={label}
        aria-multiline={false}
        contentEditable="plaintext-only"
        suppressContentEditableWarning
        spellCheck
        onBlur={finish}
        onKeyDown={onKeyDown}
        onPaste={(e) => {
          e.preventDefault();
          document.execCommand("insertText", false, e.clipboardData.getData("text/plain").replace(/\s*\n\s*/g, " "));
        }}
        className={`${base} cursor-text bg-white outline-2 outline-blue-600`}
        style={{ display, whiteSpace: "pre-wrap" }}
      />
    );
  }

  let content: ReactNode = value || <span className="text-slate-400 italic">{placeholder ?? "Empty"}</span>;
  const changed = showChanges && value && (isNew || (before !== undefined && before !== value));
  const addCls = mine ? "bg-blue-100 text-blue-950" : "bg-emerald-100 text-emerald-950";
  if (changed) {
    content =
      isNew || !before ? (
        <span className={addCls}>{value}</span>
      ) : (
        wordDiff(before, value).map((p, i) =>
          p.kind === "same" ? (
            <span key={i}>{p.text}</span>
          ) : p.kind === "add" ? (
            <span key={i} className={addCls}>{p.text}</span>
          ) : (
            <del key={i} className="text-red-700 decoration-red-500">{p.text}</del>
          ),
        )
      );
  }

  return (
    <span
      key="view"
      tabIndex={0}
      role="textbox"
      aria-readonly={false}
      aria-label={`${label}: ${value || "empty"}. Press Enter to edit.`}
      onClick={() => setEditing(true)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === "F2") {
          e.preventDefault();
          setEditing(true);
        }
      }}
      className={`${base} cursor-text hover:bg-slate-50 hover:outline hover:outline-1 hover:outline-blue-300 focus-visible:outline-2 focus-visible:outline-blue-600`}
      style={{ display }}
    >
      {content}
    </span>
  );
}

function Ghost({ glyph, text, onRestore }: { glyph: string; text: string; onRestore: () => void }) {
  return (
    <div className="flex items-baseline">
      {glyph && (
        <span aria-hidden className="shrink-0 text-center text-red-400" style={{ width: "1.1em", marginLeft: "0.2em" }}>
          {glyph}
        </span>
      )}
      <del className="min-w-0 flex-1 text-red-700 decoration-red-500">{text}</del>
      <RestoreButton onClick={onRestore} />
    </div>
  );
}

function RestoreButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="ml-2 shrink-0 cursor-pointer rounded border border-slate-300 bg-white px-1.5 font-sans text-[11px] leading-5 font-medium text-slate-600 hover:border-blue-400 hover:text-blue-700"
    >
      Restore
    </button>
  );
}
