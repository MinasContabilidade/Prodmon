import streamlit as st
import pandas as pd
import plotly.express as px
import data_loader
import sidebar

st.set_page_config(page_title="Dashboard RH", page_icon="👥", layout="wide")
st.title("👥 Dashboard de Recursos Humanos")

net_dir = data_loader.get_network_dir()

with st.spinner("Apuração do Banco de Dados..."):
    df = data_loader.load_all_data(net_dir)

if df.empty:
    st.info("Nenhuma base encontrada na rede. O agente já foi instalado?")
    st.stop()

start_dt, end_dt, sel_anchor = sidebar.render_global_sidebar(df)

st.markdown(f"**Resumo da Equipe de `{start_dt.strftime('%d/%m/%Y')}` a `{end_dt.strftime('%d/%m/%Y')}`**")

# Filtra o DF pro periodo global
mask = (df['date'] >= start_dt) & (df['date'] <= end_dt)
df_filtered = df.loc[mask]

if df_filtered.empty:
    st.warning("Nenhum dado produtivo no período selecionado.")
    st.stop()

# --- Cálculos Macro da Equipe ---
grouped = df_filtered.groupby("operator_name").agg({
    "balance_h": "sum",
    "justification_h": "sum",
    "active_seconds": "sum",
}).reset_index()

st.markdown("---")
# Destaques Top 3
col1, col2, col3 = st.columns(3)

# 1. Banco de Horas Positivo (Extratores)
top_banco = grouped.sort_values(by="balance_h", ascending=False).head(3)
with col1:
    st.markdown("### 🏆 Top Banco Positivo")
    if not top_banco.empty and top_banco.iloc[0]["balance_h"] > 0:
        for idx, row in top_banco.iterrows():
            if row["balance_h"] > 0:
                st.metric(row['operator_name'], f"+{row['balance_h']:.1f}h")
    else:
        st.write("Nenhum saldo positivo.")

# 2. Banco de Horas Negativo (Devedores)
worst_banco = grouped.sort_values(by="balance_h", ascending=True).head(3)
with col2:
    st.markdown("### ⚠️ Maior Saldo Devedor")
    if not worst_banco.empty and worst_banco.iloc[0]["balance_h"] < 0:
        for idx, row in worst_banco.iterrows():
            if row["balance_h"] < 0:
                st.metric(row['operator_name'], f"{row['balance_h']:.1f}h")
    else:
        st.write("Nenhum saldo negativo.")

# 3. Mais Abonados (Justificativas Médicas, etc)
top_abonos = grouped.sort_values(by="justification_h", ascending=False).head(3)
with col3:
    st.markdown("### 🩺 Mais Abonos/Atestados")
    if not top_abonos.empty and top_abonos.iloc[0]["justification_h"] > 0:
        for idx, row in top_abonos.iterrows():
            if row["justification_h"] > 0:
                st.metric(row['operator_name'], f"{row['justification_h']:.1f}h abonadas")
    else:
        st.write("Nenhum abono registrado no período.")

st.markdown("---")

# Ranking Completo
st.markdown("### 📊 Extrato Completo de Fechamento")
st.dataframe(
    grouped.rename(columns={
        "operator_name": "Colaborador",
        "balance_h": "Saldo Banco (h)",
        "justification_h": "Total Abonado (h)"
    })[["Colaborador", "Saldo Banco (h)", "Total Abonado (h)"]]
    .sort_values(by="Saldo Banco (h)", ascending=False)
    .style.format({
        "Saldo Banco (h)": "{:+.1f}h",
        "Total Abonado (h)": "{:.1f}h"
    }),
    use_container_width=True
)

st.caption("Fatores como finais de semana não processados (sem arquivo do agente) ou ausências totais s/ atestados (sem agente ou abono) constam na aba 'Folha de Ponto' diária.")
