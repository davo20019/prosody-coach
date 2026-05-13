# Vendored frontend assets

These files are vendored deliberately so the local app does not ping CDNs at runtime. They are not edited by hand.

## Versions

- `htmx.min.js` — HTMX 2.0.4
- `chart.umd.min.js` — Chart.js 4.4.6

## Refresh procedure

```bash
curl -L -o web/static/vendor/htmx.min.js \
  https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js

curl -L -o web/static/vendor/chart.umd.min.js \
  https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js
```

When bumping a version, change the URL above AND the version number in this file in the same commit.
