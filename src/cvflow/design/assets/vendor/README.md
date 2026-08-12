# Vendored assets

These files ship inside the wheel and are inlined into the generated dashboard,
so `pip install cvflow` remains the only install step — no Node, npm, or network
access at runtime or build time.

| File | Version | License | Source |
|---|---|---|---|
| `chart.umd.min.js` | Chart.js 4.4.x | MIT — © 2014-2024 Chart.js Contributors | https://www.chartjs.org |
| `Archivo-Variable.woff2` | Archivo Variable (latin) | SIL Open Font License 1.1 — © Omnibus-Type | https://fonts.google.com/specimen/Archivo |
| `Archivo-Variable-ext.woff2` | Archivo Variable (latin-ext) | SIL Open Font License 1.1 — © Omnibus-Type | https://fonts.google.com/specimen/Archivo |
| `GeistMono-Variable.woff2` | Geist Mono Variable | SIL Open Font License 1.1 — © 2023 Vercel | https://vercel.com/font |

Archivo is the Ultralytics corporate typeface (ultralytics.com/brand) and carries
the whole interface. Geist Mono covers the monospaced role only — paths, check
codes, and tabular figures — which the brand guide does not specify.

Both licenses permit redistribution in this form. Chart.js keeps its own banner
comment in the minified file; the fonts carry their license metadata inside the
`woff2` container.

The dashboard renders identically offline and over `file://` because everything
here is embedded in the page — the fonts as `data:` URIs, Chart.js as an inline
`<script>`.
