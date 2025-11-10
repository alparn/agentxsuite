# AgentxSuite Landing Page

Statische Landing Page für AgentxSuite - Enterprise MCP Agent Orchestration Platform.

## 🎯 Features

- ✅ **Kein Framework**: Reines HTML, CSS und JavaScript
- ✅ **Dunkles Theme**: Modernes Design inspiriert vom AgentxSuite Dashboard
- ✅ **Zweisprachig**: Englisch und Deutsch (umschaltbar)
- ✅ **SEO-optimiert**: Meta-Tags, Schema.org, Sitemap, RSS
- ✅ **Mobile-first**: Responsives Design für alle Geräte
- ✅ **Blog-System**: Mit Suche, Tags und Pagination
- ✅ **Rechtliche Seiten**: Impressum, Datenschutz (DE/EN)
- ✅ **PWA-Ready**: Web App Manifest und Service Worker-fähig

## 📁 Projektstruktur

```
landing-page/
├── index.html              # Startseite (EN)
├── de/
│   └── index.html         # Startseite (DE)
├── blog/
│   ├── index.html         # Blog-Übersicht (EN)
│   ├── getting-started-with-agentxsuite.html
│   └── understanding-mcp-protocol.html
├── legal/
│   ├── imprint.html       # Impressum (EN)
│   ├── impressum.html     # Impressum (DE)
│   ├── privacy.html       # Datenschutz (EN)
│   └── datenschutz.html   # Datenschutz (DE)
├── assets/
│   ├── css/
│   │   ├── base.css       # Basis-Styles
│   │   ├── theme-dark.css # Dunkles Theme
│   │   └── utilities.css  # Utility-Klassen
│   ├── js/
│   │   ├── main.js        # Haupt-JavaScript
│   │   ├── i18n.js        # Internationalisierung
│   │   ├── search.js      # Blog-Suche
│   │   └── theme-toggle.js # Theme-Switcher
│   ├── i18n/
│   │   ├── en.json        # Englische Übersetzungen
│   │   └── de.json        # Deutsche Übersetzungen
│   └── img/
│       └── favicon.svg    # Favicon
├── robots.txt             # Robots.txt
├── sitemap.xml            # Sitemap
├── feed.xml               # RSS Feed
├── manifest.webmanifest   # PWA Manifest
├── .htaccess              # Apache Configuration (Cache, Security, Compression)
└── serve.py              # Lokaler Entwicklungsserver (optional)
```

## 🚀 Verwendung

### Direktes Öffnen (ohne Server)

Einfach `index.html` im Browser öffnen:

```bash
open index.html
# oder Rechtsklick → "Öffnen mit" → Browser
```

**Hinweis**: Einige Features (wie i18n via fetch) funktionieren nur mit einem Webserver.

### Mit lokalem Webserver (empfohlen für Entwicklung)

```bash
cd landing-page
python3 serve.py 8000
```

Dann öffnen: `http://localhost:8000`

## ⚙️ Anpassungen

### Platzhalter ersetzen

Suchen und ersetzen Sie in allen HTML-Dateien:

1. **`${SITE_URL}`** → Ihre Domain (z.B. `https://agentxsuite.com`)
2. **`https://github.com/alparn/agentxsuite`** → Ihre GitHub-Repo-URL
3. **`${CONTACT_EMAIL}`** → Ihre Kontakt-E-Mail
4. **`${LICENSE_NAME}`** → Ihre Lizenz (z.B. `AGPL-3.0`)

**Schnelle Ersetzung (Linux/Mac)**:

```bash
find . -type f -name "*.html" -exec sed -i '' 's|\${SITE_URL}|https://agentxsuite.com|g' {} +
find . -type f -name "*.html" -exec sed -i '' 's|\https://github.com/alparn/agentxsuite|https://github.com/YOUR_USER/YOUR_REPO|g' {} +
find . -type f -name "*.html" -exec sed -i '' 's|\${CONTACT_EMAIL}|contact@example.com|g' {} +
find . -type f -name "*.html" -exec sed -i '' 's|\${LICENSE_NAME}|AGPL-3.0|g' {} +
```

### Inhalte anpassen

#### Impressum & Datenschutz

Bearbeiten Sie die Platzhalter in:
- `legal/imprint.html` und `legal/impressum.html`
- `legal/privacy.html` und `legal/datenschutz.html`

#### Blog-Posts hinzufügen

1. Neue HTML-Datei in `/blog/` erstellen (siehe `post-template.html`)
2. In `/blog/index.html` hinzufügen mit `data-post-*` Attributen
3. `sitemap.xml` und `feed.xml` aktualisieren

#### Farben anpassen

In `assets/css/theme-dark.css`:

```css
:root {
    --color-primary: #6366f1;  /* Hauptfarbe */
    --color-accent: #8b5cf6;   /* Akzentfarbe */
    /* ... weitere Farben */
}
```

## 🎨 Design-System

### Farben (Dark Theme)

- **Primary**: `#6366f1` (Indigo)
- **Accent**: `#8b5cf6` (Purple)
- **Background**: `#0a0a0f` (Dunkel)
- **Surface**: `#131318` (Erhöht)
- **Text Primary**: `#e2e8f0` (Hell)
- **Text Secondary**: `#94a3b8` (Grau)

### Typografie

- **Schriftart**: System-Fonts (keine externen Fonts)
- **Base Size**: 16px
- **Scale**: 0.75rem → 3rem

### Spacing

- **xs**: 0.25rem
- **sm**: 0.5rem
- **md**: 1rem
- **lg**: 1.5rem
- **xl**: 2rem
- **2xl**: 3rem
- **3xl**: 4rem
- **4xl**: 6rem

## 📱 Responsive Breakpoints

- **Mobile**: < 480px
- **Tablet**: 480px - 768px
- **Desktop**: > 768px

## 🔍 SEO-Features

### Meta-Tags
- Title, Description, Keywords
- Open Graph (Facebook)
- Twitter Cards
- Canonical Links
- Hreflang (EN/DE)

### Strukturierte Daten (Schema.org)
- WebSite mit SearchAction
- BlogPosting für Blog-Artikel
- BreadcrumbList für Navigation
- SoftwareApplication

### Performance
- Preload kritischer Assets
- Lazy Loading für Bilder
- Minimierte Animationen für `prefers-reduced-motion`
- Optimierte SVG-Icons

## ✨ JavaScript-Features

### Theme Toggle
- Automatische Erkennung von `prefers-color-scheme`
- LocalStorage-Persistenz
- Smooth Transitions

### Internationalisierung
- JSON-basierte Übersetzungen
- Dynamischer Sprachwechsel
- URL-basierte Spracherkennung

### Blog-Suche
- Client-seitige Volltextsuche
- Suche in Titel, Beschreibung und Tags
- Live-Ergebnisse mit Highlighting

## 🚢 Deployment

### Statisches Hosting (empfohlen)

**GitHub Pages**:
```bash
# Im Repository Settings → Pages aktivieren
# Branch: main, Folder: /landing-page
```

**Netlify**:
```bash
netlify deploy --prod --dir=landing-page
```

**Vercel**:
```bash
vercel --prod landing-page
```

### Traditionelles Hosting

Laden Sie alle Dateien per FTP/SFTP auf Ihren Webserver hoch.

**Apache mit .htaccess**:
Die `.htaccess` Datei ist bereits konfiguriert für:
- ✅ Cache-Control Headers (HTML: kein Cache, Assets: lange Cache-Zeit)
- ✅ Gzip-Kompression
- ✅ Security Headers
- ✅ MIME Types
- ✅ UTF-8 Encoding

**Wichtig**: HTML-Dateien werden **nicht gecacht**, damit neue Uploads sofort sichtbar sind. Statische Assets (CSS, JS, Bilder) haben lange Cache-Zeiten für Performance.

**Nginx-Beispiel**:
```nginx
server {
    listen 80;
    server_name agentxsuite.com;
    root /var/www/landing-page;
    index index.html;

    # Cache-Control für HTML (kein Cache)
    location ~ \.html$ {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }

    # Lange Cache-Zeit für statische Assets
    location ~* \.(css|js|jpg|jpeg|png|gif|webp|svg|ico|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Gzip-Kompression
    gzip on;
    gzip_types text/html text/css text/javascript application/javascript application/json image/svg+xml;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

## ⚙️ Cache-Handling

Die `.htaccess` Datei konfiguriert intelligentes Cache-Handling:

### Cache-Strategie

- **HTML-Dateien**: `no-cache` - Werden immer neu geladen, damit Updates sofort sichtbar sind
- **CSS/JS**: Lange Cache-Zeit (1 Jahr) mit `immutable` - Für Performance
- **Bilder**: Lange Cache-Zeit (1 Jahr) - Statische Assets
- **JSON (i18n)**: Kurze Cache-Zeit (1 Stunde) mit Revalidation
- **XML (Sitemap/RSS)**: Kurze Cache-Zeit (1 Stunde)

### Nach Upload neuer Dateien

1. **HTML-Änderungen**: Werden sofort sichtbar (kein Cache)
2. **CSS/JS-Änderungen**: 
   - Option A: Dateinamen ändern (z.B. `main.v2.js`) - Browser lädt automatisch neu
   - Option B: Query-Parameter verwenden (z.B. `main.js?v=2`) - Funktioniert auch
3. **Bild-Änderungen**: Dateinamen ändern oder Query-Parameter verwenden

### Cache leeren (für Entwicklung)

```bash
# Browser-Cache leeren
# Chrome/Edge: Ctrl+Shift+Delete (Windows) oder Cmd+Shift+Delete (Mac)
# Oder: Hard Reload mit Ctrl+F5 (Windows) oder Cmd+Shift+R (Mac)
```

## 🔧 Troubleshooting

### Problem: CSS/JS-Dateien werden nicht geladen (MIME type 'text/html')

**Symptome:**
- Browser-Fehler: "Refused to apply style... MIME type ('text/html')"
- 404-Fehler für CSS/JS-Dateien
- Website lädt ohne Styles

**Lösungen:**

1. **Prüfen Sie, ob die Dateien auf dem Server existieren:**
   ```bash
   # Testen Sie direkt im Browser:
   https://agentxsuite.com/assets/css/base.css
   https://agentxsuite.com/assets/js/main.js
   ```

2. **Stellen Sie sicher, dass `.htaccess` aktiviert ist:**
   - Apache: `AllowOverride All` in der Server-Konfiguration
   - Die `.htaccess` Datei muss im Root-Verzeichnis liegen

3. **Prüfen Sie die Dateistruktur auf dem Server:**
   ```
   /var/www/html/ (oder Ihr Document Root)
   ├── index.html
   ├── .htaccess
   ├── assets/
   │   ├── css/
   │   │   ├── base.css
   │   │   ├── theme-dark.css
   │   │   └── utilities.css
   │   ├── js/
   │   │   ├── main.js
   │   │   ├── i18n.js
   │   │   ├── theme-toggle.js
   │   │   └── cookie-banner.js
   │   └── img/
   │       └── orchestration-diagram.svg
   ```

4. **Wenn Sie eine SPA-Routing-Konfiguration haben:**
   - Entfernen Sie Regeln, die ALLE Anfragen auf `index.html` umleiten
   - Die `.htaccess` enthält bereits Regeln, die statische Dateien ausschließen

5. **Testen Sie die MIME-Types:**
   ```bash
   curl -I https://agentxsuite.com/assets/css/base.css
   # Sollte zeigen: Content-Type: text/css
   
   curl -I https://agentxsuite.com/assets/js/main.js
   # Sollte zeigen: Content-Type: application/javascript
   ```

6. **Falls das Problem weiterhin besteht:**
   - Prüfen Sie die Apache-Error-Logs: `/var/log/apache2/error.log`
   - Prüfen Sie, ob `mod_rewrite`, `mod_headers` und `mod_mime` aktiviert sind:
     ```bash
     apache2ctl -M | grep rewrite
     apache2ctl -M | grep headers
     apache2ctl -M | grep mime
     ```

## 📊 Lighthouse-Scores (Ziel)

- **Performance**: ≥ 90
- **Accessibility**: ≥ 90
- **Best Practices**: ≥ 90
- **SEO**: ≥ 90

## 🧪 Testing

### HTML-Validierung
```bash
# W3C Validator
curl -s -H "Content-Type: text/html; charset=utf-8" \
  --data-binary @index.html \
  https://validator.w3.org/nu/?out=gnu
```

### Lighthouse (Chrome DevTools)
1. Chrome DevTools öffnen (F12)
2. Lighthouse-Tab
3. "Generate report"

### Broken Links prüfen
```bash
# Mit wget
wget --spider -r -nd -nv -o spider.log http://localhost:8000

# Oder mit linkchecker
linkchecker http://localhost:8000
```

## 🤝 Beitragen

Dieses Projekt ist Teil von AgentxSuite. Siehe das Haupt-Repository für Contribution-Guidelines.

## 📄 Lizenz

Siehe [LICENSE](https://github.com/alparn/agentxsuite/blob/main/LICENSE) im Haupt-Repository.

Typischerweise: **AGPL-3.0** oder eine andere OSI-genehmigte Lizenz.

## 🔗 Links

- **Haupt-Projekt**: https://github.com/alparn/agentxsuite
- **Dokumentation**: https://github.com/alparn/agentxsuite#readme
- **Issues**: https://github.com/alparn/agentxsuite/issues
- **Discussions**: https://github.com/alparn/agentxsuite/discussions

---

**Erstellt mit ❤️ für AgentxSuite**

