# Demo i przykładowe dane

[Powrót do README](../README.md)

Generator tworzy osobną bazę: **720 promptów, 12 endpointów, 5 grup, 14 reguł — 13 aktywnych**. Daty obejmują ostatnie siedem dni, z większą aktywnością w ostatnich dwóch dniach.

Zespoły: Finanse, Inżynieria, HR, QA i Obsługa klienta. Scenariusze: e-mail, PESEL, poufność, fikcyjne hasła i klucze API, dane płacowe i zdrowotne, dokumenty finansowe, SQL, kod źródłowy, eksport oraz przykłady bez alarmu i niepoprawnych numerów.

## Docker

Po ustawieniu tokena administratora w .env:

```bash
docker compose -p walleeguard-demo -f compose.demo.yaml up -d --build
```

Port hosta: 8788; można zmienić DEMO_PORT. Potrzebny Compose 2.24.4+ ze względu na !override. compose.demo.yaml odwołuje się do compose.yaml — potrzebne są oba pliki.

Przy pierwszym starcie powstaje baza w osobnym wolumenie demo-prompts. Restarty zachowują zmiany i nie dosypują nowych przykładów. Zatrzymanie:

```bash
docker compose -p walleeguard-demo -f compose.demo.yaml down
```

Opcja down -v usuwa ten wolumen. Stosuj ją tylko do świadomego wyczyszczenia projektu demo, z właściwym -p i -f.

## Python i plik SQLite

```bash
python3 -m server.demo
PROMPT_DB=data/walleeguard-demo.sqlite3 python3 -m server.app
```

Wcześniej ustaw PROMPT_TOKEN zgodnie z instrukcją instalacji. Generator nie nadpisuje istniejącego pliku, nawet pustego. Dla innego rozmiaru i kolejnej kopii:

```bash
python3 -m server.demo --output data/demo-large.sqlite3 --events 1440
```

Minimum to liczba scenariuszy źródłowych, obecnie 22; maksimum 10000. Układ czasu jest generowany względem chwili utworzenia bazy. Liczby dla filtra „24 h” będą inne niż dla „7 dni”.

Źródła: server/demo_data.json i server/demo.py. Każdy scenariusz zawiera oczekiwane nazwy dopasowanych reguł; generator sprawdza je rzeczywistym silnikiem. Eksport używa SQLite backup i daje samodzielny plik, bez potrzeby przenoszenia WAL.

## Co jest symulacją

Treści mają znacznik [DEMO], a adresy używają domen example.com/example.org. Hasła i klucze są fikcyjne. Syntetyczny poprawny PESEL nie daje gwarancji, że taki numer nie został nadany — nie wiąż go z rzeczywistą osobą.

Endpointy są przykładami, nie aktywnymi urządzeniami. Ich tokeny nie są udostępniane; aby połączyć własną wtyczkę, utwórz nowy endpoint. Jeden endpoint jest oznaczony jako cofnięty.

Generator zapisuje przykłady jako observed. Nie udaje, że prawdziwa wtyczka zatrzymała te prompty. Niektóre podglądy dashboardu przygotowane w rozmowie używały dodatkowo **symulowanych** decyzji blocked; nie są one domyślną zawartością generatora.

Gotowy plik walleeguard-demo.sqlite3 jest dołączany przez workflow do artefaktów i przyszłych wydań po udanej publikacji. Istniejące bazy i wolumeny nie są automatycznie aktualizowane do większego zestawu.
