# API kolektora

[Powrót do README](../README.md)

API i dashboard mają wspólny adres. Żądania POST używają Content-Type: application/json, a chronione operacje nagłówka Authorization: Bearer TOKEN. CORS dla stron trzecich nie jest publicznie otwarty; wtyczka korzysta z uprawnień hosta Chrome.

## Uprawnienia

| Tożsamość | Dostęp |
|---|---|
| Bez tokena | GET /health i statyczne pliki dashboardu |
| Administrator: PROMPT_TOKEN | Odczyt logów i analityki, zarządzanie regułami, grupami i endpointami |
| Token endpointu | POST /api/events, POST /api/heartbeat i POST /api/policy |

Administrator może także wysłać zdarzenie bez endpointu dla zgodności ze starszymi integracjami. Nie może przy tym podać endpoint_id, aby udawać instalację. POST /api/policy i heartbeat wymagają dedykowanego tokena endpointu.

Endpoint podaje instance_id i opcjonalnie version. Pierwszy kontakt wiąże token z profilem. Identyfikator endpointu do logu pochodzi z uwierzytelnienia; podanie innego endpoint_id jest odrzucane.

## Trasy

| Metoda | Ścieżka | Operacja |
|---|---|---|
| GET | /health | Status procesu |
| GET | /api/events | Maksymalnie 1000 przefiltrowanych zdarzeń, od najnowszych |
| GET | /api/analytics | Agregacje całego przefiltrowanego zbioru |
| GET / POST | /api/rules | Lista / utworzenie reguły |
| POST | /api/rules/ID | Edycja reguły |
| DELETE | /api/rules/ID | Usunięcie reguły |
| POST | /api/rules/test | Próba reguły, bez zapisu |
| GET / POST | /api/endpoints | Lista / utworzenie endpointu |
| POST | /api/endpoints/UUID | Zmiana nazwy i grupy |
| POST | /api/endpoints/UUID/revoke | Cofnięcie dostępu |
| POST | /api/endpoints/UUID/rotate | Nowy token i ponowne parowanie |
| GET / POST | /api/groups | Lista / utworzenie grupy |
| POST | /api/groups/ID | Zmiana nazwy grupy i przypisań endpointów |
| DELETE | /api/groups/ID | Usunięcie pustej grupy |
| POST | /api/heartbeat | Kontakt i parowanie profilu |
| POST | /api/policy | Aktywne reguły critical i hash wersji, bez analizy promptu |

Nowe endpointy i reguły oraz zapis zdarzeń zwracają 201. Operacje grup i aktualizacje zwracają 200. Ciała są JSON; usunięcie zwykle zwraca {"ok":true}. Edycja odbywa się przez POST, nie PATCH/PUT.

## Filtry zdarzeń i analityki

| Parametr | Wartości / znaczenie |
|---|---|
| q | Fragment promptu z Unicode casefold |
| provider | chatgpt, claude, gemini |
| endpoint_id | UUID endpointu; legacy dla nieprzypisanych |
| group | Dokładna nazwa; __none__ dla braku grupy |
| severity | info, warning, critical; co najmniej jedno dopasowanie tego poziomu |
| action | observed, allowed, blocked |
| alerts | 1 oznacza co najmniej jedno dopasowanie |
| range | 1h, 24h, 7d, 30d, all |

Domyślny zakres GET /api/events to cała historia; GET /api/analytics to 24h. Dashboard jawnie przesyła wybrany zakres, żeby listy i wykresy odpowiadały sobie. Filtry są stosowane przed limitem listy. Lista nie ma obecnie kursora paginacji.

Analityka zwraca m.in. total, alerts, blocked, critical, endpoints, severity, providers, groups, top_rules, buckets i generated_at. severity i segmenty alertów liczą najwyższy poziom promptu; top_rules liczy osobne dopasowania. Liczba koszyków czasu zależy od zakresu.

## Przykładowe ciała

Utworzenie endpointu jako administrator:

```json
{"name":"Laptop Anny — Chrome","group_name":"Finanse"}
```

Odpowiedź zawiera id, name, group_name i **token widoczny tylko teraz**. Lista endpointów nie zwraca tokenów ani ich hashy. Rotacja również zwraca nowy token tylko raz.

Reguła PESEL:

```json
{"name":"Dane osobowe — PESEL","type":"pesel","severity":"critical","enabled":true}
```

Dla type=contains wymagane jest contains. Typy email/pesel nie potrzebują wzorca. Nazwa ma 1–100 znaków, wzorzec do 500 znaków. Próba /api/rules/test przyjmuje te same pola oraz text do 100000 znaków i zwraca {"matched":true} lub false.

Zdarzenie od endpointu:

```json
{
  "id":"unikalny-identyfikator-próby",
  "provider":"chatgpt",
  "prompt":"Przykładowe zapytanie bez danych osobowych",
  "instance_id":"stabilny-uuid-profilu",
  "version":"0.4.0",
  "action":"allowed"
}
```

id ma 1–100 znaków, prompt 1–100000 znaków, instance_id 1–100 znaków, version do 40 znaków. Brak action oznacza observed. Serwer nadaje czas odbioru UTC; klient nie ustawia go w API. Ponowne przesłanie tego samego id w danym endpoincie nie tworzy duplikatu; identyczne id innego endpointu jest osobnym zdarzeniem.

Heartbeat i polityka:

```json
{"instance_id":"stabilny-uuid-profilu","version":"0.4.0"}
```

Polityka zwraca {"version":"SHA-256","rules":[...]}. Reguły zawierają id, name, type, contains i severity; wyłącznie aktywne critical. Nie jest to endpoint do wysyłania promptu ani pełna lista reguł administracyjnych.

## Odpowiedzi błędów

| Kod | Typowy powód |
|---|---|
| 400 | Błędny JSON, dane reguły, filtr lub metadane profilu |
| 401 | Brak właściwego tokena lub token cofnięty |
| 403 | Próba operacji administracyjnej tokenem wtyczki, podszycie się pod endpoint, niewłaściwa rola |
| 404 | Nieznana trasa lub brak edytowanego obiektu |
| 409 | Token sparowany z innym profilem, istniejąca nazwa grupy lub próba usunięcia zajętej grupy |
| 413 | Ciało żądania puste lub większe niż 650000 bajtów |

Ciało błędu ma pole error. Nie loguj nagłówków Authorization ani tokenów do narzędzi diagnostycznych.
