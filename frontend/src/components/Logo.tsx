import { Link } from "react-router";
import { DocCheckIcon } from "./Icons";

export default function Logo({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="flex items-center gap-2.5 text-slate-900 no-underline">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-700 text-white">
        <DocCheckIcon size={18} />
      </span>
      <span className="text-lg font-bold">ResumeBoost</span>
    </Link>
  );
}
