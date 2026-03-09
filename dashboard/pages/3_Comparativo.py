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

import sidebar
start_dt, end_dt, op_A = sidebar.render_global_sidebar(df)

st.markdown(f"**Analisando período:** `{start_dt.strftime('%d/%m/%Y')}` a `{end_dt.strftime('%d/%m/%Y')}`")

df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Colaborador Âncora (A)")
    st.info(f"**{op_A}**")
    df_A = df[df['operator_name'] == op_A]

with col2:
    st.markdown("### Seleção Desafiante (B)")
    # Remove A da lista de B para nao comparar com si próprio
    opcoes_b = [op for op in operadores if op != op_A]
    op_B = st.selectbox("Colaborador B", opcoes_b, index=0 if opcoes_b else None)
    df_B = df[df['operator_name'] == op_B] if op_B else pd.DataFrame()

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
    fig = px.bar(
        comp_df, 
        x="date", 
        y="Ativo (h)", 
        color="Colaborador", 
        barmode="group",
        title="Total de Horas Ativas por Dia (Comparativo)",
        color_discrete_sequence=["#38BDF8", "#818CF8"], # Sky 400 e Indigo 400
        template="plotly_dark"
    )
    
    fig.update_layout(
        font_family="Outfit",
        title_font_size=20,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Data",
        yaxis_title="Horas Ativas",
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.05)")
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
