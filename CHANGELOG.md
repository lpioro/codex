# Historia zmian

## W przygotowaniu

- Uporządkowana dokumentacja instalacji, użytkowania, API, ochrony i utrzymania.
- Opis wydania 0.4.0 i obsługa przygotowanych notatek w przyszłych workflow wydań.
- Doprecyzowanie podziału tokenów, zachowania cache i granic ochrony.

Te zmiany dokumentacji nie przesuwają istniejącego taga v0.4.0 ani nie potwierdzają aktualizacji jego plików Release.

## 0.4.0 — 2026-10-31

- Lokalne blokowanie krytycznych promptów w rozpoznanych ścieżkach wysyłki.
- API polityki, cache, zatrzymywanie przy braku polityki i lokalny wyłącznik offline.
- Akcje observed/allowed/blocked w logach i filtr dashboardu.
- Obsługa wielu endpointów z tokenami przypisanymi do profili Chrome.
- Grupy, wykresy, filtry i nawigacja dashboardu po lewej.
- Demo 720 promptów, 12 endpointów, 5 grup i 14 reguł.
- Reguły e-mail/PESEL/tekst oraz konstruktor i test dopasowania.
- Docker Compose, paczkowanie ZIP i workflow GHCR/GitHub Releases.
- Poprawiona kolejność zatwierdzania rotacji tokena w bazie.

Tag wysłany; stan publikacji obrazu i GitHub Release wymaga sprawdzenia Actions.

## Wcześniejsze iteracje

- 0.1.0: kolektor, SQLite, logowanie promptów i reguły tekstowe.
- 0.2.0: branding WalleeGuard, ikony i lokalny Bootstrap.
- 0.3.0: wiele instalacji, parowanie tokenów i oznaczenia endpointów.

To wersje źródeł manifestu rozwijane przed tagiem 0.4.0; lista nie oznacza, że każda miała osobny opublikowany Release.
