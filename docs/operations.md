# Utrzymanie i rozwiązywanie problemów

[Powrót do README](../README.md)

## Aktualizacja

1. Wykonaj kopię SQLite.
2. Przy budowaniu z kodu pobierz zmiany i uruchom docker compose up -d --build. Przy gotowym obrazie zmień PROMPT_IMAGE na potwierdzoną wersję, wykonaj pull i up -d --no-build.
3. Sprawdź healthcheck, logowanie i zachowanie dotychczasowych reguł.
4. Rozpakuj nowy ZIP wtyczki lub zaktualizuj katalog extension, przeładuj rozszerzenie w chrome://extensions.
5. Odśwież karty dostawców AI i sprawdź próbny, nieszkodliwy prompt oraz kontrolowany wzorzec krytyczny.

Migracje przy starcie dodają pola reguł, endpointy, grupy i action. Stare logi zostają nieprzypisane i mają action=observed. Nie da się automatycznie odzyskać ich dawnych urządzeń. Nowy serwer nie przelicza historycznych dopasowań.

Wtyczka 0.4.0 potrzebuje API polityki z serwera 0.4.0. Najpierw aktualizuj serwer. Nie przenoś istniejącego taga wydania na inne commity.

## Przejście ze wspólnego tokena

Utwórz osobny endpoint dla każdego profilu. Wyślij starą kolejkę przed przejściem albo świadomie usuń ją w ustawieniach. Zmiana serwera lub tokena z zaległymi promptami jest blokowana.

Po przeniesieniu instalacji zmień stary PROMPT_TOKEN, jeśli był udostępniany wtyczkom. Wymaga to odtworzenia kontenera i ponownego logowania administratora; dedykowane tokeny endpointów nie zmieniają się.

Zmiana tokena pojedynczej wtyczki odbywa się w dashboardzie przez rotację. Cofnięcie dostępu i rotacja zachowują logi.

## Kopia SQLite w Dockerze

Mechanizm backup kopiuje spójny stan również przy WAL. Poniższa komenda zapisuje kopię w katalogu /data/backups w istniejącym wolumenie:

```bash
docker compose exec -T observatory python - <<'PY'
import os, sqlite3
from pathlib import Path
from datetime import datetime, timezone
folder = Path('/data/backups')
folder.mkdir(mode=0o700, exist_ok=True)
path = folder / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
source = sqlite3.connect(os.environ['PROMPT_DB'])
destination = sqlite3.connect(path)
try:
    source.backup(destination)
finally:
    destination.close()
    source.close()
path.chmod(0o600)
print(path)
PY
```

Skopiuj wskazany plik poza wolumen, np. docker compose cp observatory:/data/backups/NAZWA.sqlite3 ./NAZWA.sqlite3. Kopia tylko w tym samym wolumenie nie chroni przed jego usunięciem.

## Odtworzenie

Zatrzymaj aplikację, zachowaj dotychczasowy wolumen i przetestuj kopię w osobnym projekcie. Dla standardowego Compose można użyć nowego katalogu z compose.yaml/.env oraz **innej nazwy projektu**.

Przykład zapisania kopii do **nowego** wolumenu bez uruchamiania serwera i bez nadpisywania istniejącego pliku:

```bash
# W nowym katalogu z compose.yaml i ustawionym .env.
# backup.sqlite3 to istniejąca, wcześniej sprawdzona kopia.
docker compose -p walleeguard-restore run --rm --no-deps -T --entrypoint python observatory -c '
import os, shutil, sqlite3, sys
from pathlib import Path
target = Path(os.environ["PROMPT_DB"])
with target.open("xb") as output:
    shutil.copyfileobj(sys.stdin.buffer, output)
target.chmod(0o600)
db = sqlite3.connect(target)
try:
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
finally:
    db.close()
print("Kopia zapisana i sprawdzona")
' < ./backup.sqlite3
```

Nowy nazwany wolumen przejmuje uprawnienia katalogu /data z obrazu. Import działa jako użytkownik aplikacji, bez dodawania uprawnień kontenerowi. Istniejący plik powoduje przerwanie przez tryb xb. Zachowaj oryginalny backup również po imporcie.

Nie uruchamiaj obu projektów na tym samym porcie: ustaw inny PORT dla projektu odtworzeniowego. Uruchom go po sprawdzeniu uprawnień i integralności bazy. Nigdy nie kopiuj samego aktywnego głównego pliku SQLite z pominięciem WAL zamiast wykonywać backup.

## Diagnostyka

| Objaw | Co sprawdzić |
|---|---|
| Dashboard 401 | Użyj PROMPT_TOKEN, nie tokena endpointu |
| Parowanie odrzucone 403 | Wtyczka wymaga dedykowanego tokena endpointu |
| Token sparowany z innym profilem / 409 | Utwórz drugi endpoint lub wykonaj świadomą rotację |
| Brak logów | Włącz logowanie, odśwież kartę AI, sprawdź kolejkę i ostatni błąd w ustawieniach |
| Prompt zatrzymany bez dopasowania | Aktualność polityki, dostępność serwera, długość tekstu i rozpoznanie edytora |
| Nie działa zmieniona reguła | Stan aktywności, poziom critical, do 60 s cache; logi historyczne nie są przeliczane |
| E-mail nie blokuje | Szablon e-mail domyślnie ma warning; do blokowania potrzebuje critical |
| Nie można zmienić serwera/tokena | Najpierw wyślij albo świadomie usuń kolejkę |
| Tunel nie widzi aplikacji | W Compose cel to http://observatory:8787, nie localhost |
| Brak obrazu lub Release | Sprawdź Actions i uprawnienia publikacji; tag nie dowodzi sukcesu |
| Demo nadal ma stary zestaw | Generator nie nadpisuje bazy; utwórz nowy plik lub osobny wolumen |
| Brak wyników | Sprawdź zakres czasu, grupę, decyzję i wyszukiwanie; użyj Wyczyść |
| Grupa nie daje się usunąć | Przenieś przypisane endpointy |

Przy awarii można świadomie wyłączyć blokowanie lokalnie w ustawieniach rozszerzenia, także offline. Oznacza to rezygnację z zatrzymywania promptów, a nie naprawę połączenia.

## Granice utrzymania

To lekki kolektor dla jednego administratora i niewielkiego ruchu. Brak automatycznej retencji, odrębnych kont, limitowania żądań i powiadomień zewnętrznych. Agregacje czytają przefiltrowany zbiór; duża baza wymaga oceny wydajności. Logi i kopie zawierają pełną treść promptów.

Nie używaj docker compose down -v do zwykłego restartu — usuwa wolumeny projektu. Sam restart procesu nie usuwa bazy.
