/** Skip link for keyboard users — place as first focusable in the shell. */
export function SkipLink({ href = '#main-content' }: { href?: string }) {
  return (
    <a
      href={href}
      className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-cyan focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-void"
    >
      Skip to main content
    </a>
  );
}
