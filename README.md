<div align="center">

# 🚗 Technical Data Sheet

**Crawler assíncrono para coleta de fichas técnicas de veículos do mercado brasileiro**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![asyncio](https://img.shields.io/badge/asyncio-async%2Fawait-00b4d8?style=for-the-badge)](https://docs.python.org/3/library/asyncio.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

---

> [!WARNING]
> **🔧 REFACTOR EM ANDAMENTO**
>
> Este projeto está passando por uma reestruturação completa. A arquitetura atual (`src/scrapers/`, `src/runners/`) será substituída por uma nova abordagem mais modular e testável — baseada nos módulos `CarrosWeb/` e `Common/` que já estão sendo desenvolvidos. Partes do código atual podem estar instáveis ou incompletas.

---

## Sobre o Projeto

O **Technical Data Sheet** é um crawler assíncrono que percorre sites especializados em veículos do mercado brasileiro para coletar fichas técnicas completas: especificações de motor, transmissão, dimensões, desempenho, consumo e equipamentos de série/opcionais.

Os dados são persistidos em **MongoDB** e coletados através de um pipeline em duas fases, com suporte a proxy e contornar técnicas anti-scraping.

### Fontes de Dados

| Site | Status | Observações |
|------|--------|-------------|
| [fichacompleta.com.br](https://www.fichacompleta.com.br) | ✅ Funcional | Fonte principal, suporte a CAPTCHA via proxy |
| [carrosnaweb.com.br](https://www.carrosnaweb.com.br) | 🔧 Em desenvolvimento | Impersonação de browser + OCR para valores em imagem |

---

## Como Funciona

O pipeline é dividido em **duas fases independentes**, que podem ser executadas juntas ou separadamente:

```
┌────────────────────────────────────────────────────────────────┐
│                         FASE 1 — Catálogo                      │
│                                                                  │
│  Fabricantes → Modelos → Anos → Versões → Salva no MongoDB     │
│                                         (status: "todo")        │
└────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                       FASE 2 — Ficha Técnica                    │
│                                                                  │
│  Lê veículos "todo" do DB → Busca ficha técnica → Salva specs  │
│                              (status: "done")                   │
└────────────────────────────────────────────────────────────────┘
```

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
├── main.py                          # Ponto de entrada — CLI
│
├── src/
│   ├── cli/
│   │   └── parser.py                # Definição dos subcomandos CLI (argparse)
│   │
│   ├── runners/                     # Orquestradores por site
│   │   ├── fichacompleta.py         # Pipeline completo do fichacompleta
│   │   └── carronaweb.py            # Pipeline completo do carrosnaweb
│   │
│   ├── scrapers/                    # Scrapers por site e função
│   │   ├── fichacompleta/
│   │   │   ├── automakers.py
│   │   │   ├── models.py
│   │   │   ├── version_and_years.py
│   │   │   └── technical_sheet.py
│   │   └── carronaweb/
│   │       ├── automakers.py
│   │       ├── models.py
│   │       ├── years.py
│   │       ├── version_link_consultation.py
│   │       └── technical_sheet.py
│   │
│   ├── CarrosWeb/                   # 🔧 Nova arquitetura (refactor)
│   │   ├── CarrosWebCrawler.py      # Orquestrador completo
│   │   ├── CarrosWebParser.py       # Parser HTML com resolução de duplicatas
│   │   ├── CarrosWebRequestFactory.py # Fábrica de requisições HTTP
│   │   └── example.html             # HTML de exemplo da ficha técnica
│   │
│   ├── Common/                      # 🔧 Utilitários compartilhados (refactor)
│   │   ├── NetworkManager.py        # Gerenciador de sessões HTTP
│   │   └── utils.py                 # OCR para imagens anti-scraping
│   │
│   ├── commons/
│   │   └── DatabaseRepository.py    # Repositório MongoDB (motor)
│   │
│   ├── Model/
│   │   └── Response.py              # Dataclass de resposta HTTP
│   │
│   ├── logger/                      # Sistema de logs colorido
│   │   ├── logger.py
│   │   ├── formatter.py
│   │   ├── handlers.py
│   │   └── repository.py
│   │
│   └── utils/                       # Utilitários de proxy por site
│       ├── proxy.py
│       ├── carroweb/
│       └── fichacompleta/
│
└── requirements.txt
```

---

## Pré-requisitos

- Python **3.11+**
- MongoDB rodando localmente na porta `27017`
- Tesseract OCR instalado no sistema

```bash
# Fedora / RHEL
sudo dnf install tesseract

# Debian / Ubuntu
sudo apt install tesseract-ocr

# macOS
brew install tesseract
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
python main.py <comando> [opções]
```

### Subcomandos

| Comando | Descrição |
|---------|-----------|
| `site <nome>` | Executa o scraper de um site específico |
| `full` | Executa todos os scrapers em sequência |
| `maintenance` | Comandos de manutenção do banco de dados |

### Exemplos

```bash
# Coletar tudo do fichacompleta (fases 1 e 2)
python main.py site fichacompleta

# Só coletar o catálogo (fabricantes, modelos, versões) — Fase 1
python main.py site fichacompleta --phase 1

# Só buscar as fichas técnicas dos veículos já no banco — Fase 2
python main.py site carronaweb --phase 2

# Executar todos os scrapers
python main.py full

# Ver estatísticas do banco
python main.py maintenance --show-stats
```

### Fases (`--phase`)

| Fase | O que faz |
|------|-----------|
| `1` | Percorre fabricantes → modelos → anos → versões e salva no MongoDB com `status: "todo"` |
| `2` | Lê os veículos `"todo"` do banco e busca a ficha técnica completa para cada um |
| `3` | Executa as fases 1 e 2 em sequência *(padrão)* |

---

## Banco de Dados

O projeto usa MongoDB com duas collections principais:

### `vehicle`
Registro de cada versão de veículo encontrada no catálogo.

```json
{
  "_id": "ObjectId",
  "timestamp": "04-06-2026 14:32:00",
  "status": "todo | in_progress | done",
  "reference": "fichacompleta | carroweb",
  "automaker": "volkswagen",
  "model": "gol",
  "year": "2020",
  "version": "1.0 MPI Trendline"
}
```

### `vehicle_specs`
Ficha técnica completa de cada veículo.

```json
{
  "automaker": "volkswagen",
  "model": "gol",
  "version": "1.0 MPI Trendline",
  "year": "2020",
  "result": {
    "Motor": "1.0 MPI",
    "Potência": "82 cv",
    "Torque": "10,2 kgfm",
    "Câmbio": "Manual 5 marchas",
    "..."
  },
  "equipments": [
    "Ar-condicionado",
    "Direção elétrica",
    "..."
  ]
}
```

---

## Concorrência

O pipeline usa `asyncio.Semaphore(5)` para limitar o número de requisições simultâneas, evitando sobrecarga nos servidores e bloqueios por rate limiting.

```python
semaphore = asyncio.Semaphore(5)

async def process_model(automaker, model):
    async with semaphore:
        ...
```

---

## Logs

Os logs são coloridos por nível e referência, escritos tanto no terminal quanto em arquivo.

```
[14:32:01] INFO     fichacompleta | ✅ Technical sheet inserted for: /carros/vw/gol/...
[14:32:02] WARNING  carroweb      | ⚠️ CAPTCHA detected, retrying with proxy...
[14:32:05] ERROR    main          | ❌ Unexpected error: Connection timeout
```

---

## Roadmap do Refactor

- [x] `NetworkManager` — gerenciador de sessões unificado (aiohttp + curl_cffi)
- [x] `CarrosWebRequestFactory` — fábrica de requisições para o carrosnaweb
- [x] `CarrosWebParser` — parser completo com OCR e desambiguação de labels duplicados
- [x] `CarrosWebCrawler` — orquestrador com resolução de valores em imagem via OCR
- [ ] Migrar `scrapers/fichacompleta` para a nova arquitetura
- [ ] Migrar `runners/` para usar os novos Crawlers
- [ ] Testes unitários
- [ ] Docker + docker-compose

---

## Licença

Distribuído sob a licença [MIT](https://opensource.org/licenses/MIT).

---

<div align="center">
Feito por <a href="https://github.com/AndreNogueir4">André Nogueira</a>
</div>
