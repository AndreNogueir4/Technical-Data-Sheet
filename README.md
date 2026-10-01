<div align="center">

# 🚗 Technical Data Sheet

**Crawler assíncrono para coleta de fichas técnicas de veículos do mercado brasileiro**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![asyncio](https://img.shields.io/badge/asyncio-async%2Fawait-00b4d8?style=for-the-badge)](https://docs.python.org/3/library/asyncio.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

---

## Sobre o Projeto

O **Technical Data Sheet** é um crawler assíncrono que percorre sites especializados em veículos do mercado brasileiro para coletar fichas técnicas completas: especificações de motor, transmissão, dimensões, desempenho, consumo e equipamentos de série/opcionais.

Os dados são persistidos em **MongoDB** com detecção de mudanças — o crawler só baixa versões que ainda não estão no banco, evitando re-scraping desnecessário.

### Fontes de Dados

| Site | Status | Observações |
|------|--------|-------------|
| [fichacompleta.com.br](https://www.fichacompleta.com.br) | ✅ Funcional | Suporte a CAPTCHA via proxy |
| [carrosnaweb.com.br](https://www.carrosnaweb.com.br) | 🔧 Em desenvolvimento | Impersonação de browser + OCR para valores em imagem e para o captcha |

---

## Como Funciona

```
┌──────────────────────────────────────────────────────────────────┐
│                        Pipeline por Site                         │
│                                                                  │
│  catalog:  Montadoras → Modelos → Versões/Anos                   │
│                                  │                               │
│                                  ▼                               │
│                            job (status: todo)                    │
│                          já existe? → skip                       │
│                                  │                               │
│  worker:   pool de N workers ────┤                               │
│                  │               │                               │
│                  ▼               ▼                               │
│            Busca ficha     status: in_progress                   │
│                  │                                               │
│                  ▼                                               │
│            vehicle_specs + status: done (ou error)               │
└──────────────────────────────────────────────────────────────────┘
```

Os dois estágios são independentes: o `catalog` enfileira o que falta e o `worker` drena a fila.
O pool de workers é um só para todos os sites — cada job carrega o seu `source` e o
`TechnicalSheet` entrega cada um ao crawler certo, respeitando o intervalo daquele site.

Na primeira execução, tudo é baixado. Nas execuções seguintes, apenas versões/anos que ainda não estão na collection `job` viram novos jobs.

### Anti-Scraping

| Técnica | Implementação |
|---------|---------------|
| Browser impersonation | `curl_cffi` com perfil Chrome124 |
| User-Agent rotativo | `fake-useragent` |
| Suporte a proxy | Pool de proxies armazenado no MongoDB |
| CAPTCHA detection | Fallback automático para proxy ao detectar CAPTCHA |
| CAPTCHA por imagem | **OCR** com `Common/CaptchaManager.py` (carrosnaweb) |
| Valores em imagem | **OCR** com `Common/CaptchaManager.py` (carrosnaweb) |

> O carrosnaweb renderiza alguns campos críticos (deslocamento, potência, peso, comprimento) como imagens para dificultar scraping. O `CaptchaManager` extrai esses valores via OCR — é o mesmo Tesseract que lê o captcha, com outro alfabeto.

> **O captcha, e por que ele está aqui.** Antes de servir a ficha, o carrosnaweb
> às vezes troca a página por uma imagem de quatro caracteres e um formulário. O
> `CaptchaManager` mostra o que esse tipo de verificação vale contra um scraper:
> a imagem tem fonte única, contraste alto e nenhum ruído, então binarizar,
> ampliar e rodar o Tesseract em algumas combinações de limiar e `--psm` já
> resolve — o manager fica com a leitura mais votada, envia e segue a navegação.
> O que realmente contém coleta automática é o que está nas outras linhas desta
> tabela — ritmo de requisição, sessão coerente, reputação de IP.
>
> `python sessao_ficha.py 23727 23734 23723` roda esse caminho no terminal: ele
> desenha o captcha, imprime as leituras do OCR e só pede que você digite se
> nenhuma delas passar.

---

## Stack

- **Python 3.11+** — async/await nativo com `asyncio`
- **aiohttp / curl_cffi** — requisições HTTP assíncronas e impersonação de browser
- **lxml** — parsing de HTML com XPath
- **motor** — driver assíncrono para MongoDB
- **pytesseract + Pillow** — OCR para valores em imagem
- **colorlog** — logs coloridos e estruturados
- **FastAPI + uvicorn** — a API que serve as fichas coletadas
- **dependency-injector** — composition root declarativo

---

## Estrutura do Projeto

```
Technical-Data-Sheet/
│
├── src/
│   ├── __main__.py                      # Ponto de entrada — CLI
│   │
│   ├── TechnicalSheetRunner/            # Camada de execução
│   │   ├── TechnicalSheet.py            # Runner: CLI, estágios e pool de workers
│   │   └── TechnicalSheetContainer.py   # Composition root (dependency-injector)
│   │
│   ├── Server/                          # Camada HTTP
│   │   └── TechnicalSheetApi/           # A API das fichas técnicas
│   │       ├── __main__.py              # Sobe o uvicorn
│   │       ├── TechnicalSheetApi.py     # App FastAPI + erros do domínio em HTTP
│   │       ├── TechnicalSheetRouter.py  # As rotas
│   │       ├── TechnicalSheetService.py # Banco primeiro, fonte quando pedem
│   │       ├── TechnicalSheetSchema.py  # Contrato de entrada e saída (Pydantic)
│   │       └── TechnicalSheetApiContainer.py
│   │
│   ├── CarrosWeb/                       # Scraper do carrosnaweb
│   │   ├── CarrosWebCrawler.py          # Orquestrador
│   │   ├── CarrosWebParser.py           # Parser HTML
│   │   ├── CarrosWebRequestFactory.py   # Requisições, proxy e captcha
│   │   └── CarrosWebContainer.py        # Peças do site, montadas por DI
│   │
│   ├── FichaCompleta/                   # Scraper do fichacompleta
│   │   ├── FichaCompletaCrawler.py      # Orquestrador
│   │   ├── FichaCompletaParser.py       # Parser HTML
│   │   ├── FichaCompletaRequestFactory.py
│   │   └── FichaCompletaContainer.py    # Peças do site, montadas por DI
│   │
│   ├── Common/                          # Infraestrutura compartilhada
│   │   ├── Crawler.py                   # Classe base de todo crawler + erros do domínio
│   │   ├── CaptchaManager.py            # OCR: captcha e valores em imagem
│   │   ├── DatabaseRepository.py        # Repositório MongoDB (motor)
│   │   ├── NetworkManager.py            # Gerenciador de sessões HTTP
│   │   ├── settings.py                  # Configuração (variáveis de ambiente)
│   │   └── utils.py                     # Retry, rate limit, parse de HTML, texto
│   │
│   └── Model/
│       ├── Job.py                       # Job: uma versão de veículo a coletar
│       ├── JobStatus.py                 # todo / in_progress / done / invalid / error
│       ├── SheetMode.py                 # Modos de execução (all / catalog / worker)
│       └── Response.py                  # Dataclass de resposta HTTP
│
├── tests/                               # Suíte sem rede e sem banco
│   ├── conftest.py                      # Dublês e páginas de exemplo
│   └── fixtures/                        # HTML com a estrutura das páginas reais
│
├── sessao_ficha.py                      # Demonstração do OCR do captcha no terminal
├── pytest.ini
├── requirements.txt
└── requirements-dev.txt
```

---

## Pré-requisitos

- Python **3.11+**
- MongoDB (local ou via Docker)
- Tesseract OCR instalado no sistema

```bash
# Fedora / RHEL
sudo dnf install tesseract

# Debian / Ubuntu
sudo apt install tesseract-ocr

# macOS
brew install tesseract
```

### MongoDB via Docker

```bash
docker run -d -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=admin \
  --name mongo mongo:latest
```

---

## Instalação

```bash
# Clone o repositório
git clone https://github.com/AndreNogueir4/Technical-Data-Sheet.git
cd Technical-Data-Sheet

# Crie e ative um ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Instale as dependências
pip install -r requirements.txt
```

---

## Como Usar

```bash
python -m src [-s SOURCE] [-m MODE]
```

| Argumento | Valores | Default | Descrição |
|-----------|---------|---------|-----------|
| `-s`, `--source` | `all`, `carrosweb`, `fichacompleta` | `all` | Qual fonte coletar |
| `-m`, `--mode` | `all`, `catalog`, `worker` | `all` | O `SheetMode` da execução |

Os modos (`src/Model/SheetMode.py`):

| Modo | O que faz |
|------|-----------|
| `all` | Catálogo + fichas, **termina** quando não sobra nada para coletar |
| `catalog` | Só descobre veículos e enfileira jobs |
| `worker` | Só drena a fila, e **fica de pé**: dorme `SLEEP_TIME` sempre que ela seca |

### Exemplos

```bash
# Tudo, até pegar todos os veículos dos dois sites
python -m src

# Só o fichacompleta, catálogo + fichas
python -m src -s fichacompleta

# Só o catálogo do carrosnaweb
python -m src -s carrosweb -m catalog

# Worker permanente: drena a fila dos dois sites até Ctrl+C
python -m src -m worker
```

### A API

```bash
python -m src.Server.TechnicalSheetApi
```

Sobe em `API_HOST:API_PORT` (default `127.0.0.1:8000`), com a documentação
interativa em `/docs`. Ela usa o mesmo composition root do crawler: o banco é o
mesmo, e o runner que a coleta ao vivo empresta é o mesmo que o `python -m src`
roda.

| Rota | O que faz |
|------|-----------|
| `GET /health` | Se o banco responde, quantas fichas ele tem e quais fontes existem |
| `GET /fichas` | Lista o que já foi coletado — filtra por `source`, `montadora`, `modelo`, `ano`, `versao`, pagina com `limit`/`offset` |
| `GET /fichas/{source}/{reference}` | Uma ficha. `?ao_vivo=true` manda buscar na fonte quando ela não está no banco |
| `POST /fichas/coleta` | Coleta uma lista de fichas na fonte, agora |

```bash
# o que já está no banco (rápido: só lê o Mongo)
curl 'http://127.0.0.1:8000/fichas?montadora=audi&versao=quattro&limit=5'

# uma ficha pela referência (a barra inicial é opcional)
curl 'http://127.0.0.1:8000/fichas/fichacompleta/carros/audi/100-2-8-v6-quattro-1993'

# coleta na fonte e guarda no banco
curl -X POST http://127.0.0.1:8000/fichas/coleta \
  -H 'content-type: application/json' \
  -d '{"fichas": [{"source": "fichacompleta", "reference": "/carros/audi/100-2-8-v6-quattro-1993"}]}'
```

> `GET /fichas` só lê o Mongo e responde em milissegundos. A coleta ao vivo passa
> pelo mesmo limitador de taxa do crawler — é segundos por ficha, de propósito —, e
> é por isso que ela é uma rota separada em vez do comportamento padrão. O que ela
> coleta é gravado no banco (`salvar: false` desliga), então o mesmo pedido na
> segunda vez sai pelo caminho rápido. Quando a fonte está bloqueando, a resposta é
> `503` com `Retry-After`, não um `500`.

### Quanto Tempo Leva

O crawler é lento de propósito. Quem dá o ritmo é o `RateLimiter`: uma requisição a
cada `1 ÷ REQUESTS_PER_SECOND` segundos, **compartilhada por todos os workers da
fonte**. Aumentar `WORKER_COUNT` não acelera a coleta — muda só quantos jobs ficam em
voo esperando a vez. Quem acelera (e derruba) é o `REQUESTS_PER_SECOND`.

```
tempo ≈ requisições ÷ REQUESTS_PER_SECOND
```

| Execução | Tempo | Resultado |
|----------|-------|-----------|
| `-s fichacompleta -m catalog` | **~1h28** | 120 montadoras, 1.318 modelos, **20.397 jobs** enfileirados |

> O tempo acima é de antes de o ritmo passar a ser só do limitador: na época o catálogo
> ainda dormia um intervalo aleatório por modelo, em cima da espera entre requisições.
> Hoje a conta é a da fórmula acima, e o catálogo do fichacompleta (~1.440 requisições a
> `0.3` req/s) sai perto de **1h20**. Reexecuções são bem mais rápidas: o catálogo só
> enfileira versão que ainda não está na collection `job`.

O `worker` é a parte cara: uma requisição por ficha — mais uma por valor que o
carrosnaweb desenha como imagem. Para os 20.397 jobs do fichacompleta, no padrão de
`0.3` req/s, dá algo em torno de **19 horas**. É trabalho para deixar rodando em
`-m worker`, não para esperar sentado — dá para parar com Ctrl+C e retomar depois, que
a fila continua de onde parou.

> **Não aperte o ritmo para “ir mais rápido” em produção.** Um `REQUESTS_PER_SECOND`
> alto derruba a coleta: o fichacompleta responde com captcha e o carrosnaweb com
> página de erro, e o crawler recua sozinho. Suba o valor só para testar o fluxo.

### Testes

```bash
pip install -r requirements-dev.txt
pytest
```

A suíte não toca a rede nem o MongoDB: os sites entram como dublê e as páginas como
HTML de exemplo em `tests/fixtures`, com a mesma estrutura das reais. Os testes de OCR
desenham o captcha na hora e são pulados se o sistema não tiver uma fonte TrueType.

### Variáveis de Ambiente

Todas saem de `src/Common/settings.py`.

| Variável | Default | Descrição |
|----------|---------|-----------|
| `MONGO_URI` | `mongodb://localhost:27017/` | Conexão com o MongoDB |
| `MONGO_DB` | `technical_sheet` | Nome do banco |
| `WORKER_COUNT` | `10` | Workers simultâneos no pool |
| `SLEEP_TIME` | `5` | Espera (s) com a fila vazia no modo `worker` |
| `BATCH_SIZE` | `10` | Jobs reservados por vez, por fonte |
| `CONCURRENT` | `30` | Requisições simultâneas por crawler |
| `TRY_LIMIT` | `4` | Tentativas antes de um job virar `error` |
| `MAX_FAILURES` | `5` | Falhas seguidas antes de recuar de uma fonte |
| `TIMEOUT` | `100` | Tempo (s) máximo de uma requisição |
| `TCP_LIMIT` | `90` | Conexões TCP simultâneas do pool do aiohttp |
| `REQUESTS_PER_SECOND` | `0.3` | Ritmo de cada fonte, somando todos os workers |
| `CFFI_IMPERSONATE` | `chrome124` | Perfil de browser do `curl_cffi` |
| `CAPTCHA_LENGTH` | `4` | Quantos caracteres a resposta do captcha tem |
| `CAPTCHA_ATTEMPTS` | `3` | Leituras do captcha antes de desistir da página |
| `API_HOST` | `127.0.0.1` | Endereço em que a API escuta |
| `API_PORT` | `8000` | Porta em que a API escuta |
| `API_PAGE_SIZE` | `20` | Fichas por página quando o pedido não traz `limit` |

---

## Banco de Dados

O projeto usa MongoDB com as seguintes collections:

### `fichacompleta_automakers`
Catálogo de montadoras e seus modelos encontrados no site.

```json
{
  "automaker": "volkswagen",
  "models": ["gol", "polo", "tiguan"],
  "updated_at": "2026-06-10T19:32:57"
}
```

### `job`
Fila de trabalho: um documento por versão de veículo.
É a collection que o modelo `Job` (`src/Model/Job.py`) representa — todo job entra como `todo`.

| `status` | Significado |
|----------|-------------|
| `todo` | Na fila, esperando um worker |
| `in_progress` | Reservado por um worker |
| `done` | Ficha coletada e salva em `vehicle_specs` |
| `invalid` | A página respondeu, mas não existe ficha: referência morta (404) ou página vazia. Não é repetido e o motivo fica no campo `reason` |
| `error` | Falhou `TRY_LIMIT` vezes — bloqueio, captcha, rede |

A diferença entre `invalid` e `error` é o que adianta repetir: `error` é problema nosso ou
do momento e volta para a fila até esgotar as tentativas; `invalid` é problema do dado e
morre na primeira tentativa, sem queimar requisição.

```json
{
  "timestamp": "21-09-2026 18:52:03",
  "status": "todo",
  "source": "fichacompleta",
  "reference": "/carros/volkswagen/gol/2020-1-0-mpi-trendline/",
  "automaker": "volkswagen",
  "model": "gol",
  "year": "2020",
  "version": "2020 1.0 MPI Trendline",
  "attempts": 0
}
```

### `fichacompleta_models`
Catálogo de versões/anos por modelo.

```json
{
  "automaker": "volkswagen",
  "model": "gol",
  "reference": "https://www.fichacompleta.com.br/carros/volkswagen/gol/",
  "versions": {
    "2020 - 1.0 MPI Trendline": "/carros/volkswagen/gol/2020-1-0-mpi-trendline/"
  },
  "years": ["2020"],
  "updated_at": "2026-06-10T19:32:57"
}
```

### `vehicle_specs`
Ficha técnica completa de cada versão de veículo.

```json
{
  "montadora": "volkswagen",
  "modelo": "gol",
  "versao": "2020 - 1.0 MPI Trendline",
  "ano": "2020",
  "Motor": "1.0 MPI",
  "Potência": "82 cv",
  "Torque": "10,2 kgfm",
  "Câmbio": "Manual 5 marchas",
  "equipamentos": ["Ar-condicionado", "Direção elétrica"]
}
```

---

## Logs

Os logs são coloridos por nível e referência, escritos tanto no terminal quanto em arquivo.

```
2026-06-10 19:32:57 [INFO]    Starting FichaCompleta crawler
2026-06-10 19:33:48 [INFO]    get_automakers - found 123 automakers
2026-06-10 19:33:49 [INFO]    volkswagen : gol | get_version_years - found 12 versions
2026-06-10 19:33:49 [INFO]    volkswagen : gol | nothing new, skipping
2026-06-10 19:33:51 [WARNING] get_version_years - unexpected status: 404
```

---

## Roadmap

- [x] `NetworkManager` — gerenciador de sessões unificado (aiohttp + curl_cffi)
- [x] `CarrosWebRequestFactory` — fábrica de requisições para o carrosnaweb
- [x] `CarrosWebParser` — parser completo com OCR e desambiguação de labels duplicados
- [x] `CarrosWebCrawler` — orquestrador com resolução de valores em imagem via OCR
- [x] `FichaCompletaCrawler` — migrado para nova arquitetura com detecção incremental
- [x] CLI unificada (`-s` source + `-m` mode)
- [x] Injeção de dependência via composition root (`TechnicalSheetContainer`)
- [x] Pool de workers compartilhado entre as fontes (`TechnicalSheet`)
- [x] API HTTP das fichas (`src/Server/TechnicalSheetApi`)
- [x] Testes unitários (`pytest`, sem rede e sem banco)
- [ ] Docker + docker-compose

---

## Licença

Distribuído sob a licença [MIT](https://opensource.org/licenses/MIT).
