export function SaveButton({ onSave }: { onSave: () => void }) {
  return <button className="rounded px-3 py-2" onClick={onSave}>Save</button>;
}
