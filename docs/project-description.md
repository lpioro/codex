# Opisy projektu do publikacji

Poniższe teksty są gotowe do użycia w metadanych repozytorium, pakietu lub wydania. Ten plik sam nie aktualizuje GitHub About, GHCR ani Chrome Web Store.

## Krótki opis repozytorium

WalleeGuard: prywatne logi promptów AI, lokalne blokowanie krytycznych treści i dashboard wielu instalacji Chrome.

## Opis pakietu serwera

WalleeGuard Collector zawiera API Python, dashboard i obsługę SQLite oraz generator danych demo. Obraz służy do uruchomienia własnego kolektora i panelu administratora. Chrome extension i Cloudflare Tunnel są osobnymi komponentami.

## Opis rozszerzenia

WalleeGuard pomaga obserwować prompty wysyłane przez rozpoznane interfejsy ChatGPT, Claude i Gemini. Każdy profil Chrome ma własną tożsamość endpointu. Administrator definiuje reguły tekstowe, e-mail i PESEL; aktywne reguły krytyczne mogą zatrzymać rozpoznaną próbę wysłania jeszcze w przeglądarce.

Analiza ochronna działa lokalnie według polityki z własnego kolektora. Oddzielnie włączane logowanie przesyła pełną treść prób, także zablokowanych, do prywatnej bazy. Token i kolejka są przechowywane lokalnie w profilu. Wtyczka nie zbiera odpowiedzi ani załączników.

Ochrona dotyczy rozpoznanych ścieżek wysyłania tekstu, nie wszystkich żądań sieciowych i nie każdego rodzaju zagrożenia. Zmiany witryn dostawców mogą wymagać aktualizacji selektorów.

## Dla kogo

Dla osoby lub małego zespołu chcącego utrzymywać własny rejestr promptów, rozdzielać ruch profili Chrome i wykrywać konkretne wzorce w treści. Jeden administrator zarządza wspólną bazą i regułami. Grupy służą organizacji, nie izolacji uprawnień.

## Czego nie obiecuje

Brak kompletnego DLP, oceny semantycznej każdego promptu, analizy plików, osobnych kont administratorów, automatycznej retencji i powiadomień zewnętrznych. Obecny ZIP ładowany jest w trybie dewelopera, nie przez Chrome Web Store.
