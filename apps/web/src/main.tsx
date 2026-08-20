import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import './index.css';
import { LocaleProvider } from './i18n/LocaleProvider';
import { ThemeProvider } from './theme/ThemeProvider';
import { registerCarePlusSW } from './pwa/registerSW';

void registerCarePlusSW();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <LocaleProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </LocaleProvider>
    </ThemeProvider>
  </StrictMode>,
);
