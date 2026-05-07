import { useState } from "react";

interface Props {
  text: string;
  children: React.ReactNode;
}

export default function Tooltip({ text, children }: Props) {
  const [show, setShow] = useState(false);

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-xs font-sans text-stone-100 bg-stone-800 rounded shadow-lg whitespace-normal w-64 leading-relaxed pointer-events-none">
          {text}
        </span>
      )}
    </span>
  );
}
