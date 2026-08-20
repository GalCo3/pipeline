"use client";

import { useEffect, useState } from "react";

/**
 * Tracks the `dark` class `Shell`'s theme toggle puts on `<html>`.
 *
 * A `MutationObserver` rather than lifted state: the toggle writes directly
 * to `document.documentElement.classList` (see `src/components/Shell.tsx`)
 * with no React state of its own above this, so watching the DOM node is the
 * only way another component learns the theme changed.
 */
export function useDarkMode(): boolean {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    setDark(root.classList.contains("dark"));
    const observer = new MutationObserver(() => setDark(root.classList.contains("dark")));
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return dark;
}
