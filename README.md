# ProdMon Agent v1.3
### Monitor de Produtividade Silencioso — Windows 10/11

---

> **Autor:** Leonardo Scherpl — Contador · [Minas Contabilidade](https://minascontabilidade.com.br)

---

## Visão Geral

O **ProdMon Agent** roda silenciosamente na máquina do colaborador e apura:

| Período    | Descrição |
|------------|-----------|
| `active`   | Mouse ou teclado utilizados |
| `idle`     | Sem atividade por ≥ N minutos (com backdating preciso) |
| `locked`   | Tela bloqueada (Win+L, screensaver, política) — capturado **em tempo real** |
| `boot`     | Início da sessão / login — marca a **hora de entrada** na jornada |
| `shutdown` | Encerramento / logoff — marca a **hora de saída** da jornada |
| `lock`     | Evento pontual de bloqueio de tela |
| `unlock`   | Evento pontual de desbloqueio de tela |

Os dados são salvos localmente em JSON e sincronizados de hora em hora com uma pasta de rede.
Se a rede estiver indisponível, os arquivos ficam salvos localmente e são enviados assim que a conexão for restaurada.
Após sync bem-sucedido, o arquivo local do dia anterior é apagado.

---

## Pré-requisitos

- Windows 10 ou 11 (64-bit)
- Python 3.8 ou superior — https://www.python.org/downloads/
  - **Importante:** marcar a opção *"Add Python to PATH"* durante a instalação
- Acesso à pasta de rede mapeada ou endereço UNC (ex: `\\servidor\TI\ProdMon`)

---

## Referência de Configurações (`config.py`)

O arquivo `config.py` é dividido em **dois escopos** de responsabilidade:

---

### 🏢 Configurações do Escritório Contábil
> Definidas **uma única vez** pelo administrador/TI antes de distribuir para as máquinas.
> Todas as máquinas devem receber o mesmo `config.py` base (exceto `local_dir` se necessário).

| Parâmetro | Seção | Padrão | Descrição |
|-----------|-------|--------|-----------|
| `operator_name` | `[user]` | *(preenchido no install)* | Nome do operador desta máquina — identifica a pessoa nos relatórios de produtividade |
| `network_dir` | `[paths]` | *(obrigatório)* | Caminho da pasta de rede onde os JSONs de todas as máquinas são centralizados. Ex: `\\SERVIDOR\TI\ProdMon` ou `Z:\ProdMon` |
| `sync_interval_minutes` | `[settings]` | `60` | De quantos em quantos minutos o agente sincroniza com a rede. Recomendado: 30–60 min |
| `idle_threshold_minutes` | `[settings]` | `5` | ⚠️ **Configurado automaticamente no Windows durante a instalação.** Veja seção abaixo. |
| `autostart` | `[install]` | `true` | `true` = agente sobe automaticamente no login. `false` = iniciar via launcher |

---

### ⏱️ Como funciona a detecção de ausência

O agente usa **três mecanismos complementares** para capturar com precisão quando o colaborador está ou não trabalhando:

#### Modo 1 — Bloqueio de tela (Win+L, screensaver com senha)
> Captura instantânea via evento do Windows (`WM_WTSSESSION_CHANGE`)

| Ação | O que acontece |
|------|----------------|
| Pressiona **Win+L** | Estado vira `BLOQUEADO` **imediatamente**, com timestamp exato |
| Digita a senha e volta | Estado vira `ATIVO` **imediatamente**, com timestamp exato |

✅ **Funciona para qualquer duração**: 2 minutos, 4 minutos, 1 hora — tudo capturado com precisão total, sem depender do `idle_threshold_minutes`.

---

#### Modo 2 — Ausência sem bloqueio de tela (saiu sem pressionar Win+L)
> Detecção por inatividade de mouse/teclado via `GetLastInputInfo`

O agente detecta que ninguém usou o mouse/teclado por `idle_threshold_minutes` e **retroage o início da ociosidade** até o momento do último input — então o erro máximo é de `check_interval_seconds` segundos.

> **⚠️ Regra de ouro:** `idle_threshold_minutes` deve ser igual ao tempo configurado em:
> **Configurações → Sistema → Energia e suspensão → Tela: desligar após X minutos**
> *(O `install.bat` configura isso automaticamente via `powercfg`)*

Isso garante que o monitor e o agente "concordem" sobre quando o usuário está ausente.

---

#### Modo 3 — Polling de sessão (fallback redundante)
> Detecção por verificação periódica do estado do desktop via `OpenInputDesktop`

Caso o `pywin32` não esteja disponível (e portanto o Modo 1 não funcione), o agente verifica a cada `check_interval_seconds` se a tela está bloqueada. Funciona automaticamente como redundância — sem necessidade de configuração.

**Exemplos práticos:**

| Monitor apaga em | `idle_threshold_minutes` | Comportamento |
|-----------------|--------------------------|---------------|
| 5 minutos | `5` | Ausências de 5+ min sem bloqueio são capturadas |
| 10 minutos | `10` | Padrão recomendado |
| 15 minutos | `15` | Mais tolerante a pausas curtas |

```ini
; ── Exemplo de config.py para o escritório ──────────────────────────────────
[user]
operator_name = João Silva        ; preenchido automaticamente durante a instalação

[install]
autostart = true              ; inicia automaticamente no login (recomendado)

[paths]
network_dir = \\SERVIDOR\TI\ProdMon   ; ← ALTERE para o caminho real da rede

[settings]
idle_threshold_minutes = 5    ; tempo de espera de tela — configurado automaticamente (powercfg)
sync_interval_minutes  = 60   ; sincronizar a cada hora
```

---

### 💻 Configurações por Máquina
> Ajustadas individualmente conforme o ambiente de cada estação de trabalho.
> Não sobrescreva uma máquina já instalada — o `install.bat` preserva o `config.py` existente.

| Parâmetro | Seção | Padrão | Quando ajustar |
|-----------|-------|--------|----------------|
| `local_dir` | `[paths]` | `C:\ProgramData\ProdMon` | Altere apenas se o disco C: não for o principal ou se houver política de TI restritiva |
| `check_interval_seconds` | `[settings]` | `10` | Frequência de verificação de atividade. Valores menores = mais preciso, mais CPU. Aumente para `30` em máquinas mais antigas ou lentas |
| `debug_mode` | `[debug]` | `false` | Mude para `true` temporariamente para abrir a janela de diagnóstico visual (cronômetro ao vivo). **Nunca deixar em `true` em produção** |

```ini
; ── Ajustes específicos por máquina ──────────────────────────────────────────
[paths]
local_dir = C:\ProgramData\ProdMon    ; pasta local (oculta) — geralmente não alterar

[settings]
check_interval_seconds = 10           ; 30 em máquinas lentas, 5 para máxima precisão

[debug]
debug_mode = false                    ; true apenas para diagnóstico temporário
```

---

### 📋 `config.py` completo comentado

```ini
[user]
# Nome do operador desta máquina (preenchido durante a instalação)
# Usado para identificar a pessoa nos relatórios e logs de produtividade
operator_name = 

[install]
# true  = registra no startup do Windows (HKLM\...\Run) — inicia no login
# false = não registra; cria start_prodmon.vbs para iniciar manualmente
autostart = true

[paths]
# Pasta local onde dados e logs são gravados (oculta ao usuário)
local_dir = C:\ProgramData\ProdMon

# Pasta de rede centralizada — OBRIGATÓRIO configurar antes de instalar
# Exemplos: \\SERVIDOR\TI\ProdMon  |  \\192.168.1.10\prodmon  |  Z:\ProdMon
network_dir = \\SERVIDOR\TI\ProdMon

[settings]
# Minutos sem mouse/teclado para marcar período como ocioso
# Configurado automaticamente no Windows durante a instalação (powercfg)
idle_threshold_minutes = 5

# Intervalo de sincronização com a pasta de rede (em minutos)
sync_interval_minutes = 60

# Frequência de verificação de atividade (em segundos)
# Menor = mais preciso, mais CPU | Maior = menos preciso, menos CPU
check_interval_seconds = 10

[debug]
# true  = exibe janela visual ao vivo com cronômetro (diagnóstico)
# false = agente totalmente silencioso (padrão de produção)
debug_mode = false
```


---

## Instalação (por máquina)

### 1. Copiar os arquivos para a máquina

Coloque em qualquer pasta temporária (ex: Área de Trabalho):
```
prodmon_agent.py
config.py
install.bat
uninstall.bat
requirements.txt
```

### 2. Editar o `config.py`

Defina o caminho da pasta de rede em `network_dir` e escolha o modo de `autostart`.
(O `operator_name` será preenchido durante a instalação.)

### 3. Executar o instalador como Administrador

Clique com botão direito em `install.bat` → **Executar como administrador**

O instalador irá:
- Copiar os arquivos para `C:\ProgramData\ProdMon` (pasta oculta)
- Perguntar o **nome do operador** da máquina
- Gravar o nome do operador no `config.py`
- Instalar `pywin32` via pip
- Restringir permissões do `config.py` (Admins escrevem, Users apenas leem — via `icacls`)
- Configurar automaticamente o **timeout de tela** do Windows (via `powercfg`)
- **Se `autostart = true`:** registrar o agente em `HKLM\...\Run\ProdMonAgent`
- **Se `autostart = false`:** criar o arquivo `start_prodmon.vbs` e um atalho na Área de Trabalho para iniciar manualmente
- Iniciar o agente imediatamente

### 4. Configurar o standby do monitor

Para que a ociosidade seja apurada corretamente, o `install.bat` **configura automaticamente** o timeout de tela do Windows para coincidir com `idle_threshold_minutes`.

> ⚠️ Se precisar alterar manualmente:
> Configurações → Sistema → Energia e suspensão → **Tela: X minutos**

---

## Modos de Inicialização

### `autostart = true` (padrão — recomendado para produção)

O agente é registrado no startup do Windows. Inicia automaticamente a cada login, sem qualquer interação do usuário.

### `autostart = false` (início manual)

Nenhuma entrada é criada no registro. O instalador cria dois arquivos de atalho:

| Arquivo | Local |
|---------|-------|
| `start_prodmon.vbs` | `C:\ProgramData\ProdMon\` |
| `Iniciar ProdMon.vbs` | Área de Trabalho pública |

Basta **clicar duas vezes** em qualquer um deles para iniciar o agente silenciosamente (sem abrir terminal ou janela).

---

## Debug Visual (cronômetro ao vivo)

Para verificar se o agente está funcionando corretamente, ative o modo debug no `config.py`:

```ini
[debug]
debug_mode = true
```

Uma pequena janela aparece no **canto inferior direito** da tela, sempre visível:

```
┌──────────────────────────────┐
│  ● ProdMon Debug             │
│  ● ATIVO                     │  ← verde (ativo) ou amarelo (ocioso)
│        00:12:47              │  ← cronômetro do estado atual
│  Ativo  01:23:10  Ocioso 00:08:30 │
└──────────────────────────────┘
```

- **Cronômetro** conta o tempo no estado atual e reseta a cada transição
- **Totais** mostram o acumulado do dia incluindo o período em andamento
- Usa **tkinter** (nativo do Python — sem dependências extras)
- Para produção: `debug_mode = false` (sem janela)

---

## Estrutura de Arquivos

```
C:\ProgramData\ProdMon\          ← pasta oculta (+h +s)
├── prodmon_agent.py
├── config.py                    ← leitura por Users, escrita só por Admins
├── prodmon.pid                  ← PID do processo (usado pelo uninstall)
├── start_prodmon.vbs            ← launcher manual (se autostart = false)
├── data\
│   ├── HOSTNAME_2025-01-15.json ← arquivo do dia atual
│   └── HOSTNAME_2025-01-14.json ← pendente de sync (se houver)
└── logs\
    ├── prodmon.log
    ├── prodmon.log.1            ← backups de rotação automática (até 3 × 5 MB)
    └── prodmon.log.2
```

**Pasta de rede:**
```
\\SERVIDOR\TI\ProdMon\
└── NOME-DA-MAQUINA\
    ├── NOME-DA-MAQUINA_2025-01-15.json
    ├── NOME-DA-MAQUINA_2025-01-14.json
    └── ...
```

---

## Formato do JSON gerado

```json
{
  "machine":       "PC-JOAO",
  "operator_name": "João Silva",
  "username":      "joao.silva",
  "date":          "2025-01-15",
  "version":       "1.3",
  "events": [
    { "type": "boot",     "timestamp": "2025-01-15T08:00:12" },
    { "type": "active",  "start": "2025-01-15T08:00:15", "end": "2025-01-15T12:00:00", "duration_seconds": 14385 },
    { "type": "lock",    "timestamp": "2025-01-15T12:00:00" },
    { "type": "locked",  "start": "2025-01-15T12:00:00", "end": "2025-01-15T13:05:00", "duration_seconds": 3900 },
    { "type": "unlock",  "timestamp": "2025-01-15T13:05:00" },
    { "type": "active",  "start": "2025-01-15T13:05:00", "end": "2025-01-15T17:30:00", "duration_seconds": 15900 },
    { "type": "idle",    "start": "2025-01-15T17:30:00", "end": "2025-01-15T17:55:00", "duration_seconds": 1500 },
    { "type": "shutdown","timestamp": "2025-01-15T17:55:04" }
  ],
  "summary": {
    "active_seconds":  30285,
    "idle_seconds":    1500,
    "locked_seconds":  3900,
    "session_start":   "2025-01-15T08:00:12",
    "session_end":     "2025-01-15T17:55:04"
  }
}
```

> **Leitura da jornada:**
> - `session_start` → horário de entrada (boot/login)
> - `session_end` → horário de saída (shutdown/logoff)
> - Períodos `locked` = almoço, reuniões, etc. (ajuste de intervalo fica para o dashboard)
> - Períodos `idle` < threshold = pequenas ausências sem bloqueio

### Como calcular horas trabalhadas no servidor:

```python
import json, pathlib

data = json.loads(pathlib.Path("PC-JOAO_2025-01-15.json").read_text())
s = data["summary"]

print(f"Operador       : {data['operator_name']}")
print(f"Máquina        : {data['machine']} ({data['username']})")
print(f"Entrada        : {s['session_start'][11:16]}")
print(f"Saída          : {s['session_end'][11:16]}" if s['session_end'] else "Em andamento")
print(f"Horas ativas   : {s['active_seconds'] / 3600:.2f}h")
print(f"Horas ociosas  : {s['idle_seconds']   / 3600:.2f}h")
print(f"Horas bloqueado: {s['locked_seconds'] / 3600:.2f}h")
```

---

## Comportamento de Sincronização

| Situação | Comportamento |
|----------|---------------|
| Rede disponível (a cada hora) | Copia JSON para rede, apaga local (exceto o do dia atual) |
| Rede indisponível | Mantém arquivo local, tenta novamente na próxima hora |
| Desligamento com rede OK | Sync final antes de encerrar |
| Desligamento sem rede | Arquivo fica local; no próximo boot envia automaticamente |
| Virada de meia-noite | Fecha o dia anterior, sincroniza, inicia novo arquivo |

---

## Desinstalação

Execute `uninstall.bat` como Administrador.
Ele irá:
- Encerrar o processo pelo PID salvo (ou buscar especificamente o `prodmon_agent` via `wmic`)
- Remover a entrada do startup (`HKLM\...\Run\ProdMonAgent`)
- Perguntar se deseja apagar todos os dados locais

---

## Segurança e Privacidade

- O agente **não captura conteúdo** digitado (teclas, textos) — apenas detecta se houve atividade ou não
- O agente **não captura screenshots**
- Os dados são armazenados apenas localmente e na pasta de rede configurada
- O `config.py` tem ACL restritiva: Admins e SYSTEM têm controle total, usuários comuns apenas leitura
- O nome do operador é **sanitizado** durante a instalação (caracteres perigosos removidos)
- Os dados JSON são gravados de forma **atômica** (via arquivo temporário + `os.replace`) para evitar corrupção por queda de energia
- Proteção contra **múltiplas instâncias**: o agente verifica o PID existente e não inicia se outro já estiver rodando
- O `uninstall.bat` encerra apenas o processo ProdMon (busca específica via `wmic`), sem afetar outros scripts Python

---

## Solução de Problemas

**Agente não iniciou após instalação:**
```
Verifique: C:\ProgramData\ProdMon\logs\prodmon.log
```

**Arquivos não sincronizam:**
- Verifique se a pasta de rede está acessível: `net use \\SERVIDOR\TI\ProdMon`
- Verifique permissões de escrita na pasta de rede

**Ver agente em execução:**
```
type C:\ProgramData\ProdMon\prodmon.pid
tasklist | findstr pythonw
```

**Parar agente manualmente:**
```
type C:\ProgramData\ProdMon\prodmon.pid
taskkill /pid <PID> /f
```

**Testar o debug visual:**
1. Edite `config.py` e defina `debug_mode = true`
2. Execute: `python C:\ProgramData\ProdMon\prodmon_agent.py`
3. A janela de debug aparecerá no canto inferior direito

---

## Roadmap Futuro

- [ ] Script de relatório consolidado (lê todos os JSONs da rede)
- [ ] Dashboard web simples (HTML/Python)
- [ ] Alerta por e-mail se máquina não sincronizar em X horas
- [ ] Suporte a múltiplos usuários na mesma máquina

---

## Histórico de Versões

| Versão | Data | Mudanças |
|--------|------|----------|
| 1.3 | Mar/2026 | Auditoria de segurança: escrita atômica do JSON; proteção contra múltiplas instâncias; sanitização do input de operador; ACL corrigida (`Users:R`); sync always-copy (sem comparação falha por tamanho); detecção de lock por polling como fallback; `uninstall.bat` corrigido (`REG_NAME`, `EnableDelayedExpansion`, kill seletivo via `wmic`); thread-safety no overlay de debug |
| 1.2 | Mar/2026 | Detecção de lock/unlock de sessão em tempo real (`WM_WTSSESSION_CHANGE`); campo `operator_name` e `username` no JSON; timeout de tela automático (`powercfg`); renomear config para `.py`; campos `session_start`, `session_end`, `locked_seconds` no summary; estado `locked` na overlay de debug (azul); retrocompatibilidade com arquivos v1.1 |
| 1.1 | Mar/2026 | `GetTickCount64`; `RotatingFileHandler`; thread-safety; ACL no config.py; Debug Overlay tkinter; flag `autostart`; launcher VBS |
| 1.0 | —       | Versão inicial |

---

*Desenvolvido por **Leonardo Scherpl** · Contador · Minas Contabilidade*
