import streamlit as st
import pandas as pd
import plotly.express as px
import data_loader

st.set_page_config(page_title="Perfil Individual", page_icon="👤", layout="wide")
st.title("👤 Perfil Individual (Timeline)")

net_dir = data_loader.get_network_dir()

with st.spinner("Carregando bases..."):
    df = data_loader.load_all_data(net_dir)

if df.empty:
    st.warning("Sem dados.")
    st.stop()

import sidebar
start_dt, end_dt, selected_op = sidebar.render_global_sidebar(df)

st.markdown(f"**Foco em:** `{selected_op}`")

# Filtra datas disponíveis para o colaborador
df_op = df[df['operator_name'] == selected_op]

# Respeitar o Filtro Global de datas
mask = (df_op['date'] >= start_dt) & (df_op['date'] <= end_dt)
df_op = df_op.loc[mask]

datas_disp = sorted(df_op['date'].unique(), reverse=True)

if not datas_disp:
    st.info("Nenhuma data encontrada para este operador no período do Filtro Global.")
    st.stop()

def format_date_br(d):
    return d.strftime("%d/%m/%Y")

selected_date = st.selectbox("Selecione o Dia para Timeline (dentro do Filtro Global):", datas_disp, format_func=format_date_br)

# Busca o machine_name exato daquele dia
machine_name = df_op[df_op['date'] == selected_date].iloc[0]['machine']

st.markdown(f"**Análise detalhada de {selected_op} no dia {selected_date} (PC: {machine_name})**")

# Carrega a linha do tempo bruta daquele dia e máquina
timeline_df = data_loader.get_user_events_for_timeline(net_dir, machine_name, str(selected_date))

if timeline_df.empty:
    st.warning("Não foi possível montar a timeline (eventos detalhados não encontrados no JSON original).")
else:
    # Configuração de Cores Premium (UI/UX Pro Max)
    color_discrete_map = {
        "Active": "#38BDF8", # Sky 400
        "Idle": "#F59E0B",   # Amber 500
        "Locked": "#64748B"  # Slate 500
    }
    
    fig = px.timeline(
        timeline_df, 
        x_start="Start", 
        x_end="Finish", 
        y="State", 
        color="State",
        color_discrete_map=color_discrete_map,
        title=f"Jornada de Trabalho: {selected_op}",
        labels={"State": "Estado"},
        hover_data=["Duration (s)"],
        template="plotly_dark"
    )
    
    # Ordem do Eixo Y e Estética Global
    fig.update_yaxes(categoryorder="array", categoryarray=["Active", "Idle", "Locked"], gridcolor="rgba(255,255,255,0.05)")
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.05)")
    
    fig.update_layout(
        font_family="Outfit",
        title_font_size=20,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Horário do Dia",
        yaxis_title="",
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    # Exibe resumo do dia selecionado
    row = df_op[df_op['date'] == selected_date].iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entrada Atual", str(row['session_start'].strftime('%H:%M:%S')) if pd.notna(row['session_start']) else "-")
    c2.metric("Saída Atual", str(row['session_end'].strftime('%H:%M:%S')) if pd.notna(row['session_end']) else "Em andamento")
    c3.metric("Tempo Ativo", f"{(row['active_seconds']/3600):.1f}h")
    c4.metric("Tempo Ocioso", f"{(row['idle_seconds']/3600):.1f}h")
    
    st.markdown("---")
    st.markdown("### ⏲️ Controle de Jornada (Neste dia)")
    
    b1, b2, b3, b4 = st.columns(4)
    exp_h = row.get('expected_h', 0.0)
    bal_h = row.get('balance_h', 0.0)
    exp_in = row.get('expected_entry', 'Não Configurado')
    exp_out = row.get('expected_exit', '-')
    
    b1.metric("Entrada p/ Jornada", exp_in)
    b2.metric("Saída p/ Jornada", exp_out)
    b3.metric("Espectativa de Trabalho", f"{exp_h:.1f}h" if exp_h > 0 else "Sem config.")
    
    # Lógica de cor pro saldo
    saldo_str = f"{bal_h:+.1f}h" if exp_h > 0 else "-"
    b4.metric("Saldo do Dia (Banco)", saldo_str, delta=saldo_str if exp_h > 0 else None)
    
    if exp_h > 0:
        if bal_h < 0:
            st.warning(f"O colaborador trabalhou **{abs(bal_h):.1f}h a menos** que o esperado pela jornada registrada.")
        elif bal_h > 0:
            st.success(f"O colaborador realizou **{bal_h:.1f}h a mais** que o esperado pela jornada registrada.")
        else:
            st.info("A carga horária foi cumprida perfeitamente conforme a jornada.")
