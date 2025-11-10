# Troubleshooting: CSS/JS Dateien werden nicht geladen

## Problem
CSS- und JavaScript-Dateien werden mit MIME type `text/html` statt `text/css` oder `application/javascript` zurückgegeben. Dies führt zu Browser-Fehlern wie:
- "Refused to apply style... MIME type ('text/html')"
- "Refused to execute script... MIME type ('text/html')"

## Mögliche Ursachen

### 1. Dateien existieren nicht auf dem Server (404)
**Prüfung:**
```bash
# Direkt im Browser testen:
https://agentxsuite.com/assets/css/base.css
https://agentxsuite.com/assets/js/main.js
```

**Lösung:**
- Stellen Sie sicher, dass alle Dateien hochgeladen wurden
- Prüfen Sie die Verzeichnisstruktur auf dem Server

### 2. Server-Konfiguration überschreibt .htaccess
**Prüfung:**
- Gibt es eine `.htaccess` in einem übergeordneten Verzeichnis?
- Hat Ihr Hosting-Provider eine Server-Konfiguration, die alles auf `index.html` umleitet?
- Ist `AllowOverride All` in der Apache-Konfiguration gesetzt?

**Lösung:**
- Kontaktieren Sie Ihren Hosting-Provider
- Prüfen Sie die Apache-Konfiguration (meist in `/etc/apache2/sites-available/`)

### 3. mod_rewrite ist nicht aktiviert
**Prüfung:**
```bash
apache2ctl -M | grep rewrite
apache2ctl -M | grep headers
apache2ctl -M | grep mime
```

**Lösung:**
```bash
# Aktivieren Sie die Module:
sudo a2enmod rewrite
sudo a2enmod headers
sudo a2enmod mime
sudo systemctl restart apache2
```

### 4. SPA-Routing-Konfiguration
Wenn Sie eine Single-Page-Application-Routing-Konfiguration haben, die ALLE Anfragen auf `index.html` umleitet, müssen Sie diese anpassen.

**Problem-Konfiguration (falsch):**
```apache
# FALSCH - leitet ALLES auf index.html um
RewriteRule ^(.*)$ index.html [L]
```

**Korrekte Konfiguration:**
Die `.htaccess` Datei enthält bereits korrekte Regeln, die statische Dateien ausschließen.

### 5. Content-Type Header wird überschrieben
**Prüfung:**
```bash
curl -I https://agentxsuite.com/assets/css/base.css
# Sollte zeigen: Content-Type: text/css
```

**Lösung:**
Die `.htaccess` setzt explizite Content-Type Header. Falls diese nicht greifen, könnte eine Server-Konfiguration sie überschreiben.

## Schritt-für-Schritt Debugging

1. **Prüfen Sie, ob die Dateien existieren:**
   ```bash
   # SSH auf Server
   ls -la /var/www/html/assets/css/
   ls -la /var/www/html/assets/js/
   ```

2. **Prüfen Sie die Apache-Error-Logs:**
   ```bash
   tail -f /var/log/apache2/error.log
   # Dann laden Sie die Seite neu und sehen Sie die Fehler
   ```

3. **Testen Sie direkt eine CSS-Datei:**
   ```bash
   curl -I https://agentxsuite.com/assets/css/base.css
   ```
   - Wenn 404: Datei existiert nicht
   - Wenn 200 mit `Content-Type: text/html`: Umleitung auf index.html
   - Wenn 200 mit `Content-Type: text/css`: Funktioniert!

4. **Prüfen Sie die Apache-Konfiguration:**
   ```bash
   # Finden Sie die VirtualHost-Konfiguration
   grep -r "DocumentRoot" /etc/apache2/sites-available/
   
   # Prüfen Sie AllowOverride
   grep -r "AllowOverride" /etc/apache2/sites-available/
   ```

5. **Testen Sie mit einer minimalen .htaccess:**
   Erstellen Sie eine Test-Datei `test.css` im Root:
   ```css
   /* Test */
   ```
   Dann testen Sie: `https://agentxsuite.com/test.css`
   - Wenn das funktioniert, liegt das Problem in der Verzeichnisstruktur
   - Wenn nicht, liegt das Problem in der Server-Konfiguration

## Alternative Lösungen

### Option 1: Nginx statt Apache
Wenn Sie Nginx verwenden, benötigen Sie eine `nginx.conf` statt `.htaccess`:

```nginx
server {
    listen 80;
    server_name agentxsuite.com;
    root /var/www/html;
    index index.html;

    # Statische Dateien direkt ausliefern
    location ~* \.(css|js|jpg|jpeg|png|gif|webp|svg|ico|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # CSS mit korrektem MIME-Type
    location ~* \.css$ {
        add_header Content-Type "text/css; charset=UTF-8";
    }

    # JS mit korrektem MIME-Type
    location ~* \.js$ {
        add_header Content-Type "application/javascript; charset=UTF-8";
    }

    # Alle anderen Anfragen auf index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### Option 2: CDN verwenden
Laden Sie statische Assets auf eine CDN hoch (z.B. Cloudflare, AWS CloudFront) und verweisen Sie darauf.

### Option 3: Inline CSS/JS (nur für kleine Projekte)
Für sehr kleine Projekte können Sie CSS/JS inline einbinden, aber das ist nicht empfohlen für Production.

## Kontakt
Wenn das Problem weiterhin besteht, kontaktieren Sie:
- Ihren Hosting-Provider
- Apache/Nginx Support-Community
- Oder öffnen Sie ein Issue im Repository





