"use client";

import { createTheme } from "@mui/material/styles";

/**
 * Two static MUI themes mirroring the light/dark HSL triads in
 * `src/app/globals.css`, as literal `hsl(...)` strings rather than the CSS
 * custom properties themselves — MUI's own `alpha()` (hover/selected overlays,
 * disabled states) parses its input as a literal color and throws on a
 * `var(--x)` reference, so the values are copied here instead of shared live.
 * `useDarkMode` picks between the two to track the app's own light/dark toggle.
 */

const shared = {
  shape: { borderRadius: 6 },
  typography: {
    fontFamily: "var(--font-sans)",
    fontSize: 13,
  },
} as const;

export const muiLightTheme = createTheme({
  ...shared,
  palette: {
    mode: "light",
    background: { default: "hsl(210, 22%, 96%)", paper: "hsl(0, 0%, 100%)" },
    text: { primary: "hsl(215, 28%, 15%)", secondary: "hsl(215, 12%, 42%)" },
    divider: "hsl(214, 20%, 87%)",
    primary: { main: "hsl(207, 57%, 46%)", contrastText: "hsl(210, 22%, 98%)" },
    error: { main: "hsl(0, 70%, 50%)" },
    warning: { main: "hsl(38, 82%, 42%)" },
    success: { main: "hsl(146, 50%, 38%)" },
    action: { hover: "hsl(210, 18%, 88%)", selected: "hsl(210, 18%, 91%)" },
  },
});

export const muiDarkTheme = createTheme({
  ...shared,
  palette: {
    mode: "dark",
    background: { default: "hsl(210, 26%, 8%)", paper: "hsl(213, 22%, 11%)" },
    text: { primary: "hsl(210, 20%, 92%)", secondary: "hsl(213, 12%, 60%)" },
    divider: "hsl(213, 16%, 19%)",
    primary: { main: "hsl(207, 66%, 57%)", contrastText: "hsl(213, 28%, 8%)" },
    error: { main: "hsl(0, 66%, 58%)" },
    warning: { main: "hsl(38, 82%, 56%)" },
    success: { main: "hsl(146, 46%, 50%)" },
    action: { hover: "hsl(213, 18%, 20%)", selected: "hsl(213, 18%, 17%)" },
  },
});
