/** App-wide navigate binder for non-React modules (voice action executor). */

type NavigateFn = (to: string, opts?: { replace?: boolean }) => void;

let navigateFn: NavigateFn | null = null;

export function bindAppNavigate(fn: NavigateFn | null): void {
  navigateFn = fn;
}

export function appNavigate(to: string, opts?: { replace?: boolean }): void {
  if (navigateFn) {
    navigateFn(to, opts);
    return;
  }
  if (opts?.replace) {
    window.location.replace(to);
  } else {
    window.location.assign(to);
  }
}
