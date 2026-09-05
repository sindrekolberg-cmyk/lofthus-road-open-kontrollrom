export function signed(n: number) {
  if (n > 0) return `+${n}`;
  if (n < 0) return `${n}`;
  return "–";
}

export function moveLabel(n: number, provisional: boolean) {
  if (!n) return "–";
  const arrow = n > 0 ? "↑" : "↓";
  const abs = Math.abs(n);
  return provisional ? `${arrow}${abs}` : `${arrow}${abs}`;
}

export function place(n: number | null | undefined) {
  if (!n) return "–";
  return `${n}.`;
}
