import streamlit as st
import pandas as pd
import os
import json
import datetime
import data_loader

st.set_page_config(page_title="Administração", page_icon="⚙️", layout="wide")
st.title("⚙️ Administração & Base de Dados")

net_dir = data_loader.get_network_dir()

# Painel de Controle
st.markdown("### Ferramenta de Otimização Mensal (Lote)")
st.warning(
    "Aviso: Com o tempo, a pasta de rede acumula milhares de arquivos `.json` "
    "(1 por máquina, por dia). Isso pode deixar o Dashboard lento. "
    "Utilize a ferramenta de consolidação mensal abaixo para juntar os arquivos "
    "de meses anteriores em um único arquivo de alta performance."
)

c1, c2 = st.columns(2)
with c1:
    year = st.number_input("Ano da Consolidação", value=2026, min_value=2025, max_value=2099)
with c2:
    month = st.selectbox("Mês da Consolidação", options=range(1, 13), format_func=lambda x: f"{x:02d}")

if st.button("Executar Consolidação", type="primary"):
    with st.spinner(f"Agrupando arquivos de {year:04d}-{month:02d}..."):
        qtde_deletados, total_registros = data_loader.consolidate_logs(net_dir, year, month)
        
        if qtde_deletados > 0:
            st.success(f"**Sucesso!** {qtde_deletados} arquivos diários foram unificados num único arquivo consolidado.")
            st.info(f"O arquivo consolidado contém agora {total_registros} registros de sessões, preservando todo o histórico e reduzindo a carga do disco de rede.")
            st.cache_resource.clear()
            st.cache_data.clear()
        else:
            st.info("Nenhum arquivo individual encontrado para esse mês/ano que já não estivesse consolidado.")

st.markdown("---")
st.markdown("### 👥 Gestão de Jornada dos Colaboradores")
st.write("Defina o horário padrão de cada operador para o cálculo automático de horas extras (excesso) e horas devidas (ausência).")

# Função para carregar/salvar as configurações de jornada no diretório de rede
SCHEDULE_FILE = os.path.join(net_dir, "schedules_config.json")

def load_schedules():
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_schedules(sched):
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(sched, f, ensure_ascii=False, indent=2)

schedules = load_schedules()

with st.spinner("Buscando lista de colaboradores..."):
    df = data_loader.load_all_data(net_dir)
    
if not df.empty:
    operadores = sorted(df['operator_name'].unique())
    selected_op = st.selectbox("Selecione o Operador para configurar:", operadores)
    
    # Carrega config existente ou valores padrão
    op_cfg = schedules.get(selected_op, {
        "entry_time": "08:00",
        "exit_time": "18:00",
        "lunch_minutes": 60,
        "break_minutes": 15
    })
    
    with st.form("form_jornada"):
        c1, c2, c3, c4 = st.columns(4)
        
        # Converter string HH:MM para objeto time para o input do streamlit
        try:
            def_entry = datetime.datetime.strptime(op_cfg["entry_time"], "%H:%M").time()
            def_exit = datetime.datetime.strptime(op_cfg["exit_time"], "%H:%M").time()
        except:
            def_entry = datetime.time(8, 0)
            def_exit = datetime.time(18, 0)
            
        inp_entry = c1.time_input("Hora de Chegada Prevista", value=def_entry)
        inp_exit = c2.time_input("Hora de Saída Prevista", value=def_exit)
        inp_lunch = c3.number_input("Intervalo de Almoço (min)", value=int(op_cfg.get("lunch_minutes", 60)), min_value=0, max_value=240, step=15)
        inp_break = c4.number_input("Outros Lanches/Pausas (min)", value=int(op_cfg.get("break_minutes", 15)), min_value=0, max_value=120, step=5)
        
        submitted = st.form_submit_button("Salvar Jornada")
        if submitted:
            schedules[selected_op] = {
                "entry_time": inp_entry.strftime("%H:%M"),
                "exit_time": inp_exit.strftime("%H:%M"),
                "lunch_minutes": inp_lunch,
                "break_minutes": inp_break
            }
            save_schedules(schedules)
            st.success(f"Jornada salva para {selected_op}!")
            st.cache_data.clear() # Limpa cache para o dataframe global recalcular as faltas
else:
    st.info("Nenhum operador encontrado na base de dados para configurar jornada.")

st.markdown("---")
st.markdown("### Limpar Cache da Aplicação")
if st.button("Limpar Cache de Dados Atuais"):
    st.cache_resource.clear()
    st.cache_data.clear()
    st.success("Cache limpo! Os dados serão lidos do disco na próxima atualização.")
