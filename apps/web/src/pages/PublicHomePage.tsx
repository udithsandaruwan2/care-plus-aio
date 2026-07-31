import { Link } from 'react-router-dom';
import { brand } from '@care-plus/ui-tokens';
import { Button } from '../components/ui/Button';
import { useLocale } from '../i18n/LocaleProvider';

export function PublicHomePage() {
  const { t } = useLocale();

  return (
    <div>
      <section className="relative -mx-5 overflow-hidden sm:-mx-8">
        <div
          className="absolute inset-0 bg-[radial-gradient(ellipse_at_20%_20%,color-mix(in_oklab,var(--cp-cyan)_22%,transparent),transparent_55%),radial-gradient(ellipse_at_80%_10%,color-mix(in_oklab,var(--cp-violet)_18%,transparent),transparent_50%),linear-gradient(180deg,color-mix(in_oklab,var(--cp-panel)_40%,transparent),transparent)]"
          aria-hidden
        />
        <div className="relative mx-auto flex min-h-[78vh] max-w-6xl flex-col justify-center px-5 py-16 sm:px-8 sm:py-20">
          <p className="font-display text-4xl tracking-tight text-mist sm:text-6xl">{brand.name}</p>
          <h1 className="mt-4 max-w-2xl font-display text-2xl leading-snug text-mist/95 sm:text-3xl">
            {t('home.headline')}
          </h1>
          <p className="mt-4 max-w-xl text-base text-muted">{t('home.support')}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/caregivers">
              <Button className="px-6">{t('action.browseCaregivers')}</Button>
            </Link>
            <Link to="/register">
              <Button tone="ghost" className="px-6">
                {t('action.getStarted')}
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="mt-16">
        <h2 className="font-display text-2xl text-mist">{t('home.howTitle')}</h2>
        <p className="mt-2 max-w-xl text-sm text-muted">{t('home.howSubtitle')}</p>
        <ol className="mt-8 grid gap-8 sm:grid-cols-3">
          <li>
            <p className="font-display text-cyan">01</p>
            <p className="mt-2 font-display text-lg text-mist">{t('home.step1Title')}</p>
            <p className="mt-1 text-sm text-muted">{t('home.step1Body')}</p>
          </li>
          <li>
            <p className="font-display text-cyan">02</p>
            <p className="mt-2 font-display text-lg text-mist">{t('home.step2Title')}</p>
            <p className="mt-1 text-sm text-muted">{t('home.step2Body')}</p>
          </li>
          <li>
            <p className="font-display text-cyan">03</p>
            <p className="mt-2 font-display text-lg text-mist">{t('home.step3Title')}</p>
            <p className="mt-1 text-sm text-muted">{t('home.step3Body')}</p>
          </li>
        </ol>
      </section>

      <section id="about" className="mt-20">
        <h2 className="font-display text-2xl text-mist">{t('home.whyTitle')}</h2>
        <p className="mt-2 max-w-xl text-sm text-muted">{t('home.whySubtitle')}</p>
        <div className="mt-8 grid gap-10 md:grid-cols-3">
          <div>
            <p className="font-display text-lg text-mist">{t('home.why1Title')}</p>
            <p className="mt-2 text-sm text-muted">{t('home.why1Body')}</p>
          </div>
          <div>
            <p className="font-display text-lg text-mist">{t('home.why2Title')}</p>
            <p className="mt-2 text-sm text-muted">{t('home.why2Body')}</p>
          </div>
          <div>
            <p className="font-display text-lg text-mist">{t('home.why3Title')}</p>
            <p className="mt-2 text-sm text-muted">{t('home.why3Body')}</p>
          </div>
        </div>
      </section>

      <section id="testimonials" className="mt-20">
        <h2 className="font-display text-2xl text-mist">{t('home.storiesTitle')}</h2>
        <p className="mt-2 text-sm text-muted">{t('home.storiesSubtitle')}</p>
        <div className="mt-8 space-y-8">
          <blockquote className="border-l-2 border-cyan/40 pl-5">
            <p className="text-mist">{t('home.quote1')}</p>
            <footer className="mt-2 text-xs text-muted">{t('home.quote1By')}</footer>
          </blockquote>
          <blockquote className="border-l-2 border-cyan/40 pl-5">
            <p className="text-mist">{t('home.quote2')}</p>
            <footer className="mt-2 text-xs text-muted">{t('home.quote2By')}</footer>
          </blockquote>
          <blockquote className="border-l-2 border-cyan/40 pl-5">
            <p className="text-mist">{t('home.quote3')}</p>
            <footer className="mt-2 text-xs text-muted">{t('home.quote3By')}</footer>
          </blockquote>
        </div>
      </section>

      <section className="mt-20 mb-4">
        <h2 className="font-display text-2xl text-mist">{t('home.helpTitle')}</h2>
        <p className="mt-2 max-w-xl text-sm text-muted">{t('home.helpBody')}</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/contact">
            <Button>{t('action.contactUs')}</Button>
          </Link>
          <Link to="/caregivers">
            <Button tone="ghost">{t('action.exploreCaregivers')}</Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
