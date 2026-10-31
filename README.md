# WalleeGuard

Pierwsza wersja prywatnego obserwatorium promptów: wtyczka Chrome MV3 → API Python → SQLite → dashboard. Bez zewnętrznych zależności Pythona. Wymaga Python 3.10+; testowane na 3.12.

Dashboard korzysta z lokalnie dołączonego Bootstrap 5.3.3 (licencja MIT w server/static/vendor/bootstrap.LICENSE). Branding WalleeGuard obejmuje logo SVG z tarczą i robotem oraz ikony Chrome 16/32/48/128 px. Nie wymaga CDN ani zewnętrznych fontów.

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

Nie używaj down -v, jeśli chcesz zachować dane — usuwa wolumen bazy. Plik .env jest ignorowany przez Git i wyłączony z kontekstu budowania. Końcowy obraz zawiera tylko serwer; etap testowy korzysta również ze źródeł wtyczki i skryptu pakowania. Nie dodawaj tokenów do obrazu ani repozytorium. Zmiana PROMPT_TOKEN w .env wymaga odtworzenia kontenera przez docker compose up -d i ponownego logowania w dashboardzie. Dedykowane tokeny wtyczek pozostają ważne. Wersje bazowe są wskazane tagami; przed docelowym wdrożeniem można przypiąć je dodatkowo do digestów z własnego rejestru.

## Wtyczka

1. Otwórz chrome://extensions, włącz tryb dewelopera i wybierz „Załaduj rozpakowane”.
2. Wskaż katalog extension.
3. Zaloguj się do dashboardu tokenem administratora PROMPT_TOKEN. Rozwiń Endpointy, dodaj nazwę urządzenia/profilu i opcjonalną grupę. Skopiuj jednorazowo wyświetlony token endpointu.
4. Kliknij ikonę rozszerzenia. Wprowadź adres kolektora (HTTPS lub lokalny HTTP), dedykowany token endpointu i świadomie włącz przechwytywanie. Nie wpisuj tokena administratora.
5. Zaakceptuj dostęp do wskazanego serwera. Odśwież istniejące karty dostawców.
6. Wyślij prompt w ChatGPT, Claude lub Gemini i odśwież dashboard.

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

Powiąż domenę z tunelem w Cloudflare i uruchom cloudflared jako usługę. Adres HTTPS domeny wpisz we wtyczce. Token administratora zabezpiecza odczyt i zarządzanie; osobne tokeny endpointów uprawniają tylko do wysyłania zdarzeń i heartbeatów; /health jest publiczne. Dodatkowa interaktywna bramka Cloudflare Access będzie wymagać osobnej integracji z wtyczką — obecna wersja nie obsługuje logowania Access ani jego service tokens.

Tunel zapewnia transport HTTPS do Cloudflare, ale treść promptów przechodzi przez jego infrastrukturę. Token rozszerzenia jest zapisany w chrome.storage.local, bez synchronizacji, bez szyfrowania przez aplikację. Baza zawiera pełną treść promptów. Kontroluj dostęp do profilu Chrome, plików bazy i kopii zapasowych. Rotacja tokena endpointu odbywa się w dashboardzie i wymaga wpisania nowego tokena tylko w danej wtyczce.

## Reguły i zakres

Konstruktor obsługuje trzy typy reguł: fragment tekstu (bez rozróżniania wielkości liter), adres e-mail oraz PESEL. Przyciski + E-mail i + PESEL wypełniają gotowe szablony — kliknij Zapisz regułę, aby je aktywować. Poziomy: info, warning, critical. Reguły można edytować, wyłączać i usuwać. Przycisk Sprawdź dopasowanie wysyła tekst do własnego kolektora, ale nie zapisuje go jako zdarzenia ani reguły; próba wyłączonej reguły zwraca brak dopasowania.

Detektor e-mail wykrywa typowe adresy ASCII z domeną zawierającą kropkę, a nie pełny zakres RFC ani adresy międzynarodowe. Detektor PESEL szuka ciągu 11 cyfr i weryfikuje datę urodzenia (stulecia 1800–2299) oraz sumę kontrolną; nie sprawdza nadania numeru w rejestrze. Są to sygnały obserwowalności: nie blokują wysyłania i nie maskują danych. Nie ma wykonywania dowolnych regexów użytkownika.

Przy uruchomieniu serwer automatycznie dodaje kolumny typu i stanu do starej bazy; istniejące reguły pozostają aktywnymi regułami tekstowymi. Zrób kopię bazy przed aktualizacją. Wynik jest utrwalany przy zapisie — zmiana lub usunięcie reguły nie zmienia historii. Dashboard filtruje ostatnie 1000 zdarzeń po tekście, dostawcy i poziomie. Odświeżanie jest ręczne.

To wersja dla jednego administratora, wielu instalacji wtyczki i niewielkiego ruchu. Nie obejmuje retencji, osobnych kont i uprawnień użytkowników, alertów zewnętrznych, redakcji danych ani metryk odpowiedzi/tokenów. Standardowy serwer HTTP Pythona jest prostym kolektorem za tunelem; przed wdrożeniem dla wielu użytkowników potrzebne są utwardzenie, limity ruchu i zarządzanie tożsamościami. Kopię SQLite wykonuj przez mechanizm backup SQLite, uwzględniając tryb WAL.

Cloudflare, LXC i przechwytywanie na żywych stronach nie są zweryfikowane przez testy API.

## Paczki i GitHub Releases

Workflow `.github/workflows/packages.yml` sprawdza API, JavaScript, paczkę wtyczki i działanie Compose. Pull requesty budują obraz bez publikacji. Push na main publikuje obraz `ghcr.io/lpioro/codex:edge` i tag powiązany z SHA. Tag wydania np. `v0.3.0` publikuje `ghcr.io/lpioro/codex:0.3.0` oraz `latest` dla stabilnej wersji, a następnie tworzy GitHub Release z ZIP-em wtyczki, sumą SHA-256, compose.yaml, .env.example i README. Obecny obraz jest budowany dla linux/amd64.

Workflow używa wbudowanego GITHUB_TOKEN; nie wymaga dodawania PAT. GitHub Actions musi być włączone, a polityka organizacji musi zezwalać na publikację pakietów. Widoczność pakietu GHCR ustaw w jego ustawieniach: dla pobierania bez logowania musi być publiczny. Przy prywatnym pakiecie odbiorca musi wykonać docker login ghcr.io z uprawnieniem odczytu pakietu. Pierwszy push konfiguracji nie potwierdza jeszcze, że workflow zakończył się sukcesem.

### Instalacja gotowej wersji bez budowania

Pobierz compose.yaml i .env.example z wybranego GitHub Release do jednego katalogu. Skopiuj .env.example do .env, zabezpiecz go prawami 600, ustaw własny PROMPT_TOKEN i dodaj `PROMPT_IMAGE=ghcr.io/lpioro/codex:0.3.0` (podstaw rzeczywistą opublikowaną wersję). Potem:

```bash
docker compose pull observatory
docker compose up -d --no-build
# Z opcjonalnym tunelem i skonfigurowanym TUNNEL_TOKEN:
docker compose --profile tunnel pull
docker compose --profile tunnel up -d --no-build
```

ZIP wtyczki rozpakuj do osobnego katalogu. W chrome://extensions wybierz tryb dewelopera i załaduj rozpakowany katalog zawierający manifest.json. ZIP nie instaluje się automatycznie i nie zapewnia aktualizacji z Chrome Web Store. Adres kolektora i token skonfiguruj w ustawieniach wtyczki.

### Przygotowanie następnego wydania

Zaktualizuj version w extension/manifest.json, zatwierdź zmiany i sprawdź workflow. Tag musi zgadzać się z wersją manifestu:

```bash
python3 scripts/package_extension.py --version 0.3.0
# Dopiero gdy chcesz opublikować tę wersję:
git tag v0.3.0
git push origin v0.3.0
```

Lokalna paczka i suma kontrolna powstają w ignorowanym katalogu dist. W ZIP-ie znajduje się manifest i cztery jawnie wskazane pliki wtyczki; baza i sekrety nie są dołączane. Zawartość archiwum jest powtarzalna dla tych samych źródeł. W razie błędu wersji publikacja zatrzymuje się przed wysłaniem obrazu i utworzeniem Release. Status publikacji sprawdzaj w zakładce Actions repozytorium; sam tag nie dowodzi gotowości paczek.

## Baza demonstracyjna

```bash
python3 -m server.demo
# Uruchom z tokenem ustawionym zgodnie z instrukcją lokalną:
PROMPT_DB=data/walleeguard-demo.sqlite3 python3 -m server.app
```

Tworzy osobny plik data/walleeguard-demo.sqlite3: **12 endpointów, 5 grup, 14 reguł (13 aktywnych) i 720 promptów** z trzech dostawców, z datami z ostatnich 7 dni i większym ruchem w ostatnich dwóch dniach. Przykłady obejmują e-mail, PESEL, poufny dokument, dane logowania, próbę nadpisania instrukcji, SQL, umowę i wyłączoną regułę telefonu. Są również prompty bez alarmu, numery z błędną sumą kontrolną i zdarzenia z wieloma dopasowaniami. Reguła instrukcji jest prostym dopasowaniem tekstu, a nie kompletną detekcją prompt injection.

Wszystkie treści mają znacznik [DEMO], adresy używają domen example.com/example.org, a dane logowania są fikcyjne. Poprawny numer PESEL jest syntetycznym przykładem walidacji — nie ma gwarancji, że nie został komuś nadany. Nie łącz tych treści z rzeczywistą tożsamością.

Workflow pakowania dołącza gotowy plik walleeguard-demo.sqlite3 do artefaktów i przyszłych GitHub Releases. Źródła znajdują się w server/demo_data.json, wraz z oczekiwanymi dopasowaniami każdego promptu. Generator sprawdza wyniki przez rzeczywisty silnik reguł. Nigdy nie nadpisuje istniejącego pliku, także pustego; dla kolejnej kopii podaj np. --output data/demo-2.sqlite3. Właściwa baza prompts.sqlite3 nie jest zmieniana. Demo nie zawiera tokenów.

### Demo w Docker Compose

Po ustawieniu PROMPT_TOKEN w .env:

```bash
docker compose -p walleeguard-demo -f compose.demo.yaml up -d --build
# Dashboard demo jest na lokalnym porcie 8788.
docker compose -p walleeguard-demo -f compose.demo.yaml down
```

Wymaga Compose 2.24.4+ (tag !override). Demo używa osobnego wolumenu demo-prompts i portu 8788, więc może działać równolegle z właściwą aplikacją. DEMO_PORT pozwala zmienić port. Przy pierwszym starcie baza jest tworzona automatycznie; restarty zachowują zmiany reguł i nowe zdarzenia. Usunięcie danych demo wymaga świadomego użycia down -v z tym samym projektem i plikiem. Aby po pobraniu gotowego obrazu uruchomić demo bez budowania, ustaw PROMPT_IMAGE i użyj up -d --no-build.

## Wiele instalacji wtyczki (od 0.3.0)

Każdy profil Chrome jest osobnym endpointem, z nazwą, grupą, identyfikatorem UUID i własnym tokenem. Ten sam kolektor obsługuje wiele endpointów. Rozszerzenie generuje lokalny UUID instalacji w chrome.storage.local (bez synchronizacji i fingerprintingu); pierwsze połączenie paruje go z tokenem. Użycie tego samego tokena przez inny profil jest odrzucane. Nowa instalacja lub profil wymaga nowego endpointu albo rotacji tokena.

Dashboard pokazuje endpoint i grupę przy każdym zdarzeniu, filtr po endpointach, wersję wtyczki, liczbę logów oraz ostatni kontakt. Nazwy i grupy historycznych logów odzwierciedlają aktualne etykiety endpointu. Heartbeat jest wysyłany co około minutę, także przy wyłączonym przechwytywaniu. „Ostatnio widziany” oznacza kontakt w ciągu ostatnich trzech minut, a nie potwierdzenie działania Chrome, włączonego przechwytywania czy stałego połączenia. Przeglądarka może opóźniać alarmy w tle.

Token endpointu:
- jest widoczny tylko po utworzeniu lub rotacji; w bazie zapisany jest jego SHA-256;
- umożliwia tylko POST /api/events i POST /api/heartbeat;
- nie pozwala czytać logów, reguł ani listy endpointów lub zarządzać konfiguracją;
- jest przypisywany do zdarzeń po stronie serwera, więc wtyczka nie może podać tożsamości innego endpointu;
- może zostać cofnięty bez usuwania historii; rotacja unieważnia stary token i pozwala ponownie sparować profil.

Zdarzenia z różnych endpointów mają osobne przestrzenie identyfikatorów, więc jednakowe identyfikatory klientów nie usuwają sobie wzajemnie logów. Reguły pozostają wspólne dla wszystkich endpointów; nie ma jeszcze odrębnych polityk grupowych ani odrębnych kont administratorów.

### Aktualizacja starszych instalacji

1. Wykonaj kopię bazy SQLite i zaktualizuj serwer.
2. Migracja doda tabelę endpointów i kolumnę endpoint_id; stare logi pozostają jako Nieprzypisane / starsze wersje.
3. Zainstaluj/przeładuj wtyczkę 0.3.0 i w dashboardzie utwórz osobny endpoint dla każdego profilu.
4. Wyślij starą kolejkę przed aktualizacją albo usuń ją świadomie w ustawieniach. Zmiana tokena lub serwera z niepustą kolejką jest blokowana, aby nie przypisać dawnych logów do innego endpointu.
5. Wpisz token endpointu we wtyczce i zapisz ustawienia. To wykonuje heartbeat oraz parowanie; w razie błędu nowa konfiguracja nie zastępuje działającej.
6. Jeśli wcześniej udostępniałeś token administratora wtyczkom, po przeniesieniu ich na dedykowane tokeny zmień PROMPT_TOKEN na serwerze. Dla zgodności integracje używające tokena administratora nadal mogą wysyłać zdarzenia, ale trafiają one wyłącznie do logów nieprzypisanych.

Nie da się odzyskać nazwy urządzenia ani przypisać starych logów automatycznie — wcześniej nie były zbierane takie dane. Cofnięcie dostępu blokuje kolejne żądania; lokalna kolejka pozostaje w profilu i może zostać usunięta w ustawieniach. Przy rotacji tokena z zaległymi promptami najpierw usuń starą kolejkę albo świadomie wyślij ją przed rotacją. Sparowanie identyfikuje profil, ale skopiowanie całego profilu wraz z tokenem i UUID nie stanowi odrębnej, uwierzytelnionej tożsamości urządzenia.

Dodatkowy test rozszerzenia: node tests/extension_background.test.cjs. Sprawdza stabilność UUID, metadane zdarzeń, kolejkę offline i zabezpieczenie zmiany serwera/tokena; nie zastępuje ręcznej kontroli przechwytywania na stronach dostawców AI.

## Konsola, grupy i wykresy

Dashboard ma jasny układ inspirowany konsolami chmurowymi, z nawigacją po prawej (na telefonie nad treścią): Przegląd, Zdarzenia, Alerty, Endpointy, Grupy i Reguły. Wykresy SVG działają lokalnie bez CDN i bibliotek analitycznych. Bootstrap pozostaje lokalnym arkuszem CSS.

Filtry czasu (1 h / 24 h / 7 dni / 30 dni / cała historia), grupy, endpointu, dostawcy i ważności dotyczą logów i wykresów. W widoku Zdarzenia można też wyszukiwać treść; aktywne wyszukiwanie obowiązuje we wszystkich widokach i jest zaznaczone nad wynikami. Wyczyść resetuje wszystkie filtry. Kliknięcie słupka dostawcy lub ważności ustawia odpowiedni filtr. Dane mogą odświeżać się co 30 sekund, gdy karta jest widoczna; opcję można wyłączyć.

/api/analytics liczy cały przefiltrowany zbiór, podczas gdy /api/events zwraca maksymalnie 1000 wyników po zastosowaniu filtrów. Alert to prompt z co najmniej jednym dopasowaniem. W rozkładzie ważności prompt liczony jest raz, według najwyższego poziomu. Najczęstsze sygnały liczą dopasowania poszczególnych reguł, więc ich suma może być większa niż liczba promptów z alertem. To alerty w dashboardzie; nie są wysyłane powiadomienia zewnętrzne.

Grupy można tworzyć, zmieniać nazwy i usuwać, jeśli są puste. Zmiana nazwy aktualizuje przypisanie endpointów; przynależność historycznych logów odpowiada obecnej grupie urządzenia. Można przypisać grupę podczas edycji endpointu; nowa nazwa automatycznie tworzy grupę. Karty grup pokazują liczbę endpointów i logów z całej historii, niezależnie od filtrów analitycznych. Przycisk Analizuj ruch przechodzi do przeglądu z filtrem grupy. Grupy służą organizacji i filtrowaniu, a nie izolacji uprawnień ani osobnym politykom reguł.

Generator demo tworzy 720 promptów z 12 profili w zespołach Finanse, Inżynieria, HR, QA i Obsługa klienta. Zawiera też przykłady fikcyjnych kluczy API, danych płacowych, zdrowotnych, eksportów i dokumentów finansowych. Można zmienić rozmiar: python3 -m server.demo --output data/demo-large.sqlite3 --events 1440 (minimum liczba scenariuszy źródłowych, maksimum 10000). Istniejące bazy demo nie są automatycznie uzupełniane — utwórz nowy plik lub nowy wolumen, aby zachować dotychczasowe dane.
