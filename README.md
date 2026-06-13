# WASDE Monitorr

Monitor automatizado do relatório mensal de oferta e demanda de grãos do USDA (WASDE — *World Agricultural Supply and Demand Estimates*).

No dia e horário de divulgação, o bot:
1. Baixa o PDF do relatório direto do servidor da USDA
2. Extrai os dados de produção e estoques via LLM (Groq)
3. Gera uma imagem de tabela no estilo dark com os principais números
4. Envia mensagem de texto + imagem + áudio via Telegram
5. Puxa as cotações de soja, milho e trigo do Yahoo Finance no momento da divulgação

---

## Estrutura do projeto

```
wasde_bot/
├── config.py              # Credenciais e constantes (editar antes de usar)
├── scheduler.py           # Daemon principal — monitora datas e dispara o pipeline
├── wasde_main.py          # Orquestrador do pipeline completo
├── wasde_fetcher.py       # Download e extração de texto do PDF do USDA
├── wasde_parser.py        # Extração estruturada de dados via Groq LLM
├── market_data.py         # Cotações de futuros via Yahoo Finance
├── image_generator.py     # Geração da tabela dark em PNG (Pillow)
├── audio_generator.py     # Síntese de voz via Groq TTS → OGG/Opus
├── message_formatter.py   # Montagem da mensagem Telegram em Markdown
├── telegram_sender.py     # Envio de texto, imagem e áudio via Telegram Bot API
├── requirements.txt       # Dependências Python
├── wasde-monitor.service  # Unit file para systemd
└── wasde_sent.json        # Gerado automaticamente — controle de envios
```

---

## Pré-requisitos

### Sistema
- Python 3.11+
- `ffmpeg` (conversão de áudio WAV → OGG Opus para Telegram)

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y ffmpeg python3-venv
```

### Credenciais necessárias

| Serviço | Como obter |
|---|---|
| **Telegram Bot Token** | [@BotFather](https://t.me/BotFather) no Telegram → `/newbot` |
| **Telegram Chat ID** | Envie `/start` para o bot, depois acesse `https://api.telegram.org/bot<TOKEN>/getUpdates` |
| **Groq API Key** | [console.groq.com](https://console.groq.com) → API Keys (free tier disponível) |

> ⚠️ **Importante:** o usuário do Telegram deve enviar `/start` para o bot antes do primeiro envio, caso contrário a API retorna `"chat not found"`.

---

## Instalação

### 1. Clonar / copiar os arquivos

```bash
# Exemplo com diretório no home do usuário
mkdir -p ~/wasde_bot
cp *.py requirements.txt wasde-monitor.service ~/wasde_bot/
cd ~/wasde_bot
```

### 2. Criar e ativar o ambiente virtual

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar credenciais

Edite `config.py` e preencha as variáveis:

```python
TELEGRAM_BOT_TOKEN = "123456789:AAF..."
TELEGRAM_CHAT_ID   = "-1001234567890"   # grupo ou chat individual
GROQ_API_KEY       = "gsk_..."
```

Ajuste também o `LOG_FILE` se quiser um caminho diferente para os logs:

```python
LOG_FILE = "/home/SEU_USUARIO/wasde_bot/wasde_monitor.log"
```

---

## Execução manual

Use para testar o pipeline completo antes de ativar o serviço.

### Pipeline de um relatório específico

```bash
# Ativa o venv (se ainda não estiver ativado)
source ~/wasde_bot/venv/bin/activate

# Sintaxe: python wasde_main.py <ANO> <MÊS>
python wasde_main.py 2026 6    # processa o relatório de junho/2026
python wasde_main.py 2026 7    # processa o relatório de julho/2026
```

O script irá:
- Baixar o PDF do USDA (com retry automático se ainda não disponível)
- Processar com LLM e gerar imagem + áudio
- Enviar tudo para o Telegram

### Testar apenas componentes individuais

```bash
# Testar conexão com Telegram
python3 -c "
from telegram_sender import send_message
send_message('✅ WASDE Monitor — teste de conexão')
"

# Verificar cotações de mercado
python3 -c "
from market_data import get_grain_prices
import json
print(json.dumps(get_grain_prices(), indent=2))
"

# Testar geração de imagem com dados mock
python3 -c "
from image_generator import generate_wasde_image
data = {
    'report_month': 'Teste 2026',
    'crop_years_shown': ['25/26', '26/27'],
    'soybeans': {'production': {'usa_prior': 120.7, 'usa_current': 121.0,
                                'brazil_prior': 186.0, 'brazil_current': 187.0,
                                'argentina_prior': 50.0, 'argentina_current': 50.0,
                                'world_prior': 441.5, 'world_current': 442.5},
                 'ending_stocks': {'usa_prior': 8.4, 'usa_current': 8.6,
                                   'world_prior': 124.8, 'world_current': 125.1}},
    'corn':     {'production': {'usa_prior': 406.3, 'usa_current': 406.3,
                                'brazil_prior': 139.0, 'brazil_current': 139.0,
                                'argentina_prior': 55.0, 'argentina_current': 55.0,
                                'world_prior': 1295.4, 'world_current': 1300.4},
                 'ending_stocks': {'usa_prior': 49.7, 'usa_current': 49.8,
                                   'world_prior': 277.5, 'world_current': 281.2}},
    'wheat':    {'production': {'usa_prior': None, 'usa_current': None,
                                'world_prior': None, 'world_current': None},
                 'ending_stocks': {'usa_prior': 20.7, 'usa_current': 20.2,
                                   'world_prior': 275.0, 'world_current': 275.4}},
}
ok = generate_wasde_image(data, '/tmp/wasde_test.png')
print('Imagem gerada:', ok)
"

# Testar TTS (gera arquivo de áudio)
python3 -c "
from audio_generator import text_to_speech
ok = text_to_speech('Teste de síntese de voz do WASDE Monitor.', '/tmp/wasde_test.ogg')
print('Áudio gerado:', ok)
"
```

### Verificar próximas datas de divulgação

```bash
python3 -c "
from config import RELEASE_DATES_2026
from datetime import date
today = date.today()
upcoming = [(y, m, d) for y, m, d in RELEASE_DATES_2026 if date(y, m, d) >= today]
print('Próximas divulgações:')
for y, m, d in upcoming[:5]:
    print(f'  {d:02d}/{m:02d}/{y}')
"
```

---

## Execução automatizada (systemd)

### 1. Editar o arquivo de serviço

Antes de instalar, ajuste os caminhos em `wasde-monitor.service`:

```ini
[Service]
User=SEU_USUARIO                                        # usuário do VPS
WorkingDirectory=/home/SEU_USUARIO/wasde_bot            # diretório do projeto
ExecStart=/home/SEU_USUARIO/wasde_bot/venv/bin/python \
          /home/SEU_USUARIO/wasde_bot/scheduler.py      # python do venv
```

### 2. Instalar e habilitar o serviço

```bash
# Copiar para o diretório do systemd
sudo cp ~/wasde_bot/wasde-monitor.service /etc/systemd/system/

# Recarregar configurações do systemd
sudo systemctl daemon-reload

# Habilitar (inicia automaticamente no boot)
sudo systemctl enable wasde-monitor

# Iniciar agora
sudo systemctl start wasde-monitor
```

### 3. Verificar status

```bash
# Status resumido
sudo systemctl status wasde-monitor

# Logs em tempo real
sudo journalctl -u wasde-monitor -f

# Últimas 50 linhas de log
sudo journalctl -u wasde-monitor -n 50

# Logs do arquivo (formato mais legível para debug)
tail -f ~/wasde_bot/wasde_monitor.log
```

### 4. Gerenciar o serviço

```bash
# Parar
sudo systemctl stop wasde-monitor

# Reiniciar (ex: após editar config.py)
sudo systemctl restart wasde-monitor

# Desabilitar (não inicia mais no boot)
sudo systemctl disable wasde-monitor
```

---

## Calendário de divulgação 2026

Todos os relatórios são divulgados às **12:00 PM ET** (horário de Nova York).
O bot inicia as tentativas de download exatamente neste horário, com retry automático
a cada 60 segundos por até 15 minutos caso o PDF ainda não esteja disponível.

| Mês | Data | Horário BRT (verão ET) | Horário BRT (inverno ET) |
|---|---|---|---|
| Janeiro | 12/01 | — | 14h00 |
| Fevereiro | 10/02 | — | 14h00 |
| Março | 10/03 | — / 13h00* | 14h00 / 13h00* |
| Abril | 09/04 | 13h00 | — |
| **Maio** | **12/05** | **13h00** | — |
| Junho | 11/06 | 13h00 | — |
| Julho | 10/07 | 13h00 | — |
| Agosto | 12/08 | 13h00 | — |
| Setembro | 11/09 | 13h00 | — |
| Outubro | 09/10 | 13h00 / 14h00* | — |
| Novembro | 10/11 | — | 14h00 |
| Dezembro | 10/12 | — | 14h00 |

> \* Março e outubro são meses de transição de horário de verão (EUA e Brasil não mudam no mesmo dia).
> O bot usa `zoneinfo` para calcular os fusos corretamente — o horário exibido na mensagem do Telegram sempre reflete o horário real de Brasília no momento do envio.

> ⚠️ **Relatório de maio:** é o relatório mais importante do ano, pois inclui as primeiras estimativas para o novo ano-safra. O formato do PDF pode ser diferente dos demais meses. O bot detecta esse caso e inclui um aviso na mensagem.

---

## Fluxo do pipeline

```
scheduler.py
    │  (verifica a cada 60s se é dia e hora de divulgação)
    ▼
wasde_main.py
    ├── wasde_fetcher.py   → baixa PDF do USDA, extrai texto (pdfplumber)
    ├── wasde_parser.py    → extrai dados estruturados via Groq LLM
    ├── market_data.py     → cotações de futuros (Yahoo Finance)
    ├── image_generator.py → tabela dark em PNG (Pillow)
    ├── audio_generator.py → síntese de voz OGG/Opus (Groq TTS + ffmpeg)
    └── telegram_sender.py → envia texto + imagem + áudio
```

---

## Controle de envios

O arquivo `wasde_sent.json` é criado automaticamente na primeira execução
e registra quais relatórios já foram enviados (formato `"YYYY-MM"`):

```json
["2026-01", "2026-02", "2026-03"]
```

Isso garante que o bot não envie o mesmo relatório duas vezes, mesmo que
o serviço seja reiniciado no dia da divulgação.

Para forçar o reenvio de um relatório já enviado:

```bash
# Editar o arquivo e remover a entrada correspondente
nano ~/wasde_bot/wasde_sent.json

# Ou reprocessar diretamente via wasde_main.py (não verifica wasde_sent.json)
python wasde_main.py 2026 6
```

---

## Dependências

| Biblioteca | Uso |
|---|---|
| `pdfplumber` | Extração de texto do PDF do USDA |
| `pillow` | Geração da imagem de tabela |
| `requests` | Download do PDF e chamadas à API do Telegram |
| `groq` | LLM para extração de dados + TTS para áudio |
| `yfinance` | Cotações de futuros de grãos |
| `pydub` | Manipulação de áudio (suporte ao ffmpeg) |
| `zoneinfo` | Conversão de fusos horários (stdlib Python 3.9+) |
| `ffmpeg` | Conversão WAV → OGG Opus (sistema) |

---

## Solução de problemas

**Bot não dispara no horário**
- Verificar se o serviço está rodando: `sudo systemctl status wasde-monitor`
- Verificar se o fuso do VPS não interfere: `timedatectl` (o bot usa UTC internamente, não depende do fuso do sistema)
- Checar o log: `tail -50 ~/wasde_bot/wasde_monitor.log`

**Erro `"chat not found"` no Telegram**
- O usuário (ou grupo) precisa ter enviado `/start` para o bot antes do primeiro envio

**PDF retorna 404 após 15 minutos**
- O USDA ocasionalmente atrasa a publicação. Nesse caso, execute manualmente após o PDF estar disponível: `python wasde_main.py <ANO> <MÊS>`

**Erro de importação do `schedule`**
- Este projeto não usa a biblioteca `schedule`. Se aparecer esse erro, o Python sendo executado não é o do venv. Use o caminho completo: `/home/SEU_USUARIO/wasde_bot/venv/bin/python scheduler.py`

**TTS falha com erro de modelo**
- O modelo `playai-tts` pode ter disponibilidade limitada no free tier do Groq. O código faz fallback automático para `canopylabs/orpheus-v1-english`. Se ambos falharem, a mensagem de texto e a imagem são enviadas normalmente — apenas o áudio é omitido.

**Cotações retornam `n/d`**
- Os tickers `ZS=F`, `ZC=F`, `ZW=F` do Yahoo Finance rotacionam para o próximo contrato próximo ao vencimento. Se pararem de funcionar, verificar os tickers atuais em [finance.yahoo.com](https://finance.yahoo.com) e atualizar `GRAIN_TICKERS` em `config.py`.
