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
| [carrosnaweb.com.br](https://www.carrosnaweb.com.br) | 🔧 Em desenvolvimento | Impersonação de browser + OCR para valores em imagem |

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
| Valores em imagem | **OCR** com `pytesseract` + `Pillow` (carrosnaweb) |

> O carrosnaweb renderiza alguns campos críticos (deslocamento, potência, peso, comprimento) como imagens para dificultar scraping. O módulo `Common/utils.py` extrai esses valores via OCR.

---

## Stack

- **Python 3.11+** — async/await nativo com `asyncio`
- **aiohttp / curl_cffi** — requisições HTTP assíncronas e impersonação de browser
- **lxml** — parsing de HTML com XPath
- **motor** — driver assíncrono para MongoDB
- **pytesseract + Pillow** — OCR para valores em imagem
- **colorlog** — logs coloridos e estruturados
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
│   ├── CarrosWeb/                       # Scraper do carrosnaweb
│   │   ├── CarrosWebCrawler.py          # Orquestrador
│   │   ├── CarrosWebParser.py           # Parser HTML com OCR
│   │   ├── CarrosWebRequestFactory.py   # Fábrica de requisições
│   │   └── CarrosWebContainer.py        # Peças do site, montadas por DI
│   │
│   ├── FichaCompleta/                   # Scraper do fichacompleta
│   │   ├── FichaCompletaCrawler.py      # Orquestrador
│   │   ├── FichaCompletaParser.py       # Parser HTML
│   │   ├── FichaCompletaRequestFactory.py
│   │   └── FichaCompletaContainer.py    # Peças do site, montadas por DI
│   │
│   ├── Common/                          # Infraestrutura compartilhada
│   │   ├── crawler.py                   # Classe base de todo crawler de site
│   │   ├── logger.py                    # LoggerFactory + handler MongoDB
│   │   ├── settings.py                  # Configuração (variáveis de ambiente)
│   │   ├── DatabaseRepository.py        # Repositório MongoDB (motor)
│   │   ├── NetworkManager.py            # Gerenciador de sessões HTTP
│   │   ├── exceptions.py                # Erros do domínio
│   │   └── utils.py                     # OCR + normalização de texto
│   │
│   └── Model/
│       ├── Job.py                       # Job: uma versão de veículo a coletar
│       ├── SheetMode.py                 # Modos de execução (all / catalog / worker)
│       └── Response.py                  # Dataclass de resposta HTTP
│
└── requirements.txt
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

### Quanto Tempo Leva

O crawler é lento de propósito: entre uma requisição e outra ele espera um intervalo
aleatório, senão o site bloqueia. Sirva-se destes números como referência.

| Execução | Tempo | Resultado |
|----------|-------|-----------|
| `-s fichacompleta -m catalog` | **~1h28** | 120 montadoras, 1.318 modelos, **20.397 jobs** enfileirados |

> Medido com os valores padrão (`MIN_DELAY=10`, `MAX_DELAY=50`), em uma execução do zero
> com o banco vazio. Reexecuções são bem mais rápidas: o catálogo só enfileira versão
> que ainda não está na collection `job`.

O `worker` é a parte cara. Cada ficha custa uma requisição mais o intervalo entre jobs,
divididos por `WORKER_COUNT` workers em paralelo — então a conta aproximada é:

```
tempo ≈ jobs × média(MIN_DELAY, MAX_DELAY) ÷ WORKER_COUNT
```

Para os 20.397 jobs do fichacompleta, no padrão (30s de média, 10 workers), dá algo em
torno de **17 horas**. É trabalho para deixar rodando em `-m worker`, não para esperar
sentado — dá para parar com Ctrl+C e retomar depois, que a fila continua de onde parou.

> **Não aperte os intervalos para “ir mais rápido” em produção.** `MIN_DELAY`/`MAX_DELAY`
> baixos derrubam a coleta: o fichacompleta responde com captcha e o carrosnaweb com
> página de erro, e o crawler recua sozinho. Use valores curtos só para testar o fluxo.

### Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `MONGO_URI` | `mongodb://localhost:27017/` | Conexão com o MongoDB |
| `MONGO_DB` | `technical_sheet` | Nome do banco |
| `WORKER_COUNT` | `10` | Workers simultâneos no pool |
| `SLEEP_TIME` | `5` | Espera (s) com a fila vazia no modo `worker` |
| `BATCH_SIZE` | `4` | Jobs reservados por vez, por fonte |
| `CONCURRENCY` | `2` | Requisições simultâneas do `get_list_result` |
| `MAX_ATTEMPTS` | `3` | Tentativas antes de um job virar `error` |
| `MAX_FAILURES` | `5` | Falhas seguidas antes de recuar de uma fonte |
| `MIN_DELAY` / `MAX_DELAY` | `10` / `50` | Intervalo aleatório (s) entre dois jobs |
| `CFFI_IMPERSONATE` | `chrome124` | Perfil de browser do `curl_cffi` |

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
| `error` | Falhou `MAX_ATTEMPTS` vezes seguidas — bloqueio, captcha, rede |

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
- [ ] Testes unitários
- [ ] Docker + docker-compose

---

## Licença

Distribuído sob a licença [MIT](https://opensource.org/licenses/MIT).
