# Prompt Observatory

Pierwsza wersja prywatnego obserwatorium promptów: wtyczka Chrome MV3 → API Python → SQLite → dashboard. Bez zewnętrznych zależności Pythona. Wymaga Python 3.10+; testowane na 3.12.

## Lokalnie

W katalogu repozytorium:

```bash
export PROMPT_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
python3 -m server.app
```

Dashboard: otwórz lokalnie port 8787 i podaj token z własnej zmiennej środowiskowej. Token dashboardu pozostaje w pamięci karty. API i dashboard działają pod tym samym adresem. Serwer nasłuchuje wyłącznie na 127.0.0.1. Zmienne: PROMPT_TOKEN (minimum 32 znaki), PROMPT_DB (domyślnie data/prompts.sqlite3), PORT (domyślnie 8787). Zachowaj ten sam token po restarcie.

```bash
python3 -m unittest discover -s tests -v
```

## Docker Compose (także w LXC)

Wymagany Docker Engine i Compose v2. W LXC administrator hosta musi udostępnić obsługę kontenerów zagnieżdżonych (nesting), cgroups i wymagane funkcje kernela; samo zainstalowanie klienta Docker nie wystarcza.

```bash
cp .env.example .env
chmod 600 .env
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
# Wpisz wygenerowaną wartość jako PROMPT_TOKEN w .env.
docker compose up -d --build
docker compose ps
docker compose logs --tail=50 observatory
curl --fail http://127.0.0.1:8787/health
```

Dashboard i API są dostępne na porcie 8787 wyłącznie na lokalnym interfejsie hosta. Port hosta można zmienić przez PORT w .env. Wewnątrz kontenera aplikacja słucha na 0.0.0.0:8787; poza Dockerem nadal domyślnie na 127.0.0.1 (zmienna HOST). Obraz uruchamia aplikację jako użytkownik 10001 bez uprawnień root, z kontrolą zdrowia. Compose dodatkowo ustawia system plików tylko do odczytu i usuwa capabilities. Baza jest zapisywana w trwałym nazwanym wolumenie prompts. Pierwszy build uruchamia testy API w etapie testowym; brak bibliotek do pobierania przez pip.

Po zbudowaniu obrazu uruchom test kontenerowy przez `python3 tests/docker_smoke.py`. Tworzy osobny projekt Compose z losowym tokenem, zajmuje lokalny port 18787 i sprawdza zapis, autoryzację oraz zachowanie bazy po odtworzeniu kontenera. Na końcu usuwa wyłącznie swój testowy projekt i wolumen.

### Tunel Cloudflare jako drugi kontener

Utwórz zdalnie zarządzany Cloudflare Tunnel w panelu Cloudflare, wpisz jego token jako TUNNEL_TOKEN w lokalnym .env i ustaw trasę publicznej domeny na usługę **http://observatory:8787** (nie localhost — tunel jest osobnym kontenerem). Następnie:

```bash
docker compose --profile tunnel up -d --build
docker compose logs --tail=50 cloudflared
```

Bez profilu tunnel uruchamia się tylko aplikacja. Cloudflared czeka na zdrowy kolektor. Wtyczka nadal wymaga PROMPT_TOKEN; TUNNEL_TOKEN jest innym sekretem, tylko dla połączenia z Cloudflare. Wtyczka Chrome jest ładowana z katalogu extension, nie uruchamia się jej w kontenerze. Tunel wymaga wychodzącego dostępu do Cloudflare; konfiguracja konta i domeny odbywa się w Twojej infrastrukturze.

```bash
docker compose restart observatory
docker compose down
# Ponowne uruchomienie zachowuje bazę:
docker compose up -d
```

Nie używaj down -v, jeśli chcesz zachować dane — usuwa wolumen bazy. Plik .env jest ignorowany przez Git i wyłączony z kontekstu budowania. Dockerfile kopiuje tylko serwer i testy. Nie dodawaj tokenów do obrazu ani repozytorium. Zmiana PROMPT_TOKEN w .env wymaga odtworzenia kontenera przez docker compose up -d i aktualizacji wtyczki. Wersje bazowe są wskazane tagami; przed docelowym wdrożeniem można przypiąć je dodatkowo do digestów z własnego rejestru.

## Wtyczka

1. Otwórz chrome://extensions, włącz tryb dewelopera i wybierz „Załaduj rozpakowane”.
2. Wskaż katalog extension.
3. Kliknij ikonę rozszerzenia. Wprowadź adres kolektora (HTTPS lub lokalny HTTP), ten sam token i świadomie włącz przechwytywanie.
4. Zaakceptuj dostęp do wskazanego serwera. Odśwież istniejące karty dostawców.
5. Wyślij prompt w ChatGPT, Claude lub Gemini i odśwież dashboard.

Przechwytywane są próby wysłania promptu klawiszem Enter lub rozpoznanym przyciskiem wysyłania. To nie potwierdza przyjęcia promptu przez dostawcę. Nie są zbierane odpowiedzi, pliki, historia czatu ani adres rozmowy. Selektory stron mogą wymagać aktualizacji po zmianach interfejsu dostawców. Wysyłanie przyciskiem zależy od jego etykiety i języka interfejsu. Przeglądarka Chrome i rzeczywiste strony dostawców wymagają osobnej ręcznej weryfikacji.

Kolejka przechowuje maksymalnie 100 zdarzeń, ponawia wysyłkę co minutę i przy następnym zdarzeniu. Pełna kolejka odrzuca nowe zdarzenia z komunikatem w ustawieniach. Identyfikator zdarzenia chroni bazę przed duplikacją przy ponowieniu. Wyłączenie przechwytywania zatrzymuje dodawanie nowych promptów; wcześniejsza kolejka nadal może się wysłać. Usuń ją przyciskiem w ustawieniach, aby anulować wysyłkę.

## LXC i Cloudflare Tunnel

W kontenerze LXC z Pythonem 3.10+ skopiuj projekt np. do /opt/prompt-observatory i uruchom go jako zwykły dedykowany użytkownik. Zapewnij zapis do katalogu bazy. Cloudflared powinien działać w tym samym kontenerze, aby miał dostęp do lokalnego portu.

Przykładowa jednostka systemd (dostosuj użytkownika i ścieżki):

```ini
[Unit]
Description=Prompt Observatory
After=network.target

[Service]
User=promptobs
WorkingDirectory=/opt/prompt-observatory
EnvironmentFile=/etc/prompt-observatory.env
ExecStart=/usr/bin/python3 -m server.app
Restart=on-failure
UMask=0077
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

W pliku /etc/prompt-observatory.env, dostępnym tylko administratorowi, ustaw PROMPT_TOKEN i PROMPT_DB=/opt/prompt-observatory/data/prompts.sqlite3. Utwórz katalog data z prawami 0700 dla użytkownika usługi. Nie zapisuj tokena w repozytorium.

Zainstaluj cloudflared zgodnie z oficjalną dokumentacją Cloudflare i skonfiguruj nazwany Tunnel. Przykładowa sekcja jego konfiguracji:

```yaml
ingress:
  - hostname: prompts.example.com
    service: http://127.0.0.1:8787
  - service: http_status:404
```

Powiąż domenę z tunelem w Cloudflare i uruchom cloudflared jako usługę. Adres HTTPS domeny wpisz we wtyczce. Token API zabezpiecza odczyt i zapis; /health jest publiczne. Dodatkowa interaktywna bramka Cloudflare Access będzie wymagać osobnej integracji z wtyczką — obecna wersja nie obsługuje logowania Access ani jego service tokens.

Tunel zapewnia transport HTTPS do Cloudflare, ale treść promptów przechodzi przez jego infrastrukturę. Token rozszerzenia jest zapisany w chrome.storage.local, bez synchronizacji, bez szyfrowania przez aplikację. Baza zawiera pełną treść promptów. Kontroluj dostęp do profilu Chrome, plików bazy i kopii zapasowych. Rotacja tokena wymaga aktualizacji serwera i wtyczki.

## Reguły i zakres

Reguły wyszukują dosłowny fragment tekstu bez rozróżniania wielkości liter; poziomy: info, warning, critical. Wynik jest utrwalany przy zapisie — zmiana lub usunięcie reguły nie zmienia historii. Dashboard filtruje ostatnie 1000 zdarzeń po tekście, dostawcy i poziomie. Odświeżanie jest ręczne.

To wersja dla jednego użytkownika i niewielkiego ruchu. Nie obejmuje retencji, wieloużytkownikowości, alertów zewnętrznych, redakcji danych ani metryk odpowiedzi/tokenów. Standardowy serwer HTTP Pythona jest prostym kolektorem za tunelem; przed wdrożeniem dla wielu użytkowników potrzebne są utwardzenie, limity ruchu i zarządzanie tożsamościami. Kopię SQLite wykonuj przez mechanizm backup SQLite, uwzględniając tryb WAL.

Cloudflare, LXC i przechwytywanie na żywych stronach nie są zweryfikowane przez testy API.
