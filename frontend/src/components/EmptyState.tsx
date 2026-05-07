interface Props {
  message: string;
}

export default function EmptyState({ message }: Props) {
  return (
    <p className="text-sm font-sans italic text-stone-400 py-4">{message}</p>
  );
}
