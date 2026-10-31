# Obsługa dashboardu

[Powrót do README](../README.md)

## Widoki

| Widok | Do czego służy |
|---|---|
| Przegląd | Liczby promptów, alertów i blokad, aktywność w czasie, dostawcy, najczęstsze sygnały |
| Zdarzenia | Treść promptu, dostawca, endpoint, grupa, dopasowane reguły i decyzja ochrony |
| Alerty | Prompty z dopasowaniami oraz wykres najwyższej ważności w czasie |
| Endpointy | Dodawanie instalacji, tokeny, etykiety, wersja i ostatni kontakt |
| Grupy | Organizacja endpointów i przejście do analizy ruchu zespołu |
| Reguły wykrywania | Tworzenie, testowanie, edycja, wyłączanie i usuwanie detektorów |

Menu jest po lewej; na telefonie znajduje się nad treścią. Odświeżanie automatyczne działa co 30 sekund tylko przy widocznej karcie. Można je wyłączyć lub użyć przycisku Odśwież.

## Filtry i interpretacja liczb

Filtry czasu, grupy, endpointu, dostawcy, ważności i decyzji ochrony dotyczą logów oraz wykresów. Wyszukiwanie tekstu w widoku Zdarzenia także obowiązuje w innych widokach; nad wynikami widać aktywne wyszukiwanie. Wyczyść resetuje filtry do ostatnich 24 godzin.

Kliknięcie słupka dostawcy lub ważności ustawia filtr. Wybór „Nieprzypisane / starsze wersje” pokazuje historię bez endpointu.

- **Prompty z alertem**: zdarzenia z co najmniej jednym dopasowaniem.
- **Alerty krytyczne**: prompty, których najwyższy poziom dopasowania to critical.
- **Zatrzymane przez wtyczkę**: deklarowane przez rozszerzenie decyzje blocked w wybranym zakresie. Mogą różnić się od liczby alertów krytycznych.
- **Endpointy w ruchu**: liczba różnych endpointów występujących w przefiltrowanych zdarzeniach; nie jest to liczba aktualnie otwartych przeglądarek.
- **Najczęstsze sygnały**: liczba dopasowań każdej reguły. Jeden prompt może zwiększyć kilka liczników.
- Lista pokazuje maksymalnie 1000 zdarzeń po filtrowaniu. Wykresy obejmują cały przefiltrowany zbiór.

To alerty w dashboardzie. Projekt nie wysyła obecnie e-maili ani powiadomień do zewnętrznych systemów.

## Endpointy i tokeny

Endpoint oznacza profil Chrome, a nie sprzętowo poświadczone urządzenie. Nazwij go tak, aby łatwo odróżnić użytkownika, komputer i profil.

Po utworzeniu skopiuj token do jednej wtyczki. Token jest jednorazowo widoczny, a w bazie przechowywany jako SHA-256. Pierwszy kontakt wiąże go z lokalnym UUID profilu. Ten sam token z innym UUID jest odrzucany.

**Cofnij dostęp** blokuje kolejne żądania API, zachowując logi. **Nowy token / ponowne parowanie** unieważnia stary token i pozwala przypisać endpoint do profilu ponownie. Pamiętaj o lokalnym cache polityki blokowania; nie jest natychmiastowym kanałem cofania decyzji.

Zmiana nazwy i grupy aktualizuje etykiety także historycznych logów. Ostatni kontakt pochodzi z heartbeatów i zdarzeń. Heartbeat działa mniej więcej co minutę również przy wyłączonym logowaniu, z możliwymi opóźnieniami przeglądarki. „Ostatnio widziany” oznacza kontakt w ciągu trzech minut.

## Grupy

Dodaj grupę w widoku Grupy lub wpisz nową nazwę przy tworzeniu/edycji endpointu. Zmiana nazwy grupy aktualizuje przypisanie jej endpointów. Usunąć można tylko pustą grupę; najpierw przenieś urządzenia.

Karty grup pokazują liczbę endpointów i logów z całej historii, niezależnie od filtrów analitycznych. Przycisk Analizuj ruch przechodzi do przeglądu z filtrem tej grupy.

Grupy nie izolują dostępu. Jeden administrator widzi wszystkie logi, a wszystkie wtyczki korzystają ze wspólnego zestawu krytycznych reguł.

## Przykład: zatrzymywanie PESEL

1. Otwórz Reguły i wybierz **+ PESEL**.
2. Ustaw poziom critical, pozostaw regułę aktywną i zapisz.
3. We wtyczce włącz blokowanie. Po zmianie reguł uwzględnij do 60 sekund cache.
4. W kontrolowanym teście wpisz syntetyczny numer zgodny z walidatorem, bez łączenia go z rzeczywistą osobą.
5. Po rozpoznanej próbie wysyłki zobaczysz nazwę reguły, a tekst pozostanie w edytorze.
6. Przy włączonym logowaniu wybierz w dashboardzie Decyzja ochrony → Zablokowane próby.

Szablon e-mail ma domyślnie warning: rejestruje dopasowanie, ale sam nie uruchamia blokowania. Zmień poziom na critical, jeśli taki jest zamierzony sposób działania.
