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
│                        Pipeline por Site                          │
│                                                                  │
│  Montadoras → Modelos → Versões/Anos                             │
│       │            │          │                                  │
│       ▼            ▼          ▼                                  │
│  fichacompleta_automakers  fichacompleta_models                  │
│                             (referência + scraped_hrefs)         │
│                                    │                             │
│                    Novo href? ──────┤                             │
│                       Sim ▼        │ Não → skip                  │
│                   Busca ficha      │                             │
│                       │           │                             │
│                       ▼           │                             │
│                  vehicle_specs ◄───┘                             │
└──────────────────────────────────────────────────────────────────┘
```

Na primeira execução, tudo é baixado. Nas execuções seguintes, apenas versões/anos novos que ainda não estão em `scraped_hrefs` são coletados.

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

---

## Estrutura do Projeto

```
Technical-Data-Sheet/
│
├── src/
│   ├── __main__.py                      # Ponto de entrada — CLI
│   │
│   ├── CarrosWeb/                       # Scraper do carrosnaweb
│   │   ├── CarrosWebCrawler.py          # Orquestrador
│   │   ├── CarrosWebParser.py           # Parser HTML com OCR
│   │   └── CarrosWebRequestFactory.py  # Fábrica de requisições
│   │
│   ├── FichaCompleta/                   # Scraper do fichacompleta
│   │   ├── FichaCompletaCrawler.py      # Orquestrador com detecção incremental
│   │   ├── FichaCompletaParser.py       # Parser HTML
│   │   └── FichaCompletaRequestFactory.py
│   │
│   ├── Common/                          # Utilitários compartilhados
│   │   ├── DatabaseRepository.py        # Repositório MongoDB (motor)
│   │   ├── NetworkManager.py            # Gerenciador de sessões HTTP
│   │   └── utils.py                     # OCR para imagens anti-scraping
│   │
│   ├── Logger/                          # Sistema de logs
│   │   ├── Logger.py
│   │   ├── Formatter.py
│   │   ├── Handlers.py
│   │   └── Repository.py
│   │
│   └── Model/
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
python -m src <comando> [opções]
```

### Subcomandos

| Comando | Descrição |
|---------|-----------|
| `site <nome>` | Executa o scraper de um site específico |
| `full` | Executa todos os scrapers em paralelo |
| `run-forever` | Executa todos os scrapers em loop contínuo |

### Exemplos

```bash
# Coletar fichas do fichacompleta
python -m src site fichacompleta

# Coletar fichas do carrosnaweb
python -m src site carrosweb

# Executar todos os scrapers em paralelo
python -m src full

# Rodar em loop (intervalo padrão: 3600s)
python -m src run-forever

# Loop com intervalo customizado
python -m src run-forever --interval 1800
```

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

### `fichacompleta_models`
Controle de versões/anos por modelo, usado para detecção incremental.

```json
{
  "automaker": "volkswagen",
  "model": "gol",
  "reference": "https://www.fichacompleta.com.br/carros/volkswagen/gol/",
  "versions": {
    "2020 - 1.0 MPI Trendline": "/carros/volkswagen/gol/2020-1-0-mpi-trendline/"
  },
  "years": ["2020"],
  "scraped_hrefs": ["/carros/volkswagen/gol/2020-1-0-mpi-trendline/"],
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
- [x] CLI com subcomandos `site`, `full` e `run-forever`
- [ ] Testes unitários
- [ ] Docker + docker-compose

---

## Licença

Distribuído sob a licença [MIT](https://opensource.org/licenses/MIT).
