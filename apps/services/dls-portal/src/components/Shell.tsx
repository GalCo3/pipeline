"use client";

import { Activity, History, LayoutGrid, Moon, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { cx } from "@/lib/format";
import { Eyebrow } from "@/components/ui";
import { Footer } from "@/components/Footer";

/** Applied before paint by the inline script below, then toggled from here. */
const THEME_KEY = "dls-portal-theme";

function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem(THEME_KEY, next ? "dark" : "light");
  }

  return (
    <button
      onClick={toggle}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className="rounded-md border border-border bg-card p-1.5 text-muted-foreground transition hover:text-foreground"
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}

const NAV = [
  { href: "/", label: "Overview", Icon: LayoutGrid },
  { href: "/history", label: "History", Icon: History },
];

/**
 * `store` is `database.collection`, resolved from the environment by the server
 * layout and handed down. This is a client component — it cannot read
 * `@/lib/config` (server-only), and a NEXT_PUBLIC_ twin would be inlined at
 * build time, which is exactly the wrong moment for a per-cluster value.
 */
export function Shell({ store, children }: { store: string; children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <>
      {/* Theme before first paint: reading localStorage in an effect would flash
          the light palette at every dark-mode operator. */}
      <script
        dangerouslySetInnerHTML={{
          __html: `try{if(localStorage.getItem('${THEME_KEY}')==='dark'||(!localStorage.getItem('${THEME_KEY}')&&matchMedia('(prefers-color-scheme: dark)').matches))document.documentElement.classList.add('dark')}catch(e){}`,
        }}
      />
      <header className="sticky top-0 z-30 border-b border-border/70 bg-card/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
          <Link href="/" className="flex items-center gap-2">
            <span className="pulse-signal h-2 w-2 rounded-full bg-brand" />
            <span className="font-display text-lg font-semibold tracking-tight">DLS Portal</span>
          </Link>

          <nav className="flex items-center gap-1">
            {NAV.map(({ href, label, Icon }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cx(
                    "inline-flex h-9 items-center gap-1.5 rounded-md px-3 text-[0.9375rem] font-medium transition",
                    active
                      ? "bg-accent text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <Eyebrow className="hidden items-center gap-1.5 sm:inline-flex">
              <Activity className="h-3 w-3" />
              {store}
            </Eyebrow>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* The main region grows so the signature line sits at the bottom of the
          viewport rather than halfway up an empty screen. 3.5rem is the sticky
          header's own height. */}
      <div className="flex min-h-[calc(100vh-3.5rem)] flex-col">
        <main className="settle-in mx-auto w-full max-w-7xl flex-1 px-4 py-8">{children}</main>
        <Footer store={store} />
      </div>
    </>
  );
}
