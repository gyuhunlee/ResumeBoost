/**
 * The resume shown in the review step, built in the browser so toggling a change
 * or typing in the preview updates instantly:
 *
 *   original  --applyChanges(decisions)-->  base  --applyEdits(edits)-->  doc
 *
 * applyChanges mirrors apply_changes in backend/app/tailor/agent.py; keep them in step.
 * Every line keeps its id from the original (added lines get new ids), which is how
 * the preview highlights what changed and how the server edits a .docx in place.
 */
import type {
  ResumeBullet,
  ResumeDoc,
  ResumeEntry,
  TailorAction,
  TailorChange,
} from "../types";

export type Decision = { action: TailorAction; text?: string };
export type Decisions = Record<string, Decision>;

/** The user's own edits in the preview, on top of the changes they kept. */
export type DocEdits = {
  /** field key -> text. "" on a bullet removes it. Keys: see fieldKey. */
  text: Record<string, string>;
  /** entry id -> lines the user added at the end of that entry. */
  added: Record<string, ResumeBullet[]>;
};

export const emptyEdits = (): DocEdits => ({ text: {}, added: {} });

/** Keys for every editable field. Bullets use their own id. */
export const fieldKey = {
  name: "name",
  contact: (i: number) => `contact.${i}`,
  title: (sectionId: string) => `${sectionId}.title`,
  heading: (entryId: string) => `${entryId}.heading`,
  subheading: (entryId: string) => `${entryId}.subheading`,
  dates: (entryId: string) => `${entryId}.dates`,
};

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

export function lines(text: string): string[] {
  return text
    .split("\n")
    .map((l) => l.replace(/^[\s•\-\t]+|[\s•\-\t]+$/g, ""))
    .filter(Boolean);
}

const ORDER: Record<TailorChange["kind"], number> = { add_entry: 0, add_bullets: 1, rewrite: 2, remove: 3, reorder: 4 };

function findEntry(doc: ResumeDoc, id: string): ResumeEntry | undefined {
  for (const s of doc.sections) for (const e of s.entries) if (e.id === id) return e;
  return undefined;
}

function findBullet(doc: ResumeDoc, id: string): ResumeBullet | undefined {
  for (const s of doc.sections) for (const e of s.entries) for (const b of e.bullets) if (b.id === id) return b;
  return undefined;
}

function sortBy<T>(items: T[], order: string[], key: (x: T) => string): T[] {
  const rank = new Map(order.map((id, n) => [id, n]));
  return items
    .map((x, i) => ({ x, i }))
    .sort((a, b) => (rank.get(key(a.x)) ?? order.length) - (rank.get(key(b.x)) ?? order.length) || a.i - b.i)
    .map((p) => p.x);
}

/** original + the changes the user kept. A change missing from `decisions` counts as kept. */
export function applyChanges(original: ResumeDoc, changes: TailorChange[], decisions: Decisions): ResumeDoc {
  const doc = clone(original);
  const sorted = [...changes].sort((a, b) => ORDER[a.kind] - ORDER[b.kind]);
  for (const ch of sorted) {
    const d = decisions[ch.id] ?? { action: "accept" };
    if (d.action === "reject") continue;
    const edited = d.action === "edit" ? (d.text ?? "").trim() : "";
    const p = ch.payload ?? {};

    if (ch.kind === "add_entry") {
      const sec = doc.sections.find((s) => s.id === ch.targetId);
      const raw = p.entry as ResumeEntry | undefined;
      if (sec && raw) {
        const entry: ResumeEntry = clone({
          id: raw.id,
          heading: raw.heading ?? "",
          subheading: raw.subheading ?? "",
          dates: raw.dates ?? "",
          bullets: raw.bullets ?? [],
        });
        if (edited) entry.bullets = lines(edited).map((t, i) => ({ id: `${entry.id}b${i + 1}`, text: t }));
        const pos = typeof p.position === "number" ? p.position : sec.entries.length;
        sec.entries.splice(pos, 0, entry);
      }
    } else if (ch.kind === "add_bullets") {
      const entry = findEntry(doc, ch.targetId);
      if (entry) {
        const texts = edited ? lines(edited) : ((p.bullets as string[] | undefined) ?? lines(ch.after));
        entry.bullets.push(...texts.map((t, i) => ({ id: `${ch.targetId}+${ch.id}.${i + 1}`, text: t })));
      }
    } else if (ch.kind === "rewrite") {
      const b = findBullet(doc, ch.targetId);
      if (b) b.text = edited || ch.after;
    } else if (ch.kind === "remove") {
      for (const s of doc.sections) {
        s.entries = s.entries.filter((e) => e.id !== ch.targetId);
        for (const e of s.entries) e.bullets = e.bullets.filter((b) => b.id !== ch.targetId);
      }
    } else if (ch.kind === "reorder") {
      const order = (p.order as string[] | undefined) ?? [];
      const sec = doc.sections.find((s) => s.id === ch.targetId);
      if (sec) sec.entries = sortBy(sec.entries, order, (e) => e.id);
      else {
        const entry = findEntry(doc, ch.targetId);
        if (entry) entry.bullets = sortBy(entry.bullets, order, (b) => b.id);
      }
    }
  }
  return doc;
}

/**
 * base + the user's typing. Bullets set to "" disappear. A line the user just added and
 * hasn't typed in yet stays (so it can be shown and edited); the server drops it if still empty.
 */
export function applyEdits(base: ResumeDoc, edits: DocEdits): ResumeDoc {
  const doc = clone(base);
  const t = edits.text;
  const drafts = new Set(Object.values(edits.added).flat().filter((b) => !(b.id in t)).map((b) => b.id));
  const pick = (key: string, value: string) => (key in t ? t[key] : value);
  doc.name = pick(fieldKey.name, doc.name);
  doc.contact = doc.contact.map((c, i) => pick(fieldKey.contact(i), c));
  for (const s of doc.sections) {
    s.title = pick(fieldKey.title(s.id), s.title);
    for (const e of s.entries) {
      e.heading = pick(fieldKey.heading(e.id), e.heading);
      e.subheading = pick(fieldKey.subheading(e.id), e.subheading);
      e.dates = pick(fieldKey.dates(e.id), e.dates);
      e.bullets = [...e.bullets, ...(edits.added[e.id] ?? [])]
        .map((b) => ({ ...b, text: pick(b.id, b.text) }))
        .filter((b) => b.text.trim() !== "" || drafts.has(b.id));
    }
  }
  return doc;
}

/** Does this edit key belong to something the change created or changed? */
export function keyTouchedBy(change: TailorChange, key: string): boolean {
  const id = change.targetId;
  switch (change.kind) {
    case "rewrite":
      return key === id;
    case "add_bullets":
      return key.startsWith(`${id}+${change.id}.`);
    case "add_entry": {
      const entryId = String((change.payload?.entry as ResumeEntry | undefined)?.id ?? "");
      return !!entryId && (key === entryId || key.startsWith(`${entryId}.`) || key.startsWith(`${entryId}b`) || key.startsWith(`${entryId}+`));
    }
    default:
      return false;
  }
}

/** When the user flips a change, their typing on top of the old version no longer applies. */
export function dropEditsFor(edits: DocEdits, change: TailorChange): DocEdits {
  const text = Object.fromEntries(Object.entries(edits.text).filter(([k]) => !keyTouchedBy(change, k)));
  const added = Object.fromEntries(Object.entries(edits.added).filter(([k]) => !keyTouchedBy(change, k)));
  return { text, added };
}

export function hasEdits(edits: DocEdits): boolean {
  return Object.keys(edits.text).length > 0 || Object.values(edits.added).some((a) => a.length > 0);
}

// ---- comparing with the original -------------------------------------------------------

/** Every field of a resume by key, plus which entries and bullets exist. */
export type FieldIndex = { text: Map<string, string>; entries: Set<string>; bullets: Set<string> };

export function indexDoc(doc: ResumeDoc): FieldIndex {
  const text = new Map<string, string>();
  const entries = new Set<string>();
  const bullets = new Set<string>();
  text.set(fieldKey.name, doc.name);
  doc.contact.forEach((c, i) => text.set(fieldKey.contact(i), c));
  for (const s of doc.sections) {
    text.set(fieldKey.title(s.id), s.title);
    for (const e of s.entries) {
      entries.add(e.id);
      text.set(fieldKey.heading(e.id), e.heading);
      text.set(fieldKey.subheading(e.id), e.subheading);
      text.set(fieldKey.dates(e.id), e.dates);
      for (const b of e.bullets) {
        bullets.add(b.id);
        text.set(b.id, b.text);
      }
    }
  }
  return { text, entries, bullets };
}

/** Number of lines that differ from the original (changed, added or removed). */
export function countDiffs(original: ResumeDoc, doc: ResumeDoc): number {
  const a = indexDoc(original);
  const b = indexDoc(doc);
  let n = 0;
  for (const [k, v] of b.text) if (v && a.text.get(k) !== v) n++;
  for (const id of a.bullets) if (!b.bullets.has(id)) n++;
  return n;
}

/**
 * Where removed original bullets sat, so the preview can show them struck through in place.
 * Returns, per entry, a map from "after this bullet id" ("" = at the top) to the removed bullets.
 */
export function removedBullets(originalEntry: ResumeEntry | undefined, entry: ResumeEntry): Map<string, ResumeBullet[]> {
  const out = new Map<string, ResumeBullet[]>();
  if (!originalEntry) return out;
  const present = new Set(entry.bullets.map((b) => b.id));
  let anchor = "";
  for (const b of originalEntry.bullets) {
    if (present.has(b.id)) {
      anchor = b.id;
      continue;
    }
    out.set(anchor, [...(out.get(anchor) ?? []), b]);
  }
  return out;
}

export type DiffPart = { kind: "same" | "add" | "del"; text: string };

/** Word-level diff (LCS over words and the spaces between them). */
export function wordDiff(before: string, after: string): DiffPart[] {
  const a = before.split(/(\s+)/).filter((x) => x !== "");
  const b = after.split(/(\s+)/).filter((x) => x !== "");
  if (a.length * b.length > 40_000) {
    return [{ kind: "del", text: before }, { kind: "add", text: after }];
  }
  const dp: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);

  const parts: DiffPart[] = [];
  const push = (kind: DiffPart["kind"], text: string) => {
    const last = parts[parts.length - 1];
    if (last && last.kind === kind) last.text += text;
    else parts.push({ kind, text });
  };
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      push("same", a[i]);
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) push("del", a[i++]);
    else push("add", b[j++]);
  }
  while (i < a.length) push("del", a[i++]);
  while (j < b.length) push("add", b[j++]);

  // A lone space between two changes reads better as part of the change.
  for (let k = 1; k < parts.length - 1; k++) {
    if (parts[k].kind === "same" && /^\s+$/.test(parts[k].text) && parts[k - 1].kind !== "same" && parts[k + 1].kind !== "same") {
      parts[k].kind = parts[k + 1].kind;
    }
  }
  return parts.reduce<DiffPart[]>((acc, p) => {
    const last = acc[acc.length - 1];
    if (last && last.kind === p.kind) last.text += p.text;
    else acc.push({ ...p });
    return acc;
  }, []);
}

/** A stable string for "has the document changed since the last ATS check?". */
export const docKey = (doc: ResumeDoc) => JSON.stringify(doc);
