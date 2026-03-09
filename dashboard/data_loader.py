import os
import json
import glob
from datetime import datetime, date
import pandas as pd

def get_network_dir() -> str:
    dashboard_dir = os.path.dirname(__file__)
    DASH_CONFIG_FILE = os.path.join(dashboard_dir, "dashboard_config.json")
    if os.path.exists(DASH_CONFIG_FILE):
        try:
            with open(DASH_CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                if cfg.get("network_dir"):
                    return cfg["network_dir"]
        except Exception as e:
            print(f"Aviso: Erro ao ler dashboard_config.json: {e}")
            
    try:
        import sys
        parent = os.path.dirname(dashboard_dir)
        if parent not in sys.path:
            sys.path.append(parent)
        import configparser
        cfg_path = os.path.join(parent, "config.py")
        if os.path.exists(cfg_path):
            c = configparser.ConfigParser()
            c.read(cfg_path)
            nd = c['paths'].get('network_dir')
            if nd: return nd
    except Exception:
        pass
    return "C:\\Temp\\ProdMonData"

def load_all_data(network_dir: str) -> pd.DataFrame:
    """
    Lê todos os JSONs (diários e consolidados) do diretório de rede
    e retorna um DataFrame do Pandas unificado com os eventos 'summary' das sessões.
    """
    all_records = []
    
    # Busca arquivos normais diários de todas as pastas de usuários
    # Exemplo: network_dir/PC-JOAO/PC-JOAO_2025-01-15.json
    search_pattern_daily = os.path.join(network_dir, "*", "*.json")
    for file_path in glob.glob(search_pattern_daily):
        if "consolidado" in file_path.lower():
            continue # Trata separados depois
            
        try:
            # Fix #10: Ignora arquivos maiores que 50 MB (proteção contra JSONs maliciosos/corrompidos)
            MAX_JSON_BYTES = 50 * 1024 * 1024
            if os.path.getsize(file_path) > MAX_JSON_BYTES:
                print(f"Aviso: {file_path} excede 50 MB, ignorado.")
                continue
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            summary = data.get("summary", {})
            record = {
                "operator_name": data.get("operator_name", data.get("username", "Desconhecido")),
                "machine": data.get("machine", "Desconhecida"),
                "date": data.get("date"),
                "active_seconds": summary.get("active_seconds", 0),
                "idle_seconds": summary.get("idle_seconds", 0),
                "locked_seconds": summary.get("locked_seconds", 0),
                "session_start": summary.get("session_start"),
                "session_end": summary.get("session_end"),
                "source_file": file_path
            }
            all_records.append(record)
        except Exception as e:
            print(f"Erro lendo {file_path}: {e}")

    # Ler arquivos 'consolidados' (ex: consolidado_2026_01.json)
    search_pattern_cons = os.path.join(network_dir, "consolidado_*.json")
    for file_path in glob.glob(search_pattern_cons):
        try:
            # Fix #10: Ignora consolidados maiores que 50 MB
            MAX_JSON_BYTES = 50 * 1024 * 1024
            if os.path.getsize(file_path) > MAX_JSON_BYTES:
                print(f"Aviso: {file_path} excede 50 MB, ignorado.")
                continue
            with open(file_path, 'r', encoding='utf-8') as f:
                data_list = json.load(f)
                for item in data_list:
                    item['source_file'] = file_path
                    all_records.append(item)
        except Exception as e:
            print(f"Erro lendo consolidado {file_path}: {e}")

    if not all_records:
        return pd.DataFrame()
        
    df = pd.DataFrame(all_records)
    # Converter colunas para datetime e numeric
    df['date'] = pd.to_datetime(df['date']).dt.date
    df['session_start'] = pd.to_datetime(df['session_start'], format='ISO8601', errors='coerce')
    df['session_end'] = pd.to_datetime(df['session_end'], format='ISO8601', errors='coerce')
    
    # Tempo total medido no dia
    df['total_seconds'] = df['active_seconds'] + df['idle_seconds'] + df['locked_seconds']
    
    # Previne divisão por zero
    mask = df['total_seconds'] > 0
    df.loc[mask, 'active_pct'] = (df.loc[mask, 'active_seconds'] / df.loc[mask, 'total_seconds']) * 100
    df.loc[~mask, 'active_pct'] = 0.0
    
    # --- Cálculo de Jornada / Banco de Horas ---
    sched_file = os.path.join(network_dir, "schedules_config.json")
    just_file = os.path.join(network_dir, "justifications_config.json")
    
    schedules = {}
    justifications = {}
    
    if os.path.exists(sched_file):
        try:
            with open(sched_file, "r", encoding="utf-8") as sf:
                schedules = json.load(sf)
        except Exception as e:
            print(f"Aviso: Erro ao ler schedules_config.json: {e}")
            
    if os.path.exists(just_file):
        try:
            with open(just_file, "r", encoding="utf-8") as jf:
                justifications = json.load(jf)
        except Exception as e:
            print(f"Aviso: Erro ao ler justifications_config.json: {e}")
            
    # Aplica as regras de jornada se existirem
    def calc_balance(row):
        op = row['operator_name']
        dt_str = str(row['date'])
        
        cfg = schedules.get(op, None)
        
        # Puxa as justificativas daquele dia/user ("Atestado: 8.0h", etc)
        # Formato: {"Leonardo": {"2026-03-09": {"horas": 8.0, "motivo": "Atestado Medico"}}}
        just_info = justifications.get(op, {}).get(dt_str, {})
        bonus_h = float(just_info.get("horas", 0.0))
        just_reason = just_info.get("motivo", "")
        
        if not cfg:
            return pd.Series({
                "expected_h": 0.0, 
                "balance_h": 0.0 + bonus_h, 
                "expected_entry": None, 
                "expected_exit": None,
                "justification_h": bonus_h,
                "justification_reason": just_reason
            })
            
        try:
            from datetime import datetime as dt
            fmt = "%H:%M"
            t_in = dt.strptime(cfg["entry_time"], fmt)
            t_out = dt.strptime(cfg["exit_time"], fmt)
            
            # Calcula horas esperadas de trabalho: (Saida - Entrada) - Almoço - Lanche
            gross_minutes = (t_out.hour * 60 + t_out.minute) - (t_in.hour * 60 + t_in.minute)
            net_minutes = gross_minutes - int(cfg.get("lunch_minutes", 0)) - int(cfg.get("break_minutes", 0))
            expected_h = net_minutes / 60.0
            
            # Vamos usar o "Tempo Ativo + Ocioso Curto + Locked" para representar as Horas Trabalhadas da Empresa
            worked_h = row['total_seconds'] / 3600.0
            # Saldo final = (Horas Trabalhadas - Horas Exigidas) + Horas Justificadas/Atestado
            balance = (worked_h - expected_h) + bonus_h
            
            return pd.Series({
                "expected_h": expected_h, 
                "balance_h": balance,
                "expected_entry": cfg["entry_time"],
                "expected_exit": cfg["exit_time"],
                "justification_h": bonus_h,
                "justification_reason": just_reason
            })
        except Exception as e:
            return pd.Series({
                "expected_h": 0.0, 
                "balance_h": 0.0 + bonus_h, 
                "expected_entry": None, 
                "expected_exit": None,
                "justification_h": bonus_h,
                "justification_reason": just_reason
            })

    balance_cols = df.apply(calc_balance, axis=1)
    df = pd.concat([df, balance_cols], axis=1)
    
    return df

def get_user_events_for_timeline(network_dir: str, machine_name: str, target_date: str) -> pd.DataFrame:
    """
    Carrega o arquivo JSON exato e destrincha a lista "events"
    para montar um gráfico de Gantt da linha do tempo.
    target_date no formato YYYY-MM-DD
    """
    file_path = os.path.join(network_dir, machine_name, f"{machine_name}_{target_date}.json")
    if not os.path.exists(file_path):
        return pd.DataFrame()
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        events = data.get("events", [])
        timeline_records = []
        for ev in events:
            # Só interessam períodos contínuos para o Gantt
            if ev.get("type") in ["active", "idle", "locked"] and "start" in ev and "end" in ev:
                timeline_records.append({
                    "State": ev["type"].capitalize(),
                    "Start": pd.to_datetime(ev["start"]),
                    "Finish": pd.to_datetime(ev["end"]),
                    "Duration (s)": ev.get("duration_seconds", 0)
                })
                
        return pd.DataFrame(timeline_records)
    except Exception as e:
        print(f"Erro gerando timeline {file_path}: {e}")
        return pd.DataFrame()

def consolidate_logs(network_dir: str, year: int, month: int) -> tuple[int, int]:
    """
    Localiza todos os JSONs individuais de um mês específico,
    agrupa os conteúdos num único arquivo consolidado no diretório raiz,
    e exclui os arquivos originais.
    Retorna (qtde_arquivos_consolidados, total_registros)
    """
    # Fix #7: Bloqueia consolidação do mês atual para não corromper logs ativos
    today = date.today()
    if year == today.year and month == today.month:
        raise ValueError(f"Não é permitido consolidar o mês atual ({month:02d}/{year}). Aguarde o fechamento do mês.")
    prefix = f"{year:04d}-{month:02d}"
    
    files_to_consolidate = []
    # Exemplo: network_dir/PC-JOAO/PC-JOAO_2026-01-*.json
    search_pattern = os.path.join(network_dir, "*", f"*_{prefix}-*.json")
    
    for fpath in glob.glob(search_pattern):
        files_to_consolidate.append(fpath)
        
    if not files_to_consolidate:
        return 0, 0
        
    consolidated_records = []
    for fpath in files_to_consolidate:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extrair raw summary para o modelo consolidado
            summary = data.get("summary", {})
            record = {
                "operator_name": data.get("operator_name", data.get("username", "Desconhecido")),
                "machine": data.get("machine", "Desconhecida"),
                "date": data.get("date"),
                "active_seconds": summary.get("active_seconds", 0),
                "idle_seconds": summary.get("idle_seconds", 0),
                "locked_seconds": summary.get("locked_seconds", 0),
                "session_start": summary.get("session_start"),
                "session_end": summary.get("session_end"),
                # Guardar os eventos embutidos para caso precisem consultar a timeline no passado
                "events_raw": data.get("events", [])
            }
            consolidated_records.append(record)
        except Exception as e:
            print(f"Aviso: Fallhou ao ler {fpath} durante consolidacao: {e}")

    if not consolidated_records:
        return 0, 0
        
    # Append ou Criar novo arquivo consolidado
    cons_file_path = os.path.join(network_dir, f"consolidado_{year:04d}_{month:02d}.json")
    
    existing_records = []
    if os.path.exists(cons_file_path):
        try:
            with open(cons_file_path, 'r', encoding='utf-8') as f:
                existing_records = json.load(f)
        except:
            pass
            
    # Unir e gravar
    combined = existing_records + consolidated_records
    
    tmp_path = cons_file_path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, ensure_ascii=False)
        
    os.replace(tmp_path, cons_file_path)
    
    # Sucesso ao gravar, agora podemos apagar os originais
    deleted_count = 0
    for fpath in files_to_consolidate:
        try:
            os.remove(fpath)
            deleted_count += 1
        except:
            pass
            
    return deleted_count, len(consolidated_records)

def get_unconsolidated_past_months(network_dir: str) -> list[str]:
    """
    Procura JSONs individuais avulsos (não consolidados) nas pastas de máquinas
    que pertencem a meses já finalizados (menores que o mês atual no calendário).
    Retorna uma lista de strings no formato ['YYYY-MM', ...]
    """
    today = date.today()
    current_month_prefix = f"{today.year:04d}-{today.month:02d}"
    
    search_pattern = os.path.join(network_dir, "*", "*.json")
    unconsolidated_months = set()
    
    for fpath in glob.glob(search_pattern):
        if "consolidado" in fpath.lower():
            continue
            
        filename = os.path.basename(fpath)
        # Ex: PC-JOAO_2026-01-15.json
        parts = filename.replace('.json', '').split('_')
        if len(parts) >= 2:
            date_str = parts[-1] # Pega o último pedaço
            if len(date_str) == 10 and date_str.count('-') == 2:
                month_prefix = date_str[:7] # YYYY-MM
                if month_prefix < current_month_prefix:
                    unconsolidated_months.add(month_prefix)
                    
    return sorted(list(unconsolidated_months))
