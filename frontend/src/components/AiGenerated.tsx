import { HiOutlineSparkles } from "react-icons/hi2";

interface Props {
  children: React.ReactNode;
  label?: string;
  className?: string;
}

export default function AiGenerated({ children, label = "AI-generated", className = "" }: Props) {
  return (
    <div className={`relative ${className}`}>
      <div className="flex items-center gap-1 mb-1">
        <HiOutlineSparkles className="w-3 h-3 text-violet-500" />
        <span className="text-[10px] font-sans font-semibold uppercase tracking-wider text-violet-500">{label}</span>
      </div>
      <div className="border-l-2 border-violet-200 pl-3">
        {children}
      </div>
    </div>
  );
}
