import { Heart } from "lucide-react";

/** Page footer — just the signature line. */
export function Footer() {
  return (
    <footer className="mt-12 border-t border-border/70 bg-card/40">
      <div className="mx-auto flex max-w-7xl items-center justify-end px-4 py-5">
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          Developed with
          <Heart className="h-4 w-4 text-destructive" aria-label="love" />
          by
          <span className="font-medium text-foreground">Gal Cohen</span>
        </p>
      </div>
    </footer>
  );
}
