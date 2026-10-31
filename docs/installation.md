# Instalacja i konfiguracja

[Powrót do README](../README.md)

## Wymagania

- Docker Engine i Compose v2; demo: Compose 2.24.4+.
- Alternatywnie Python 3.10+, bez zewnętrznych zależności serwera.
- Chrome z możliwością załadowania rozpakowanej wtyczki MV3.
- Do zdalnego połączenia: własny adres HTTPS, np. Cloudflare Tunnel.
- W LXC: nesting, odpowiednie cgroups i wsparcie kernela hosta dla Dockera. Zapewnia je administrator hosta LXC.

## Docker — budowa z repozytorium

W katalogu projektu:

```bash
cp .env.example .env
chmod 600 .env
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Wpisz wynik jako `PROMPT_TOKEN` w lokalnym `.env`. To token administratora, minimum 32 znaki. Zachowaj go na kolejne uruchomienia.

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=50 observatory
curl --fail http://127.0.0.1:8787/health
```

Oczekiwana odpowiedź zdrowia: `{"status":"ok"}`. Sprawdź także logowanie do dashboardu. Sam healthcheck nie potwierdza działania wtyczki.

API i dashboard są jednym serwisem na lokalnym porcie 8787. Kontener działa jako UID/GID 10001, z systemem plików tylko do odczytu, osobnym zapisywalnym wolumenem `prompts` i healthcheckiem. Budowanie uruchamia testy Pythona. Na architekturze amd64 można też użyć gotowego obrazu.

## Gotowe wydanie bez budowania

Pobierz `compose.yaml` i `.env.example` z potwierdzonego GitHub Release do jednego katalogu. Skopiuj przykład do `.env`, ustaw token administratora oraz:

```dotenv
PROMPT_IMAGE=ghcr.io/lpioro/codex:0.4.0
```

```bash
docker compose pull observatory
docker compose up -d --no-build
```

Pakiet GHCR musi być publiczny albo wymaga zalogowania do rejestru z prawem odczytu. Sprawdź status Actions, jeśli tag obrazu nie istnieje. Tag Git nie gwarantuje udanej publikacji.

## Zmienne konfiguracji

| Zmienna | Gdzie | Domyślnie / działanie |
|---|---|---|
| `PROMPT_TOKEN` | Serwer i Compose | Wymagany token administratora, minimum 32 znaki |
| `PROMPT_IMAGE` | Compose | `prompt-observatory:local`; można wskazać opublikowany tag GHCR |
| `PORT` | Compose | Port hosta 8787; wewnątrz kontenera nadal 8787 |
| `DEMO_PORT` | Demo Compose | Port hosta 8788 |
| `TUNNEL_TOKEN` | Profil Compose `tunnel` | Token zdalnie zarządzanego tunelu Cloudflare |
| `HOST` | Bezpośredni proces Python | `127.0.0.1`; obraz Dockera ustawia `0.0.0.0` |
| `PORT` | Bezpośredni proces Python | Port procesu 8787 |
| `PROMPT_DB` | Bezpośredni proces Python | `data/prompts.sqlite3`; obraz ustawia `/data/prompts.sqlite3` |

Standardowy `compose.yaml` przekazuje do aplikacji tylko `PROMPT_TOKEN`; samo wpisanie HOST lub PROMPT_DB do `.env` nie zmienia środowiska kontenera. Zmiany tych parametrów wymagają własnego override Compose. `.env` nie jest dołączany do obrazu ani Gita.

## Chrome — jeden profil, jeden endpoint

1. Zaloguj się do dashboardu tokenem administratora.
2. W menu **Endpointy** dodaj nazwę, np. „Laptop Anny — Chrome”, i opcjonalną grupę.
3. Skopiuj token wyświetlony po utworzeniu. Nie da się później odczytać go z listy.
4. W `chrome://extensions` włącz tryb dewelopera i załaduj katalog `extension` albo rozpakowany ZIP wydania.
5. Kliknij ikonę WalleeGuard. Podaj sam adres kolektora, bez ścieżki, parametrów i danych logowania.
6. Wpisz **token endpointu**, wybierz logowanie i blokowanie, następnie **Zapisz i nadaj dostęp**.
7. Zaakceptuj uprawnienie dostępu do wskazanego serwera i odśwież karty dostawców AI.

Adres `http://localhost:8787` ma sens tylko, gdy Chrome i serwer są na tym samym komputerze. Do serwera w LXC z innego komputera użyj jego domeny HTTPS. Dane logowania do Cloudflare Tunnel nie są tokenem wtyczki.

Przy zapisie ustawień wtyczka paruje profil i pobiera politykę blokowania. Nie podawaj jej tokena administratora. Dla drugiego profilu, przeglądarki lub komputera utwórz drugi endpoint.

## Cloudflare Tunnel w Compose

W panelu Cloudflare utwórz zdalnie zarządzany Tunnel i wpisz `TUNNEL_TOKEN` do lokalnego `.env`. Publiczną domenę skieruj na usługę:

```text
http://observatory:8787
```

```bash
docker compose --profile tunnel up -d --build
docker compose logs --tail=50 cloudflared
```

Przy gotowym obrazie użyj `pull` i `up -d --no-build` z tym samym profilem. Kontener tunelu ma osobną przestrzeń sieciową: `localhost` nie wskazuje aplikacji. Tunel startuje po zdrowym kolektorze.

Domenę HTTPS wpisz we wtyczkach. Cloudflare Access z interaktywnym logowaniem lub service tokens nie jest zintegrowany z rozszerzeniem. Tunel zapewnia transport do Cloudflare, ale treść logowanych promptów przechodzi przez jego infrastrukturę.

## Python bez Dockera

```bash
export PROMPT_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
python3 -m server.app
```

Uruchamiaj z katalogu repozytorium. Zachowaj token, zamiast generować nowy przy każdym restarcie. Proces słucha na 127.0.0.1:8787.

Przykładowa jednostka systemd dla dedykowanego użytkownika `promptobs`:

```ini
[Unit]
Description=WalleeGuard prompt collector
After=network.target

[Service]
User=promptobs
WorkingDirectory=/opt/walleeguard
EnvironmentFile=/etc/walleeguard.env
ExecStart=/usr/bin/python3 -m server.app
Restart=on-failure
UMask=0077
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Dostosuj użytkownika i ścieżki. W pliku środowiskowym dostępnym tylko administratorowi ustaw PROMPT_TOKEN i PROMPT_DB=/opt/walleeguard/data/prompts.sqlite3. Katalog danych musi być zapisywalny przez usługę, np. z prawami 0700.

Cloudflared uruchomiony w tej samej przestrzeni sieciowej co proces Python może kierować do `http://127.0.0.1:8787`. Lokalna konfiguracja ingress wymaga także skonfigurowanego tunelu, jego poświadczeń i powiązania DNS:

```yaml
ingress:
  - hostname: prompts.example.com
    service: http://127.0.0.1:8787
  - service: http_status:404
```
