import streamlit as st
import datetime
import calendar

def render_global_sidebar(df):
    """
    Renderiza o painel lateral com Filtros Globais para todas as páginas.
    Inclui navegação rápida por mês (◀/▶) que ajusta automaticamente Data Inicial e Final.
    Retorna (start_date, end_date, anchor_name).
    """
    st.sidebar.header("🔍 Filtros Globais")

    # --- Inicialização do Session State ---
    today = datetime.date.today()
    if "global_start_date" not in st.session_state:
        st.session_state["global_start_date"] = datetime.date(today.year, 1, 1)
    if "global_end_date" not in st.session_state:
        st.session_state["global_end_date"] = today

    operadores = sorted(df['operator_name'].unique().tolist()) if not df.empty else []

    if "global_anchor" not in st.session_state:
        st.session_state["global_anchor"] = operadores[0] if operadores else None

    # --- Navegação Rápida por Mês (◀ Mês/Ano ▶) ---
    ref_date = st.session_state["global_start_date"]
    month_names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    label_mes = f"{month_names[ref_date.month - 1]} / {ref_date.year}"

    nav_prev, nav_label, nav_next = st.sidebar.columns([1, 2, 1])
    with nav_prev:
        if st.button("◀", key="nav_prev_month", use_container_width=True):
            # Retrocede 1 mês
            if ref_date.month == 1:
                new_start = datetime.date(ref_date.year - 1, 12, 1)
            else:
                new_start = datetime.date(ref_date.year, ref_date.month - 1, 1)
            _, last_day = calendar.monthrange(new_start.year, new_start.month)
            st.session_state["global_start_date"] = new_start
            st.session_state["global_end_date"] = datetime.date(new_start.year, new_start.month, last_day)
            st.rerun()
    with nav_label:
        st.markdown(f"<div style='text-align:center;padding-top:6px;font-weight:bold;'>{label_mes}</div>", unsafe_allow_html=True)
    with nav_next:
        if st.button("▶", key="nav_next_month", use_container_width=True):
            # Avança 1 mês
            if ref_date.month == 12:
                new_start = datetime.date(ref_date.year + 1, 1, 1)
            else:
                new_start = datetime.date(ref_date.year, ref_date.month + 1, 1)
            _, last_day = calendar.monthrange(new_start.year, new_start.month)
            st.session_state["global_start_date"] = new_start
            st.session_state["global_end_date"] = datetime.date(new_start.year, new_start.month, last_day)
            st.rerun()

    # --- Datas Fine-Tuning ---
    col1, col2 = st.sidebar.columns(2)
    start_dt = col1.date_input("Data Inicial", value=st.session_state["global_start_date"], format="DD/MM/YYYY")
    end_dt = col2.date_input("Data Final", value=st.session_state["global_end_date"], format="DD/MM/YYYY")

    # --- Colaborador Âncora ---
    anchor_index = 0
    if st.session_state["global_anchor"] in operadores:
        anchor_index = operadores.index(st.session_state["global_anchor"])

    sel_anchor = st.sidebar.selectbox("Colaborador Âncora", options=operadores, index=anchor_index, help="Pessoa principal referenciada nos painéis individuais/comparativos e na folha de ponto.")

    # --- Atualiza Session State ---
    st.session_state["global_start_date"] = start_dt
    st.session_state["global_end_date"] = end_dt
    st.session_state["global_anchor"] = sel_anchor

    if start_dt > end_dt:
        st.sidebar.error("A Data Inicial não pode ser maior que a Data Final.")
        st.stop()

    st.sidebar.markdown("---")

    if st.sidebar.button("🔄 Recarregar Dados da Rede"):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()

    return start_dt, end_dt, sel_anchor
