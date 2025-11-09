# Troubleshooting

## Problem: 404 Fehler für `/en/login` oder `/de/login` im Development-Modus

### Lösung 1: Cache löschen und Server neu starten
```bash
rm -rf .next node_modules/.cache
npm run dev
```

### Lösung 2: Ohne Turbopack starten
```bash
npm run dev -- --turbo=false
```

### Lösung 3: Production Build testen
```bash
npm run build
npm run start
```

### Lösung 4: Middleware prüfen
Stelle sicher, dass `middleware.ts` im Root-Verzeichnis existiert und korrekt konfiguriert ist.

### Lösung 5: next.config.ts prüfen
Stelle sicher, dass der Pfad zur i18n-Konfiguration korrekt ist:
```typescript
const withNextIntl = createNextIntlPlugin("./i18n/request.ts");
```
