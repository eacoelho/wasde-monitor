# WASDE Monitor

Bot que monitora a divulgação mensal do relatório WASDE (*World Agricultural Supply and Demand Estimates*) do USDA. No horário de divulgação, baixa o XML oficial, extrai os dados de produção e estoques de soja, milho e trigo, e envia uma mensagem de texto + imagem com tabelas comparativas para um canal do Telegram.

---

## Configuração inicial

### 1. Clonar e criar o ambiente virtual

```bash
git clone <repo-url> wasde-monitor
cd wasde-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Preencher as credenciais em `config.py`

```python
TELEGRAM_BOT_TOKEN = "123456789:AAF..."
TELEGRAM_CHAT_ID   = "-1001234567890"
```

> O usuário ou grupo deve ter enviado `/start` para o bot antes do primeiro envio.

### 3. Testar a conexão

```bash
python -c "from telegram_sender import send_message; send_message('✅ Teste WASDE Monitor')"
```

---

## Execução

### Manual (relatório específico)

```bash
source venv/bin/activate
python wasde_main.py 2026 6    # ano e mês do relatório
```

### Daemon automático

O `scheduler.py` roda continuamente e verifica a cada 60 segundos se é dia e hora de divulgação (12:00 PM ET). Quando detecta, executa o pipeline completo.

```bash
source venv/bin/activate
python scheduler.py
```

---

## Serviço systemd (Linux)

Edite `wasde-monitor.service` com os caminhos do servidor:

```ini
User=seu_usuario
WorkingDirectory=/home/seu_usuario/wasde-monitor
ExecStart=/home/seu_usuario/wasde-monitor/venv/bin/python /home/seu_usuario/wasde-monitor/scheduler.py
```

Depois instale e ative:

```bash
sudo cp wasde-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wasde-monitor
```

### Comandos de manutenção

```bash
sudo systemctl status wasde-monitor      # status
sudo systemctl restart wasde-monitor     # reiniciar após editar config.py
sudo journalctl -u wasde-monitor -f      # logs em tempo real
tail -f wasde_monitor.log                # logs do arquivo
```

---

## Forçar reenvio

O arquivo `wasde_sent.json` registra os relatórios já enviados. Para reprocessar um já enviado, execute `wasde_main.py` diretamente (ele ignora esse controle) ou remova a entrada do JSON:

```bash
python wasde_main.py 2026 6
```

---

## Estrutura

```
├── config.py              # Credenciais e datas de divulgação
├── scheduler.py           # Daemon — monitora e dispara o pipeline
├── wasde_main.py          # Orquestrador do pipeline
├── wasde_fetcher.py       # Download do XML do USDA
├── wasde_parser.py        # Extração de dados do XML
├── market_data.py         # Cotações via Yahoo Finance
├── image_generator.py     # Geração da tabela em PNG (Pillow)
├── message_formatter.py   # Mensagem Telegram em Markdown
├── telegram_sender.py     # Envio via Telegram Bot API
├── wasde-monitor.service  # Unit file para systemd
└── wasde_sent.json        # Gerado automaticamente — controle de envios
```
