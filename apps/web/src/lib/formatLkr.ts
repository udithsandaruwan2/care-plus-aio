/** Format LKR amounts for display. */
export function formatLkr(value: string | number): string {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return String(value);
  return `LKR ${n.toLocaleString('en-LK', { minimumFractionDigits: 0 })}`;
}
