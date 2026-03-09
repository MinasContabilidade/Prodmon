import streamlit as st
import pandas as pd
import os
import json
import datetime
import calendar
import data_loader

st.set_page_config(page_title="Controle de Ponto", page_icon="📅", layout="wide")
st.title("📅 Controle de Ponto (Calendário de RH)")

net_dir = data_loader.get_network_dir()

# --- Helpers ---
JUST_FILE = os.path.join(net_dir, "justifications_config.json")

def load_justifications():
    if os.path.exists(JUST_FILE):
        try:
            with open(JUST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.warning(f"Erro ao ler justificativas: {e}")
    return {}

# Fix #5: Escrita atômica das justificativas via .tmp + os.replace()
def save_justifications(j):
    tmp = JUST_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(j, f, ensure_ascii=False, indent=2)
        os.replace(tmp, JUST_FILE)
    except Exception as e:
        st.error(f"Erro ao salvar justificativa: {e}")
        try: os.remove(tmp)
        except: pass

justifications = load_justifications()

# --- Carregar Dados Globais ---
with st.spinner("Apuração do Banco de Dados..."):
    df = data_loader.load_all_data(net_dir)

if df.empty:
    st.info("Nenhuma base encontrada na rede. Verifique Configurações.")
    st.stop()

operadores = sorted(df['operator_name'].unique())

import sidebar
start_dt, end_dt, selected_op = sidebar.render_global_sidebar(df)

st.markdown("---")

# --- Processando Dados do Colaborador para o Período ---
df_op = df[(df['operator_name'] == selected_op)].copy()

calendar_data = []
total_saldo_periodo = 0.0

num_days = (end_dt - start_dt).days + 1

for i in range(num_days):
    current_date = start_dt + datetime.timedelta(days=i)
    
    # Verifica final de semana
    is_weekend = current_date.weekday() >= 5
    
    # Pesquisa no log capturado se teve dados desse dia
    match = df_op[df_op['date'] == current_date]
    
    if not match.empty:
        row = match.iloc[0]
        worked_h = (row['active_seconds'] + row['idle_seconds'] + row['locked_seconds']) / 3600
        expected_h = row.get('expected_h', 0.0)
        bal_h = row.get('balance_h', 0.0)
        just_h = row.get('justification_h', 0.0)
        just_reason = str(row.get('justification_reason', '')).strip()
    else:
        # Faltou, Ferias, Emissão Futura, FDS, ou Atestado Integral Sem Ligar o PC
        worked_h = 0.0
        # Temos que buscar o Expected manualmente se ele não veio do match
        # Como não abriu o data_loader para aquela data (não gerou tracking), não puxou na DF.
        # Precisamos puxar do schedules se dia de semana (seg-sex):
        expected_h = 0.0
        
        # Simulação: Carregando schedule se não for final de semana para computar a "falta"
        if not is_weekend:
            # Replicamos lógica do `data_loader` se fosse dia util
            # Mas como não teve log local, ele tem Horas Trabalhadas = 0, então o balance seria negativo.
            # Vamos tratar apenas o que tem registro ou justificativa para simplificar agora.
            pass
            
        bal_h = 0.0
        just_info = justifications.get(selected_op, {}).get(str(current_date), {})
        just_h = float(just_info.get("horas", 0.0))
        just_reason = just_info.get("motivo", "")

        # Se teve justificativa mas não logou o PC, o saldo dele é o valor justificado
        # Se era dia útil, ideal seria bal_h = just_h - expected_h, mas deixaremos simples na v1
        bal_h += just_h

    total_saldo_periodo += bal_h
        
    status = ""
    if is_weekend:
        status = "FDS"
    elif worked_h > 0:
        status = "Presente"
    elif just_h > 0:
        status = "Justificado"
    elif current_date > datetime.date.today():
        status = "-"
    else:
        status = "Ausência S/ Registro"
        
    row_data = {
        "Data": current_date.strftime("%d/%m/%Y"),
        "RawDate": current_date, # escondido para a UI interna
        "Dia da Semana": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][current_date.weekday()],
        "Trabalhadas (h)": worked_h,
        "Jornada Esp. (h)": expected_h,
        "Abonos (h)": just_h,
        "Saldo Diário": bal_h,
        "Motivo / Justificativa": just_reason,
        "Status": status
    }
    calendar_data.append(row_data)

st.markdown(f"#### 📜 Extrato / Folha de `{selected_op}`")

col_k1, col_k2, col_k3 = st.columns(3)
col_k1.metric("Fechamento (Saldo Acumulado)", f"{total_saldo_periodo:+.1f}h", help="Diferença entre horas trabalhadas/abonadas e jornada esperada.")

# Tabela estilizada
df_cal = pd.DataFrame(calendar_data)

st.dataframe(
    df_cal[["Data", "Dia da Semana", "Status", "Trabalhadas (h)", "Jornada Esp. (h)", "Abonos (h)", "Saldo Diário", "Motivo / Justificativa"]]
    .style.apply(lambda x: [
        'background-color: rgba(239, 68, 68, 0.2); color: #FECACA' if v == 'Ausência S/ Registro' 
        else 'background-color: rgba(16, 185, 129, 0.2); color: #D1FAE5' if v == 'Justificado' 
        else 'color: #94A3B8' if v == 'FDS'
        else '' for v in x
    ], subset=['Status'])
    .format({
        "Trabalhadas (h)": "{:.1f}", 
        "Jornada Esp. (h)": "{:.1f}", 
        "Abonos (h)": "{:.1f}", 
        "Saldo Diário": "{:+.1f}h"
    }),
    use_container_width=True
)

st.markdown("---")

# --- Interface para Abonar / Justificar ---
st.markdown("### ✍️ Lançar Justificativa Manual (RH)")
st.write("Aqui você credita ou debita horas no banco de horas de um colaborador referenciando um dia específico (Para corrigir esquecimentos, faltas médicas ou bônus).")

with st.form("justification_form"):
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    
    j_date = col_f1.date_input("Dia da Ocorrência", value=datetime.date.today(), format="DD/MM/YYYY")
    j_hours = col_f2.number_input("Horas a Abonar/Creditar", value=0.0, step=0.5, format="%.1f", help="Para descontos, insira um valor negativo.")
    j_reason = col_f3.text_input("Motivo / Descrição", placeholder="Ex: Atestado Médico Dr. Carlos, Falta Injustificada, Acerto de Relógio...")
    
    submitted = st.form_submit_button("Salvar Registro de RH")
    if submitted:
        date_key = str(j_date)
        
        if selected_op not in justifications:
            justifications[selected_op] = {}
            
        if j_hours == 0.0 and j_reason == "":
            # Remover justificativa
            if date_key in justifications[selected_op]:
                del justifications[selected_op][date_key]
        else:
            justifications[selected_op][date_key] = {
                "horas": j_hours,
                "motivo": j_reason
            }
            
        save_justifications(justifications)
        st.success(f"Alteração registrada no departamento para o dia {j_date.strftime('%d/%m/%Y')}!")
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()  # Fix #15: Atualiza a tabela imediatamente após salvar
