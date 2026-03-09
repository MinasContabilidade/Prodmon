import streamlit as st
import pandas as pd
import os
import data_loader

st.set_page_config(
    page_title="ProdMon | BI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 ProdMon - Visão Geral")
st.markdown("Bem-vindo ao painel de produtividade da equipe.")

net_dir = data_loader.get_network_dir()

if not net_dir or str(net_dir).strip() == "":
    st.error("⚠️ Caminho da rede não configurado. Acesse a aba Administração para definir.")
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

import sidebar
start_dt, end_dt, sel_anchor = sidebar.render_global_sidebar(df)

mask = (df['date'] >= start_dt) & (df['date'] <= end_dt)
df_filtered = df.loc[mask]

# --- Alerta Inteligente de Meses Não Consolidados ---
unconsolidated_months = data_loader.get_unconsolidated_past_months(net_dir)
if unconsolidated_months:
    st.info(f"💡 **Dica de Performance:** Há {len(unconsolidated_months)} mês(es) finalizado(s) (ex: {unconsolidated_months[-1]}) com arquivos avulsos na rede. Vá na aba **Administração** e clique em **Consolidar** para agilizar o dashboard!", icon="⚡")

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
