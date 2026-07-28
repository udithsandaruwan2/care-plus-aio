import { Link } from 'react-router-dom';

export function BackLink({
  to,
  children = 'Back',
}: {
  to: string;
  children?: string;
}) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1 rounded-full border border-hair px-3 py-1 text-xs text-muted transition hover:border-cyan hover:text-cyan"
    >
      ← {children}
    </Link>
  );
}
