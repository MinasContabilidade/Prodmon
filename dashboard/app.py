import streamlit as st
import pandas as pd
import data_loader
import os
import json

st.set_page_config(
    page_title="ProdMon | BI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 ProdMon - Visão Geral")
st.markdown("Bem-vindo ao painel de produtividade da equipe.")

# Gerenciamento de Configuração Persistente do Dashboard
DASH_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "dashboard_config.json")

def load_dash_config():
    if os.path.exists(DASH_CONFIG_FILE):
        try:
            with open(DASH_CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_dash_config(cfg):
    with open(DASH_CONFIG_FILE, "w") as f:
        json.dump(cfg, f)

dash_cfg = load_dash_config()
saved_path = dash_cfg.get("network_dir", "")

if not saved_path:
    saved_path = data_loader.get_network_dir()

# --- Sidebar: Configurações de Dados ---
st.sidebar.header("⚙️ Configurações Base")

with st.sidebar.expander("Pasta de Logs", expanded=(not os.path.exists(str(saved_path)))):
    new_dir = st.text_input("Caminho da Rede:", value=saved_path)
    if st.button("Salvar Caminho"):
        dash_cfg["network_dir"] = new_dir
        save_dash_config(dash_cfg)
        st.success("Salvo!")
        st.rerun()

net_dir = dash_cfg.get("network_dir", saved_path)

if st.sidebar.button("🔄 Recarregar Arquivos"):
    st.cache_resource.clear()
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")

if not net_dir or str(net_dir).strip() == "":
    st.error("⚠️ Caminho da rede não configurado. Use a barra lateral para definir.")
    st.stop()

if not os.path.exists(net_dir):
    st.warning(f"⚠️ A pasta de rede {net_dir} não está acessível ou não existe.")
    st.stop()

@st.cache_data(ttl=300) # Mantém em cache por 5 minutos
def load_data_cached(path):
    return data_loader.load_all_data(path)

# Load data
with st.spinner("Lendo arquivos JSON da rede..."):
    df = load_data_cached(net_dir)

if df.empty:
    st.info("Nenhum dado encontrado na rede ainda. O agente já foi instalado nas máquinas?")
    st.stop()

# Sidebar Filters
st.sidebar.header("Filtros Globais")

import datetime
today = datetime.date.today()
start_of_year = datetime.date(today.year, 1, 1)

col1, col2 = st.sidebar.columns(2)
start_dt = col1.date_input("Data Inicial", value=start_of_year, format="DD/MM/YYYY")
end_dt = col2.date_input("Data Final", value=today, format="DD/MM/YYYY")

if start_dt > end_dt:
    st.sidebar.error("A Data Inicial não pode ser maior que a Data Final.")
    st.stop()

mask = (df['date'] >= start_dt) & (df['date'] <= end_dt)
df_filtered = df.loc[mask]

st.markdown("---")

# --- Alerta Inteligente de Meses Não Consolidados ---
unconsolidated_months = data_loader.get_unconsolidated_past_months(net_dir)
if unconsolidated_months:
    st.info(f"💡 **Dica de Performance:** Há {len(unconsolidated_months)} mês(es) finalizado(s) (ex {unconsolidated_months[-1]}) com arquivos diários avulsos na rede. Vá na aba **Administração** e clique em **Consolidar** para agilizar o dashboard!", icon="⚡")

if df_filtered.empty:
    st.warning("Nenhum registro para o período selecionado.")
    st.stop()

# KPIs
col1, col2, col3, col4 = st.columns(4)
total_active = df_filtered['active_seconds'].sum() / 3600
total_idle = df_filtered['idle_seconds'].sum() / 3600
total_locked = df_filtered['locked_seconds'].sum() / 3600

total_expected_sum = total_active + total_idle + total_locked
pct_global = (total_active / total_expected_sum) * 100 if total_expected_sum > 0 else 0

col1.metric("Total Horas Ativas", f"{total_active:.1f}h")
col2.metric("Total Horas Ociosas", f"{total_idle:.1f}h")
col3.metric("Total Horas Bloqueado", f"{total_locked:.1f}h")
col4.metric("Desempenho Global", f"{pct_global:.1f}%", help="Porcentagem de tempo ativo")

st.markdown("### Ranking da Equipe no Período")
# Agrupa por operador
grouped = df_filtered.groupby("operator_name").agg({
    "active_seconds": "sum",
    "idle_seconds": "sum",
    "locked_seconds": "sum",
    "balance_h": "sum",
    "date": "nunique" # Dias logs
}).reset_index()

grouped["Total (h)"] = (grouped["active_seconds"] + grouped["idle_seconds"] + grouped["locked_seconds"]) / 3600
grouped["Ativo (h)"] = grouped["active_seconds"] / 3600
grouped["Ocioso (h)"] = grouped["idle_seconds"] / 3600
grouped["Bloqueado (h)"] = grouped["locked_seconds"] / 3600
grouped["Ativo (%)"] = (grouped["Ativo (h)"] / grouped["Total (h)"]) * 100
grouped["Saldo (h)"] = grouped["balance_h"]

st.dataframe(
    grouped[["operator_name", "date", "Ativo (h)", "Ocioso (h)", "Bloqueado (h)", "Ativo (%)", "Saldo (h)"]]
    .rename(columns={"date": "Dias Logs", "operator_name": "Colaborador"})
    .sort_values(by="Ativo (%)", ascending=False)
    .style.format({
        "Ativo (h)": "{:.1f}", 
        "Ocioso (h)": "{:.1f}", 
        "Bloqueado (h)": "{:.1f}",
        "Ativo (%)": "{:.1f}%",
        "Saldo (h)": "{:+.1f}h" # Exibe +1.0h ou -1.0h
    }),
    use_container_width=True
)

st.caption("Navegue pelas outras abas na barra lateral para ver detalhes diários ou comparar colaboradores.")
