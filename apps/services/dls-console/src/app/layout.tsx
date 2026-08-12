import type { Metadata } from "next";

import "@fontsource/archivo/400.css";
import "@fontsource/archivo/600.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";

import { config } from "@/lib/config";
import { Shell } from "@/components/Shell";
import { Providers } from "@/components/Providers";

export const metadata: Metadata = {
  title: "DLS Console",
  description: "Dead letter store triage for the hermes pipeline",
};

/**
 * The store label comes from the environment, and the image is built once and
 * configured per cluster — so this has to be read per request. Prerendering the
 * layout would bake whatever `next build` happened to see (nothing) into the
 * HTML. The pages are client components fetching through the API, so rendering
 * the shell per request costs a shell, not a query.
 */
export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // The theme class is set by an inline script in Shell before paint; starting
    // from the stored preference here would need a cookie round-trip.
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground">
        <Providers>
          <Shell store={config.storeLabel}>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
