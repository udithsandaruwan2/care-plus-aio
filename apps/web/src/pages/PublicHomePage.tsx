import { Link } from 'react-router-dom';
import { brand } from '@care-plus/ui-tokens';
import { Button } from '../components/ui/Button';

export function PublicHomePage() {
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
            Trusted home care for families across Sri Lanka.
          </h1>
          <p className="mt-4 max-w-xl text-base text-muted">
            Find verified caregivers in Colombo and beyond — clear schedules, transparent packages,
            and guided support from Serah in English, Sinhala, or Tamil.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/caregivers">
              <Button className="px-6">Browse caregivers</Button>
            </Link>
            <Link to="/register">
              <Button tone="ghost" className="px-6">
                Get started
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="mt-16">
        <h2 className="font-display text-2xl text-mist">How booking works</h2>
        <p className="mt-2 max-w-xl text-sm text-muted">
          Three clear steps from discovery to coordinated care.
        </p>
        <ol className="mt-8 grid gap-8 sm:grid-cols-3">
          <li>
            <p className="font-display text-cyan">01</p>
            <p className="mt-2 font-display text-lg text-mist">Explore</p>
            <p className="mt-1 text-sm text-muted">
              Filter by language, specialty, trust, and weekly availability.
            </p>
          </li>
          <li>
            <p className="font-display text-cyan">02</p>
            <p className="mt-2 font-display text-lg text-mist">Shortlist</p>
            <p className="mt-1 text-sm text-muted">
              Open a profile, review slots and reviews, then start a booking.
            </p>
          </li>
          <li>
            <p className="font-display text-cyan">03</p>
            <p className="mt-2 font-display text-lg text-mist">Coordinate</p>
            <p className="mt-1 text-sm text-muted">
              Sign in, message your caregiver, and complete checkout when ready.
            </p>
          </li>
        </ol>
      </section>

      <section id="about" className="mt-20">
        <h2 className="font-display text-2xl text-mist">Why families choose Care Plus</h2>
        <p className="mt-2 max-w-xl text-sm text-muted">
          Built for Sri Lankan households who need reliable, respectful home care.
        </p>
        <div className="mt-8 grid gap-10 md:grid-cols-3">
          <div>
            <p className="font-display text-lg text-mist">Verified profiles</p>
            <p className="mt-2 text-sm text-muted">
              Certifications, trust scores, reviews, and published weekly slots.
            </p>
          </div>
          <div>
            <p className="font-display text-lg text-mist">AI guidance, your decision</p>
            <p className="mt-2 text-sm text-muted">
              Serah helps you discover matches faster — your family stays in control.
            </p>
          </div>
          <div>
            <p className="font-display text-lg text-mist">Island-wide support</p>
            <p className="mt-2 text-sm text-muted">
              English, Sinhala, and Tamil — from Colombo to Kandy, Galle, and beyond.
            </p>
          </div>
        </div>
      </section>

      <section id="testimonials" className="mt-20">
        <h2 className="font-display text-2xl text-mist">What families say</h2>
        <p className="mt-2 text-sm text-muted">Early stories from Care Plus users.</p>
        <div className="mt-8 space-y-8">
          <blockquote className="border-l-2 border-cyan/40 pl-5">
            <p className="text-mist">
              “We found a dementia caregiver for my mother in less than a day. The process felt safe.”
            </p>
            <footer className="mt-2 text-xs text-muted">Family in Colombo 07</footer>
          </blockquote>
          <blockquote className="border-l-2 border-cyan/40 pl-5">
            <p className="text-mist">
              “Weekly slots and clear pricing helped us plan post-surgery care without confusion.”
            </p>
            <footer className="mt-2 text-xs text-muted">Family in Kandy</footer>
          </blockquote>
          <blockquote className="border-l-2 border-cyan/40 pl-5">
            <p className="text-mist">
              “Serah guided us in Tamil and made caregiver search easier for our grandparents.”
            </p>
            <footer className="mt-2 text-xs text-muted">Family in Jaffna</footer>
          </blockquote>
        </div>
      </section>

      <section className="mt-20 mb-4">
        <h2 className="font-display text-2xl text-mist">Need help choosing?</h2>
        <p className="mt-2 max-w-xl text-sm text-muted">
          Talk to our support team, or open Serah from the corner when you are ready.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/contact">
            <Button>Contact us</Button>
          </Link>
          <Link to="/caregivers">
            <Button tone="ghost">Explore caregivers</Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
