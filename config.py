[user]
# Nome do operador desta máquina (preenchido durante a instalação)
# Usado para identificar a pessoa nos relatórios e logs de produtividade
operator_name = 

[install]
# true  = Este script irá inicializar com o windows automaticamente, registrando os eventos
# false = nao registra no startup; cria um launcher (start_prodmon.vbs) para iniciar manualmente
autostart = true

[paths]
# Diretório local onde os dados e logs são armazenados.
# (pasta oculta, transparente ao usuário)
local_dir = C:\ProgramData\ProdMon

# Caminho da pasta de rede para sincronização. Depois de scincronizado os logs locais serão apagados
# Exemplos:
#   \\SERVIDOR\TI\ProdMon
#   \\192.168.1.10\prodmon
#   Z:\ProdMon
network_dir = \\SERVIDOR\TI\ProdMon

[settings]
# Minutos de inatividade (sem mouse/teclado) para considerar ociosidade
# DEVE coincidir com o tempo de descanso de tela configurado no Windows (recomendado: 5)
idle_threshold_minutes = 5

# Intervalo de sincronização com a rede (em minutos) para envio dos logs locais para a Rede.
sync_interval_minutes = 60

# Frequência de verificação de atividade (em segundos)
# Valores menores = mais preciso, mais CPU. Recomendado: 10
check_interval_seconds = 10

[debug]
# true  = exibe janela de debug visual com cronômetro ao vivo (para testes). Por padrão é instalado true, mas mude para false ao instalar definicitivamente nas máquinas dos demais usuarios.
# false = agente roda silencioso sem janela (padrão de produção)
debug_mode = true
