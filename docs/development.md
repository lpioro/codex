# Rozwój, testy i publikowanie

[Powrót do README](../README.md)

## Struktura

| Ścieżka | Rola |
|---|---|
| extension/ | Chrome MV3: przechwytywanie, blokowanie, kolejka, opcje i ikony |
| server/app.py | HTTP API, uwierzytelnienie i migracje SQLite |
| server/rules.py | Detektory serwerowe |
| extension/rules.js | Lokalny silnik krytycznych reguł |
| server/analytics.py | Wspólne filtry oraz agregacje wykresów |
| server/static/ | Dashboard, Bootstrap i branding |
| server/demo.py, server/demo_data.json | Generator i scenariusze demo |
| scripts/package_extension.py | Powtarzalny ZIP i SHA-256 |
| tests/ | API, migracje, detektory, pakowanie i integracje |
| .github/workflows/packages.yml | CI, GHCR i GitHub Releases |

Kod Pythona nie wymaga pip install. Node.js służy do sprawdzania JavaScriptu, nie do uruchamiania serwera. Nie są wymagane npm install ani kompilacja frontendu.

## Kontrole

Z katalogu repozytorium:

```bash
python3 -m unittest discover -s tests -v
node tests/extension_background.test.cjs
node tests/extension_rules.test.cjs
node --check extension/content.js
node --check extension/options.js
node --check server/static/app.js
docker build -t prompt-observatory:local .
python3 tests/docker_smoke.py
```

Testy API wymagają lokalnego gniazda HTTP. Test Compose tworzy własny projekt i wolumen, zajmuje lokalny port 18787 i usuwa własne dane po zakończeniu. Używa obrazu prompt-observatory:local.

Opcjonalnie:

```bash
python3 tests/browser_guard.py
```

Wymaga osobno zainstalowanych Playwright i Chromium; BROWSER_BIN może wskazać binarkę. Test używa kontrolowanych stron, nie prawdziwych rozmów z AI. Sprawdza zdarzenia DOM trzech dostawców, blokadę, odtworzenie dozwolonej wysyłki i awarie. Nie potwierdza pełnego uruchomienia rozszerzenia w profilu ani zgodności ze wszystkimi bieżącymi witrynami.

W lokalnych sprawdzeniach wersji 0.4.0 przeszło 20 testów Pythona, 3 testy JS, scenariusze DOM w Chromium i budowanie Dockera. Cloudflare/LXC oraz rzeczywiste witryny wymagają osobnej walidacji.

## Paczka rozszerzenia

```bash
python3 scripts/package_extension.py --version 0.4.0
```

W dist powstają ZIP i .zip.sha256. Archiwum zawiera jawnie wskazane pliki kodu, CSS, manifest i ikony; manifest.json jest w jego korzeniu. Nie zawiera tokenów ani bazy. Zawartość jest powtarzalna dla tych samych plików źródłowych.

Po rozpakowaniu sprawdź sumę SHA-256 narzędziem dostępnym w systemie. Wersja oczekiwana przez skrypt musi zgadzać się z extension/manifest.json.

## CI i obrazy

- Pull request: walidacja, paczka i testowy build bez publikacji.
- Push na main: walidacja, build/test Compose, publikacja tagów edge i SHA.
- Tag vX.Y.Z: sprawdzenie wersji manifestu, publikacja obrazu wersjonowanego i latest dla stabilnego wydania, potem GitHub Release.
- Workflow dispatch: ręczne uruchomienie zgodnie z wybraną referencją.

Obraz jest budowany dla linux/amd64. Publikowanie używa GITHUB_TOKEN z uprawnieniami packages:write i contents:write tylko w odpowiednich zadaniach. Ustawienia organizacji mogą zabronić publikacji; prywatny pakiet wymaga logowania odbiorcy.

## Następne wydanie

1. Zmień wersję manifestu i uaktualnij CHANGELOG.md.
2. Dodaj docs/releases/vX.Y.Z.md z opisem dla użytkowników.
3. Uruchom wymagane testy i skrypt pakowania z nową wersją.
4. Wyślij kod na uzgodnioną gałąź; przejrzyj wyniki CI.
5. Utwórz **nowy**, nieistniejący tag wskazujący sprawdzony commit i wyślij go.
6. Sprawdź status Actions, pliki Release i dostępność tagu GHCR.

Tag v0.4.0 został już wysłany; nie uruchamiaj ponownie przykładu jego tworzenia i nie przesuwaj go. Aktualizacja dokumentacji na gałęzi feature/walleeguard-next nie zmienia automatycznie istniejącego wydania ani jego załączników.

Workflow użyje przygotowanego opisu z docs/releases/TAG.md, jeśli plik istnieje w wydawanym commicie; w innym przypadku wygeneruje notatki GitHub. Zapis dokumentu nie edytuje sam w sobie opisu opublikowanego wydania.

## Wkład w projekt

Przy zmianie detektora utrzymuj zgodność implementacji Python i JavaScript oraz dodaj przykłady pozytywne i negatywne. Przy zmianie selektorów sprawdzaj wszystkie ścieżki wysyłania, zachowanie szkicu i pojedynczą wysyłkę bez duplikatów. Używaj wyłącznie syntetycznych danych w testach.

Przy zgłoszeniu błędu podaj wersję wtyczki/serwera, dostawcę AI, sposób wysyłania i oczekiwane zachowanie. Nie dołączaj prawdziwych promptów, tokenów ani plików bazy.
