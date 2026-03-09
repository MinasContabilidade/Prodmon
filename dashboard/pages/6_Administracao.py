import streamlit as st
import pandas as pd
import os
import json
import datetime
import data_loader

st.set_page_config(page_title="Administração", page_icon="⚙️", layout="wide")
st.title("⚙️ Administração & Base de Dados")

import sidebar

net_dir = data_loader.get_network_dir()

# Tenta carregar dados. Se net_dir não existir, avisa mas permite configurar.
df_global = pd.DataFrame()
if net_dir and os.path.exists(str(net_dir)):
    with st.spinner("Buscando dados globais..."):
        df_global = data_loader.load_all_data(net_dir)

if not df_global.empty:
    start_dt, end_dt, global_anchor = sidebar.render_global_sidebar(df_global)
else:
    st.sidebar.warning("Sem dados carregados. Configure a pasta de rede abaixo.")
    global_anchor = None

# ===========================================================
# LAYOUT PRINCIPAL: 2 COLUNAS (2/3 Consolidação | 1/3 Rede)
# ===========================================================
col_main, col_side = st.columns([2, 1])

# ---- COLUNA DIREITA (1/3): Configuração de Rede ----
with col_side:
    st.markdown("### 📂 Base de Dados (Rede)")
    st.caption("Defina o local onde os arquivos JSON dos agentes são armazenados.")

    # Fix #8: O DASH_CONFIG_FILE deve apontar para dashboard/, não para pages/
    DASH_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard_config.json")

    def load_dash_config():
        if os.path.exists(DASH_CONFIG_FILE):
            try:
                with open(DASH_CONFIG_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                st.warning(f"Erro ao ler configuração salva: {e}")
        return {}

    # Fix #5: Escrita atômica via arquivo temporário + os.replace()
    def save_dash_config(cfg):
        tmp = DASH_CONFIG_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cfg, f)
        os.replace(tmp, DASH_CONFIG_FILE)

    dash_cfg = load_dash_config()
    saved_path = dash_cfg.get("network_dir", "")
    if not saved_path:
        saved_path = data_loader.get_network_dir()

    new_dir = st.text_input("Caminho da Pasta de Rede:", value=saved_path)
    if st.button("💾 Salvar Caminho", use_container_width=True):
        # Fix #4: Validação básica do caminho para evitar Path Traversal acidental
        # Aceita se: (a) pasta existe, e (b) não parece um dir crítico do SO
        blocked_paths = ["c:\\windows", "c:\\program files", "c:\\system32"]
        normalized = new_dir.strip().lower().rstrip("\\")
        is_blocked = any(normalized == p or normalized.startswith(p + "\\") for p in blocked_paths)
        if is_blocked:
            st.error("❌ Caminho bloqueado por segurança. Utilize um diretório dedicado ao ProdMon.")
        elif not os.path.isabs(new_dir.strip()):
            st.error("❌ Forneça um caminho absoluto (ex: \\\\SERVIDOR\\ProdMon ou Z:\\ProdMon).")
        else:
            dash_cfg["network_dir"] = new_dir.strip()
            save_dash_config(dash_cfg)
            st.success("Caminho salvo! Recarregando...")
            st.cache_resource.clear()
            st.cache_data.clear()
            st.rerun()

    if net_dir and os.path.exists(str(net_dir)):
        st.success(f"✅ Conectado: `{net_dir}`")
    else:
        st.error(f"❌ Pasta inacessível: `{net_dir}`")

    st.markdown("---")
    st.markdown("### 🧹 Cache")
    if st.button("Limpar Cache de Dados Atuais", use_container_width=True):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.success("Cache limpo!")

# ---- COLUNA ESQUERDA (2/3): Consolidação + Jornada ----
with col_main:
    st.markdown("### 📦 Ferramenta de Consolidação de Logs")
    st.warning(
        "Com o tempo, a pasta de rede acumula milhares de arquivos `.json` "
        "(1 por máquina, por dia). Isso pode deixar o Dashboard lento. "
        "Utilize a consolidação abaixo para juntar os arquivos "
        "de meses anteriores em um único arquivo de alta performance."
    )

    c1, c2 = st.columns(2)
    with c1:
        year = st.number_input("Ano da Consolidação", value=datetime.date.today().year, min_value=2020, max_value=2099)
    with c2:
        month = st.selectbox("Mês da Consolidação", options=range(1, 13), format_func=lambda x: f"{x:02d}")

    # Confirmação explícita
    anchor_label = f" do colaborador **{global_anchor}**" if global_anchor else ""
    st.markdown(f"Será consolidado o período **{month:02d}/{year}**{anchor_label} (todos os colaboradores).")

    if st.button("🚀 Executar Consolidação", type="primary", use_container_width=True):
        with st.spinner(f"Agrupando arquivos de {year:04d}-{month:02d}..."):
            qtde_deletados, total_registros = data_loader.consolidate_logs(net_dir, year, month)

            if qtde_deletados > 0:
                st.success(f"**Sucesso!** {qtde_deletados} arquivos diários foram unificados num único arquivo consolidado.")
                st.info(f"O arquivo consolidado contém agora {total_registros} registros de sessões.")
                st.cache_resource.clear()
                st.cache_data.clear()
            else:
                st.info("Nenhum arquivo individual encontrado para esse mês/ano que já não estivesse consolidado.")

    st.markdown("---")
    st.markdown("### 👥 Gestão de Jornada dos Colaboradores")
    st.write("Defina o horário padrão de cada operador para o cálculo automático de horas extras e horas devidas.")

    # Configurações de jornada
    if net_dir and os.path.exists(str(net_dir)):
        SCHEDULE_FILE = os.path.join(net_dir, "schedules_config.json")

        def load_schedules():
            if os.path.exists(SCHEDULE_FILE):
                try:
                    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                        return json.load(f)
                except:
                    pass
            return {}

        # Fix #5: Escrita atômica nas configurações de jornada
        def save_schedules(sched):
            tmp = SCHEDULE_FILE + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(sched, f, ensure_ascii=False, indent=2)
                os.replace(tmp, SCHEDULE_FILE)
            except Exception as e:
                st.error(f"Erro ao salvar jornada: {e}")
                try: os.remove(tmp)
                except: pass

        schedules = load_schedules()

        if not df_global.empty:
            operadores = sorted(df_global['operator_name'].unique())
            anchor_idx = operadores.index(global_anchor) if global_anchor and global_anchor in operadores else 0
            selected_op = st.selectbox("Selecione o Operador para configurar a jornada oficial (RH):", operadores, index=anchor_idx)

            op_cfg = schedules.get(selected_op, {
                "entry_time": "08:00",
                "exit_time": "18:00",
                "lunch_minutes": 60,
                "break_minutes": 15
            })

            with st.form("form_jornada"):
                c1, c2, c3, c4 = st.columns(4)

                try:
                    def_entry = datetime.datetime.strptime(op_cfg["entry_time"], "%H:%M").time()
                    def_exit = datetime.datetime.strptime(op_cfg["exit_time"], "%H:%M").time()
                except:
                    def_entry = datetime.time(8, 0)
                    def_exit = datetime.time(18, 0)

                inp_entry = c1.time_input("Hora de Chegada", value=def_entry)
                inp_exit = c2.time_input("Hora de Saída", value=def_exit)
                inp_lunch = c3.number_input("Almoço (min)", value=int(op_cfg.get("lunch_minutes", 60)), min_value=0, max_value=240, step=15)
                inp_break = c4.number_input("Lanches/Pausas (min)", value=int(op_cfg.get("break_minutes", 15)), min_value=0, max_value=120, step=5)

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
                    st.cache_data.clear()
        else:
            st.info("Nenhum operador encontrado na base de dados para configurar jornada.")
    else:
        st.info("Configure a pasta de rede à direita para poder definir jornadas.")
