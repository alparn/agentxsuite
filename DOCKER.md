# Docker Setup für AgentxSuite

Dieses Dokument beschreibt die Docker-Konfiguration für Backend und Frontend.

## Übersicht

Das Projekt verwendet Docker Compose für die Orchestrierung der Services:
- **Backend**: Django 5 + DRF (Port 8000)
- **Frontend**: Next.js 16 (Port 3000)
- **Database**: PostgreSQL 16 (Port 5432)
- **Cache**: Redis 7 (Port 6379)
- **MCP Fabric**: FastAPI Service (Port 8090, optional)

## Voraussetzungen

- Docker >= 20.10
- Docker Compose >= 2.0

## Quick Start

### 1. Environment-Variablen einrichten

Kopiere `.env.example` zu `.env` und passe die Werte an:

```bash
cp .env.example .env
```

Wichtige Variablen:
- `SECRET_KEY`: Django Secret Key (sollte in Production geändert werden)
- `POSTGRES_PASSWORD`: Datenbank-Passwort
- `SECRETSTORE_FERNET_KEY`: Optional, wird automatisch generiert wenn leer

### 2. Development-Modus starten

```bash
# Alle Services starten
docker-compose up -d

# Logs anzeigen
docker-compose logs -f

# Services stoppen
docker-compose down
```

### 3. Datenbank-Migrationen ausführen

```bash
# Migrationen erstellen (falls nötig)
docker-compose exec backend python manage.py makemigrations

# Migrationen ausführen
docker-compose exec backend python manage.py migrate

# Superuser erstellen
docker-compose exec backend python manage.py createsuperuser
```

### 4. Production-Modus

```bash
# Mit Production-Override starten
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Services

### Backend (Django)

- **Port**: 8000
- **Health Check**: `http://localhost:8000/api/v1/`
- **Volumes**: 
  - Code-Mount für Development (Hot-Reload)
  - `backend_static`: Statische Dateien
  - `backend_media`: Media-Dateien

**Development Command**:
```bash
python manage.py runserver 0.0.0.0:8000
```

**Production Command**:
```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120
```

### Frontend (Next.js)

- **Port**: 3000
- **Health Check**: `http://localhost:3000`
- **Build**: Multi-stage Build mit standalone output

**Environment Variables**:
- `NEXT_PUBLIC_API_URL`: Backend API URL
- `NEXT_PUBLIC_MCP_FABRIC_URL`: MCP Fabric Service URL

### Database (PostgreSQL)

- **Port**: 5432
- **Volume**: `postgres_data` (persistente Daten)
- **Health Check**: PostgreSQL readiness check

### Redis

- **Port**: 6379
- **Volume**: `redis_data` (persistente Daten)
- **Verwendung**: Cache und Rate Limiting

### MCP Fabric (Optional)

- **Port**: 8090
- **Profile**: `mcp-fabric` (muss explizit gestartet werden)

**Starten**:
```bash
docker-compose --profile mcp-fabric up -d mcp-fabric
```

## Nützliche Befehle

### Logs anzeigen

```bash
# Alle Services
docker-compose logs -f

# Einzelner Service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Shell-Zugriff

```bash
# Backend Shell
docker-compose exec backend bash

# Django Shell
docker-compose exec backend python manage.py shell

# Database Shell
docker-compose exec db psql -U postgres -d agentxsuite
```

### Datenbank-Backup

```bash
# Backup erstellen
docker-compose exec db pg_dump -U postgres agentxsuite > backup.sql

# Backup wiederherstellen
docker-compose exec -T db psql -U postgres agentxsuite < backup.sql
```

### Images neu bauen

```bash
# Alle Images neu bauen
docker-compose build --no-cache

# Einzelnes Image
docker-compose build --no-cache backend
docker-compose build --no-cache frontend
```

### Volumes verwalten

```bash
# Volumes auflisten
docker volume ls | grep agentxsuite

# Volume löschen (ACHTUNG: Datenverlust!)
docker-compose down -v
```

## Troubleshooting

### Backend startet nicht

1. Prüfe Datenbank-Verbindung:
```bash
docker-compose exec backend python manage.py dbshell
```

2. Prüfe Migrationen:
```bash
docker-compose exec backend python manage.py showmigrations
```

### Frontend zeigt keine Daten

1. Prüfe Backend-URL in Frontend-Environment:
```bash
docker-compose exec frontend env | grep NEXT_PUBLIC
```

2. Prüfe CORS-Einstellungen im Backend

### Port bereits belegt

Ändere die Ports in `.env`:
```bash
BACKEND_PORT=8001
FRONTEND_PORT=3001
POSTGRES_PORT=5433
```

### Permission-Probleme

Die Container laufen als non-root User. Falls Permission-Probleme auftreten:

```bash
# Prüfe User im Container
docker-compose exec backend whoami

# Falls nötig, Permissions anpassen
docker-compose exec backend chown -R django:django /app
```

## Production-Deployment

### Checkliste

- [ ] `.env` mit sicheren Werten konfiguriert
- [ ] `SECRET_KEY` geändert
- [ ] `POSTGRES_PASSWORD` geändert
- [ ] `SECRETSTORE_FERNET_KEY` gesetzt
- [ ] `DEBUG=False` in Production
- [ ] `ALLOWED_HOSTS` korrekt gesetzt
- [ ] SSL/TLS konfiguriert (via Reverse Proxy)
- [ ] Volumes für persistente Daten eingerichtet
- [ ] Backup-Strategie implementiert

### Reverse Proxy (Nginx)

Beispiel-Nginx-Konfiguration:

```nginx
upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;
    server_name example.com;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Weitere Informationen

- [Docker Compose Dokumentation](https://docs.docker.com/compose/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/)
- [Next.js Docker Deployment](https://nextjs.org/docs/deployment#docker-image)













