import streamlit as st
import pandas as pd
import data_loader

st.set_page_config(page_title="Comparativo", page_icon="⚖️", layout="wide")
st.title("⚖️ Comparativo de Colaboradores")

net_dir = data_loader.get_network_dir()

with st.spinner("Carregando bases..."):
    df = data_loader.load_all_data(net_dir)

if df.empty:
    st.warning("Sem dados.")
    st.stop()

operadores = sorted(df['operator_name'].unique())

if len(operadores) < 2:
    st.warning("É necessário ter pelo menos 2 colaboradores registrados para fazer um comparativo.")
    st.stop()

# Filtros Gerais (Data)
import datetime
today = datetime.date.today()
start_of_year = datetime.date(today.year, 1, 1)

st.sidebar.markdown("### 📅 Período Comum")
col_s1, col_s2 = st.sidebar.columns(2)
start_dt = col_s1.date_input("Data Inicial", value=start_of_year, format="DD/MM/YYYY")
end_dt = col_s2.date_input("Data Final", value=today, format="DD/MM/YYYY")

if start_dt > end_dt:
    st.sidebar.error("A Data Inicial não pode ser maior que a Final.")
    st.stop()

df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Seleção A")
    op_A = st.selectbox("Colaborador A", operadores, index=0)
    df_A = df[df['operator_name'] == op_A]

with col2:
    st.markdown("### Seleção B")
    op_B = st.selectbox("Colaborador B", operadores, index=1 if len(operadores) > 1 else 0)
    df_B = df[df['operator_name'] == op_B]

st.markdown("---")

# Métrica de Consolidação
def render_metrics(dataset, title):
    if dataset.empty:
        st.info("Nenhum dado.")
        return
        
    total_active = dataset['active_seconds'].sum() / 3600
    total_idle = dataset['idle_seconds'].sum() / 3600
    total_locked = dataset['locked_seconds'].sum() / 3600
    
    total = total_active + total_idle + total_locked
    pct = (total_active / total) * 100 if total > 0 else 0
    
    st.metric(f"Desempenho ({title})", f"{pct:.1f}%", help="Média de foco no período")
    st.metric(f"Horas Ativas", f"{total_active:.1f}h")
    st.metric(f"Horas Ociosas", f"{total_idle:.1f}h")
    st.metric(f"Horas Bloqueado", f"{total_locked:.1f}h")

c1, c2 = st.columns(2)
with c1:
    st.markdown(f"**Resultados Acumulados: {op_A}**")
    render_metrics(df_A, op_A)

with c2:
    st.markdown(f"**Resultados Acumulados: {op_B}**")
    render_metrics(df_B, op_B)

st.markdown("---")
st.markdown("### Histórico Diário Comparado (Horas Ativas)")

# Agrupar por data para o gráfico comparativo
g_A = df_A.groupby("date")["active_seconds"].sum().reset_index()
g_A["Colaborador"] = op_A
g_B = df_B.groupby("date")["active_seconds"].sum().reset_index()
g_B["Colaborador"] = op_B

comp_df = pd.concat([g_A, g_B])
comp_df["Ativo (h)"] = comp_df["active_seconds"] / 3600

if not comp_df.empty:
    import plotly.express as px
    fig = px.bar(comp_df, x="date", y="Ativo (h)", color="Colaborador", barmode="group",
                 title="Total de Horas Ativas por Dia")
    st.plotly_chart(fig, use_container_width=True)
