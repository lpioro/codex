# WalleeGuard

**Prywatny kolektor promptów AI z lokalnym blokowaniem krytycznych treści.**

WalleeGuard łączy wtyczkę Chrome dla ChatGPT, Claude i Gemini z własnym serwerem, bazą SQLite oraz dashboardem. Pozwala rozpoznać, z którego profilu przeglądarki pochodzi prompt, wykrywać wrażliwe dane i zatrzymywać rozpoznane próby wysłania według reguł administratora.

Wersja kodu i wtyczki: **0.4.0**. Dostępność gotowych paczek sprawdzisz w [Releases](https://github.com/lpioro/codex/releases) i [Actions](https://github.com/lpioro/codex/actions). Sam tag nie potwierdza zakończenia publikacji.

## Co potrafi

| Obszar | Funkcje |
|---|---|
| Wtyczka Chrome MV3 | Logowanie prób wysłania, lokalna kolejka, osobny identyfikator profilu |
| Ochrona przed wysłaniem | Lokalne dopasowanie aktywnych reguł critical, powód blokady, zachowanie szkicu |
| Reguły | Fragment tekstu, e-mail, PESEL z datą i sumą kontrolną; konstruktor i test dopasowania |
| Endpointy | Nazwa, grupa, osobny token, parowanie, ostatni kontakt, cofanie dostępu i rotacja |
| Dashboard | Menu po lewej, wykresy aktywności i alertów, wyszukiwanie, filtry i odświeżanie co 30 s |
| Wdrożenie | Docker Compose, trwały wolumen SQLite, opcjonalny Cloudflare Tunnel, LXC |
| Demo | 720 promptów, 12 endpointów, 5 grup i 14 reguł na osobnej bazie |

Jeden administrator zarządza wieloma profilami Chrome. Grupy porządkują urządzenia; nie tworzą osobnych kont, granic dostępu ani polityk.

## Szybki start — z kodu

Wymagane: Docker Engine i Compose v2. Demo wymaga Compose **2.24.4+**.

```bash
git clone https://github.com/lpioro/codex.git
cd codex
cp .env.example .env
chmod 600 .env
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
# Wpisz wygenerowaną wartość jako PROMPT_TOKEN w .env.
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8787/health
```

Otwórz port **8787** na komputerze z serwerem i zaloguj się tokenem administratora z `.env`. Zdalny dostęp przez HTTPS opisuje [instrukcja wdrożenia](docs/installation.md).

### Podłącz wtyczkę

1. W dashboardzie otwórz **Endpointy**, dodaj urządzenie/profil i skopiuj jednorazowo pokazany token.
2. W Chrome otwórz `chrome://extensions`, włącz **Tryb dewelopera**, wybierz **Załaduj rozpakowane** i wskaż katalog `extension`.
3. Otwórz ustawienia wtyczki. Wpisz adres kolektora i **token endpointu**, nie `PROMPT_TOKEN`.
4. Wybierz niezależnie logowanie oraz blokowanie. Zapisz ustawienia i zaakceptuj dostęp do serwera.
5. Odśwież istniejące karty ChatGPT, Claude i Gemini.
6. W dashboardzie dodaj aktywną regułę critical, np. PESEL. Dopiero taka reguła uruchomi detekcję danego rodzaju w trybie blokowania.

Pusta produkcyjna baza nie zawiera gotowych reguł. Pusta, poprawnie pobrana polityka nie blokuje promptów. **Blokowanie jest domyślnie włączone we wtyczce**; brak konfiguracji lub aktualnej polityki zatrzymuje rozpoznane próby wysłania.

## Gotowy obraz i ZIP

Po potwierdzeniu udanej publikacji wydania można użyć `ghcr.io/lpioro/codex:0.4.0`. Ustaw `PROMPT_IMAGE` w `.env`:

```dotenv
PROMPT_IMAGE=ghcr.io/lpioro/codex:0.4.0
```

```bash
docker compose pull observatory
docker compose up -d --no-build
```

ZIP `prompt-observatory-extension-0.4.0.zip` trzeba rozpakować i załadować w Chrome. Nazwa pliku zachowuje wcześniejszą nazwę techniczną projektu. Paczka nie jest instalatorem ani publikacją w Chrome Web Store. Wydania zawierają także sumę SHA-256, bazę demo i pliki Compose. [Szczegóły paczkowania i wydań](docs/development.md).

## Uruchom demo

Po ustawieniu `PROMPT_TOKEN` w `.env`:

```bash
docker compose -p walleeguard-demo -f compose.demo.yaml up -d --build
```

Dashboard demo działa na lokalnym porcie **8788**, z osobnym wolumenem. Nie uzupełnia ani nie nadpisuje właściwej bazy. [Dane i scenariusze demo](docs/demo.md).

## Jak działa ochrona

Wtyczka pobiera aktywne reguły critical i ocenia tekst **lokalnie**. Dopasowanie zatrzymuje rozpoznaną wysyłkę i pokazuje powód. Sprawdzenie nie wysyła promptu do kolektora; osobno włączone logowanie przesyła pełną treść, także zablokowanych prób.

| Stan logu | Znaczenie |
|---|---|
| `observed` | Przechwycona próba bez decyzji lokalnej ochrony |
| `allowed` | Lokalna polityka pozwoliła kontynuować |
| `blocked` | Wtyczka zgłosiła zatrzymanie próby |

To decyzje i obserwacje rozszerzenia, nie potwierdzenia dostarczenia promptu do AI. Cache działa do 60 s bez odświeżenia, a przy awarii połączenia do 5 min od pobrania. Brak polityki lub starsza kopia zatrzymują wysyłkę. [Reguły, tryby i ograniczenia](docs/protection.md).

## Dokumentacja

- [Instalacja, Chrome, Docker, LXC i Cloudflare](docs/installation.md)
- [Dashboard, endpointy, grupy i codzienna obsługa](docs/user-guide.md)
- [Reguły, blokowanie, prywatność i zakres ochrony](docs/protection.md)
- [API, tokeny i filtry](docs/api.md)
- [Aktualizacja, kopie zapasowe i rozwiązywanie problemów](docs/operations.md)
- [Demo i generowanie przykładowych danych](docs/demo.md)
- [Rozwój, testy, paczki i publikowanie](docs/development.md)
- [Gotowe opisy projektu i rozszerzenia](docs/project-description.md)
- [Historia zmian](CHANGELOG.md) · [Opis wydania 0.4.0](docs/releases/v0.4.0.md)

## Zakres i technologia

Serwer używa standardowej biblioteki Pythona 3.10+; sprawdzany na 3.12. Dashboard to lokalny Bootstrap 5.3.3, JavaScript i wykresy SVG, bez CDN. Licencja Bootstrapa znajduje się w [bootstrap.LICENSE](server/static/vendor/bootstrap.LICENSE).

Ochrona obejmuje rozpoznane edytory i zdarzenia wysyłania tekstu. Nie analizuje załączników, odpowiedzi, głosu ani wszystkich żądań sieciowych. Nie zastępuje kompletnego DLP ani oceny semantycznej promptu. Rzeczywiste witryny dostawców i wdrożenie LXC/Cloudflare wymagają osobnej kontroli w Twojej infrastrukturze.

Projekt nie ma obecnie zadeklarowanej licencji własnego kodu. Nie należy utożsamiać licencji dołączonego Bootstrapa z licencją całego projektu.
