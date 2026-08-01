import { Outlet } from 'react-router-dom';
import { AtmosphereShell } from '../AtmosphereShell';
import { SkipLink } from '../../a11y/SkipLink';
import { AppTopBar } from './AppTopBar';

export function AppShell() {
  return (
    <AtmosphereShell>
      <SkipLink />
      <AppTopBar />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex min-h-[calc(100%-4rem)] w-full max-w-6xl flex-col px-4 py-6 outline-none sm:px-6 sm:py-8"
      >
        <Outlet />
      </main>
    </AtmosphereShell>
  );
}
