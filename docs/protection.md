# Reguły i ochrona promptów

[Powrót do README](../README.md)

## Detektory

| Typ | Dopasowanie | Granice |
|---|---|---|
| contains | Dosłowny fragment bez rozróżniania wielkości liter, z Unicode casefold | Nie rozpoznaje znaczenia, parafraz ani intencji |
| email | Typowy adres ASCII z domeną zawierającą kropkę | Nie jest pełnym walidatorem RFC ani adresów międzynarodowych |
| pesel | 11 cyfr, poprawna data w stuleciach 1800–2299 i suma kontrolna | Nie sprawdza, czy numer został nadany |

Konstruktor pozwala ustawić nazwę, typ, poziom info/warning/critical i stan aktywności. Nie wykonuje dowolnych regexów użytkownika ani złożonych warunków AND/OR.

Próba w konstruktorze wysyła próbkę tekstu do własnego serwera, ale nie zapisuje zdarzenia ani reguły. Wyłączona reguła zwraca brak dopasowania.

Wyniki reguł w logu są utrwalane przy zapisie. Edycja lub usunięcie reguły nie przelicza historii.

## Dwa niezależne przełączniki

| Logowanie | Blokowanie | Działanie |
|---|---|---|
| Wyłączone | Wyłączone | Brak dodawania nowych logów i lokalnej ochrony |
| Włączone | Wyłączone | Przechwytywanie rozpoznanych prób; action=observed |
| Wyłączone | Włączone | Lokalna kontrola bez zapisu treści w kolektorze |
| Włączone | Włączone | Lokalna kontrola i zapis deklarowanej decyzji allowed/blocked |

Wyłączenie logowania nie usuwa wcześniejszej kolejki. Może ona nadal zostać wysłana; służy do tego osobny przycisk usuwania kolejki. Heartbeaty działają także przy wyłączonym logowaniu.

## Zatrzymywanie przed wysłaniem

Wtyczka 0.4.0 ma domyślnie włączone blokowanie. Przechwytuje rozpoznane Enter/Ctrl+Enter/Command+Enter, kliknięcia przycisku i zdarzenia submit. Shift+Enter oraz kompozycja tekstu nie są traktowane jak wysyłka.

Wtyczka pobiera z kolektora tylko aktywne reguły critical. Prompt jest analizowany lokalnie; nie trafia do API w celu sprawdzenia. Zapis pełnego tekstu jest osobną funkcją logowania.

Dopasowanie pokazuje nazwę reguły i zachowuje szkic. Brak aktualnej polityki, błąd sprawdzania, tekst powyżej 100000 znaków, nierozpoznany edytor lub zmiana tekstu podczas analizy zatrzymują rozpoznaną próbę. Pusty tekst także nie jest odtwarzany jako wysyłka.

Bez dopasowania wtyczka uruchamia rozpoznany przycisk lub formularz, o ile szkic się nie zmienił. **Nie ma jednorazowego przycisku pominięcia**. Można poprawić treść, zmienić regułę albo świadomie wyłączyć ochronę. Przycisk Wyłącz blokowanie lokalnie działa również offline.

Pusta, poprawna polityka jest dozwolona: gdy brak aktywnych reguł critical, nie ma krytycznych wzorców do zatrzymywania.

## Cache i brak połączenia

| Sytuacja | Zachowanie |
|---|---|
| Polityka młodsza niż 60 s | Kontrola lokalna bez ponownego pobrania |
| Starsza polityka | Próba pobrania aktualnych reguł |
| Awaria połączenia, kopia młodsza niż 5 min | Kontrola według lokalnej kopii |
| Brak kopii lub wiek co najmniej 5 min | Zatrzymanie rozpoznanej wysyłki |
| Odpowiedź API odmawia dostępu, np. 401/403/409 | Brak zgody na użycie starej kopii przy tej próbie odświeżenia |

Cache jest powiązany z adresem kolektora i tokenem. Zmiana reguł i cofnięcie tokena nie propagują się natychmiast do świeżej kopii. Wtyczka nie ma stale otwartego kanału push.

## Co znaczą decyzje

observed/allowed/blocked to deklaracje klienta. allowed nie potwierdza, że strona przyjęła syntetyczne kliknięcie ani że dostawca otrzymał prompt. blocked nie jest sprzętowym dowodem zatrzymania transmisji.

Wynik krytycznych reguł w kolektorze jest liczony ponownie przy zapisie logu. Może różnić się od decyzji lokalnej, jeśli reguły zmieniły się w czasie życia cache.

## Dane i ograniczenia

Token i kolejka są w chrome.storage.local, bez synchronizacji. Nie są szyfrowane przez aplikację. Kolejka mieści 100 zdarzeń; pełna kolejka odrzuca nowe logi i zapisuje błąd. Brak miejsca w kolejce nie wyłącza blokowania. Zmiana serwera lub tokena z zaległą kolejką jest zatrzymywana, żeby nie przypisać logów do innego endpointu.

Baza zawiera pełną treść logowanych promptów; nie ma automatycznej redakcji, retencji ani szyfrowania bazy. Przy tunelu treść przechodzi przez infrastrukturę Cloudflare. Nie są zbierane odpowiedzi, historia czatu, adres rozmowy ani zawartość załączników.

To ochrona rozpoznanych ścieżek DOM na ChatGPT, Claude i Gemini, nie filtr wszystkich żądań sieciowych. Nie obejmuje głosu, obrazów, załączników, parafraz ani każdego zagrożenia semantycznego. Zmiana interfejsu dostawcy, bezpośrednie wywołanie sieciowe lub programowe wysłanie poza obsługiwanymi zdarzeniami może ominąć mechanizm.

Testy Chromium używają kontrolowanych formularzy. Pełne ładowanie rozszerzenia w profilu testowym i zgodność ze wszystkimi aktualnymi witrynami nie są potwierdzone tymi testami.
