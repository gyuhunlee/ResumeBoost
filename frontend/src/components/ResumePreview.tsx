import { useEffect, useRef, useState } from "react";
import { supabase } from "../lib/supabase";

// A US Letter page: 8.5 × 11 in. At 96 CSS px/in that's 816 px wide.
const PAGE_WIDTH_PX = 816;

type Props = {
  /** Path in the private "resumes" storage bucket. */
  path: string | null;
  fileName: string | null;
  /** Extracted text, shown as a plain page if the file can't be rendered. */
  fallbackText: string;
};

/**
 * A first-page thumbnail, like the tiles on the Google Docs home screen.
 * The PDF/DOCX renderers are loaded only when a preview is shown, so they
 * don't add to the size of every other page.
 */
export default function ResumePreview({ path, fileName, fallbackText }: Props) {
  const frameRef = useRef<HTMLDivElement>(null);
  const pageRef = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "fallback">("loading");
  const [scale, setScale] = useState(0.25);

  useEffect(() => {
    const page = pageRef.current;
    if (!path || !page) return setState("fallback");
    let cancelled = false;
    setState("loading");
    page.replaceChildren();

    (async () => {
      const { data: blob, error } = await supabase.storage.from("resumes").download(path);
      if (error || !blob) throw error ?? new Error("download failed");
      const isPdf = /\.pdf$/i.test(fileName ?? path) || blob.type === "application/pdf";
      if (isPdf) await renderPdf(blob, page, () => cancelled);
      else await renderDocx(blob, page);
      if (!cancelled) setState("ready");
    })().catch(() => !cancelled && setState("fallback"));

    return () => {
      cancelled = true;
    };
  }, [path, fileName]);

  // Scale the full-size page down to the tile width, and keep it scaled on resize.
  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const fit = () => setScale(frame.clientWidth / PAGE_WIDTH_PX);
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(frame);
    return () => ro.disconnect();
  }, []);

  return (
    <div
      ref={frameRef}
      className="relative aspect-[8.5/11] w-full overflow-hidden bg-white"
      aria-label={`Preview of ${fileName ?? "resume"}`}
      role="img"
    >
      <div
        ref={pageRef}
        className="absolute top-0 left-0 origin-top-left [&_canvas]:block [&_canvas]:w-full"
        style={{ width: PAGE_WIDTH_PX, transform: `scale(${scale})` }}
        hidden={state === "fallback"}
      />
      {state === "fallback" && (
        <div
          className="absolute top-0 left-0 origin-top-left px-[72px] py-[64px] font-serif text-[15px] leading-relaxed whitespace-pre-wrap text-slate-800"
          style={{ width: PAGE_WIDTH_PX, transform: `scale(${scale})` }}
        >
          {fallbackText || "No preview available"}
        </div>
      )}
      {state === "loading" && (
        <div className="absolute inset-0 flex flex-col gap-2.5 p-[12%]" aria-hidden="true">
          {[60, 90, 80, 95, 70, 85, 50].map((w, i) => (
            <div key={i} className="h-2 animate-pulse rounded bg-slate-100" style={{ width: `${w}%` }} />
          ))}
        </div>
      )}
    </div>
  );
}

async function renderPdf(blob: Blob, target: HTMLElement, cancelled: () => boolean) {
  const [pdfjs, worker] = await Promise.all([
    import("pdfjs-dist"),
    import("pdfjs-dist/build/pdf.worker.min.mjs?url"),
  ]);
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
  const doc = await pdfjs.getDocument({ data: new Uint8Array(await blob.arrayBuffer()) }).promise;
  try {
    const first = await doc.getPage(1);
    // Render at page width × 2 so the shrunken thumbnail stays sharp on retina screens.
    const base = first.getViewport({ scale: 1 });
    const viewport = first.getViewport({ scale: (PAGE_WIDTH_PX / base.width) * 2 });
    const canvas = document.createElement("canvas");
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    await first.render({ canvasContext: canvas.getContext("2d")!, viewport }).promise;
    if (!cancelled()) target.replaceChildren(canvas);
  } finally {
    void doc.destroy();
  }
}

async function renderDocx(blob: Blob, target: HTMLElement) {
  const { renderAsync } = await import("docx-preview");
  await renderAsync(blob, target, undefined, {
    inWrapper: false, // no grey "desk" around the page
    breakPages: true,
    ignoreLastRenderedPageBreak: false,
    renderHeaders: true,
    renderFooters: true,
  });
  // Show only the first page.
  const pages = target.querySelectorAll<HTMLElement>("section.docx");
  pages.forEach((p, i) => {
    if (i > 0) p.remove();
    else {
      p.style.margin = "0";
      p.style.boxShadow = "none";
    }
  });
}
