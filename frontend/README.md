# AgentxSuite Frontend

Next.js Frontend für die AgentxSuite Plattform zur Verwaltung von AI-Agents.

## Features

- 🌍 Zweisprachig (Englisch/Deutsch) mit next-intl
- 🎨 Moderne UI mit Tailwind CSS und Dark Mode
- 📊 Dashboard mit Charts und Metriken
- 🔌 Connections Management für MCP-Server
- 🤖 Agents Verwaltung
- 🛠️ Tools Management
- 🚀 Runs Monitoring
- 🛡️ Policies Management
- 📝 Audit Logs

## Setup

1. Installiere Dependencies:
```bash
npm install
```

2. Erstelle `.env.local` Datei:
```bash
cp .env.local.example .env.local
```

3. Starte den Development Server:
```bash
npm run dev
```

Die App läuft dann auf http://localhost:3000

## Umgebungsvariablen

- `NEXT_PUBLIC_API_URL`: Backend API URL (Standard: http://localhost:8000/api/v1)

## Struktur

- `app/[locale]/` - Lokalisierte Seiten
- `components/` - React Komponenten
- `lib/` - Utilities und API Client
- `messages/` - Übersetzungsdateien

## Technologien

- Next.js 16
- TypeScript
- Tailwind CSS
- next-intl (Internationalisierung)
- Zustand (State Management)
- React Query (Data Fetching)
- Recharts (Charts)
- Lucide React (Icons)
