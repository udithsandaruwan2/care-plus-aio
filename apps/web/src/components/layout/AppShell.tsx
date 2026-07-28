import { Outlet } from 'react-router-dom';
import { AtmosphereShell } from '../AtmosphereShell';
import { AppTopBar } from './AppTopBar';

export function AppShell() {
  return (
    <AtmosphereShell>
      <AppTopBar />
      <main className="mx-auto flex min-h-[calc(100%-4rem)] w-full max-w-6xl flex-col px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>
    </AtmosphereShell>
  );
}
