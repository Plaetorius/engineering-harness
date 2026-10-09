type Item = { id: string; ownerId: string; body: string };
export function getItem(id: string, requestUser: { id: string } | null, items: Item[]) {
  if (!requestUser) return { status: 401 };
  const item = items.find((row) => row.id === id);
  return item ? { status: 200, body: item.body } : { status: 404 };
}
