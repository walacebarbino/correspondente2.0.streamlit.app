import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. FUNÇÃO DE LOGIN (REGRA 1 - PRESERVADA) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    st.title("🔐 Login Correspondente 2.0")
    with st.form("login_form"):
        password = st.text_input("Digite a senha:", type="password")
        if st.form_submit_button("Entrar"):
            if password == "1234":
                st.session_state["password_correct"] = True
                st.rerun()
            else: st.error("😕 Senha incorreta.")
    return False

def formatar_br(valor):
    try: return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

if check_password():
    st.set_page_config(page_title="Gestão Correspondente 2026", layout="wide", page_icon="📊")

    # --- 2. CONEXÃO (MANTIDA) ---
    conn = st.connection("gsheets", type=GSheetsConnection)
    URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1n6529TSBqYhwqAq-ZwVleV0b9q0p38PSPT4eU1z-uNc/edit"

    # Lendo dados e forçando nomes de colunas do seu padrão original
    df = conn.read(spreadsheet=URL_PLANILHA, ttl=0).dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]

    # Tratamento de Data para o padrão Brasileiro (REGRA 1)
    if not df.empty:
        df['DATA_DT'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True, errors='coerce')
        df['DATA_EXIBIR'] = df['DATA_DT'].dt.strftime('%d/%m/%Y')
        df['MÊS'] = df['DATA_DT'].dt.strftime('%m/%Y')

    # --- SIDEBAR (LOGO E CADASTRO COMPLETO) ---
    try: st.sidebar.image("parceria.JPG", use_container_width=True)
    except: pass

    with st.sidebar:
        st.divider()
        st.header("📥 Gestão de Dados")
        with st.form("form_cadastro", clear_on_submit=True):
            f_data = st.date_input("DATA", datetime.now(), format="DD/MM/YYYY")
            f_nome = st.text_input("Nome do Comprador")
            f_cpf = st.text_input("CPF")
            f_imovel = st.text_input("Nome do Imóvel / Construtora")
            f_valor = st.number_input("Valor (R$)", min_value=0.0)
            f_imobiliaria = st.text_input("Imobiliária")
            f_enquadramento = st.selectbox("Enquadramento", ["SBPE", "MCMV", "FGTS", "Outros"])
            f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
            
            if st.form_submit_button("Cadastrar"):
                nova_linha = pd.DataFrame([[
                    f_data.strftime("%d/%m/%Y"), f_nome, f_cpf, f_imovel, f_valor, f_imobiliaria, f_enquadramento, f_status
                ]], columns=df.columns[:8])
                df_updated = pd.concat([df[df.columns[:8]], nova_linha], ignore_index=True)
                conn.update(spreadsheet=URL_PLANILHA, data=df_updated)
                st.cache_data.clear()
                st.rerun()

    tab_bi, tab_carteira = st.tabs(["📊 Dashboard Profissional", "📋 Carteira de Clientes"])

    if not df.empty:
        # --- ABA 1: BI (REGRA 1 - TODAS AS MÉTRICAS) ---
        with tab_bi:
            st.title("📊 BI e Performance")
            m1, m2, m3, m4 = st.columns(4)
            total_v = pd.to_numeric(df.iloc[:, 4], errors='coerce').sum()
            pago = pd.to_numeric(df[df.iloc[:, 7] == 'Pago'].iloc[:, 4], errors='coerce').sum()
            ticket = (total_v / len(df)) if len(df) > 0 else 0

            m1.metric("Total de Dossiês", f"{len(df)} PACs")
            m2.metric("Volume Total", formatar_br(total_v))
            m3.metric("Total Pago", formatar_br(pago))
            m4.metric("Ticket Médio", formatar_br(ticket))

            st.divider()
            st.subheader("📑 Resumo Financeiro Detalhado (Excel Style)")
            df_resumo = df.groupby([df.columns[7], df.columns[6]])[df.columns[4]].sum().reset_index()
            df_resumo.columns = ['Status', 'Enquadramento', 'Valor']
            
            html_code = """<style>.tab-ex{width:100%;border-collapse:collapse;}.st-row{background-color:#D9E1F2;font-weight:bold;}.en-row{background-color:#ffffff;}.tab-ex td{padding:10px;border:1px solid #D9E1F2;}.val{text-align:right;}</style><table class='tab-ex'>"""
            for status in sorted(df_resumo['Status'].unique()):
                sub_v = df_resumo[df_resumo['Status'] == status]['Valor'].sum()
                html_code += f"<tr class='st-row'><td>{status}</td><td class='val'>{formatar_br(sub_v)}</td></tr>"
                for _, row in df_resumo[df_resumo['Status'] == status].iterrows():
                    html_code += f"<tr class='en-row'><td style='padding-left:40px'>{row['Enquadramento']}</td><td class='val'>{formatar_br(row['Valor'])}</td></tr>"
            st.markdown(html_code + "</table>", unsafe_allow_html=True)

        # --- ABA 2: CARTEIRA (REGRA 1 - TODAS AS COLUNAS) ---
        with tab_carteira:
            st.title("📋 Gestão da Carteira")
            # Cabeçalho da Tabela
            h = st.columns([1, 1.5, 1, 1, 1, 1, 1, 0.5])
            titulos = ["**Data**", "**Comprador**", "**CPF**", "**Imóvel**", "**Valor**", "**Imobiliária**", "**Status**", " "]
            for col, t in zip(h, titulos): col.write(t)

            with st.container(height=500): # ROLAGEM PRESERVADA
                for i, r in df.iterrows():
                    c = st.columns([1, 1.5, 1, 1, 1, 1, 1, 0.5])
                    c[0].write(r['DATA_EXIBIR'])
                    c[1].write(r.iloc[1]) # Nome
                    c[2].write(r.iloc[2]) # CPF
                    c[3].write(r.iloc[3]) # Imóvel
                    c[4].write(formatar_br(r.iloc[4])) # Valor
                    c[5].write(r.iloc[5]) # Imobiliária
                    c[6].write(r.iloc[7]) # Status
                    if c[7].button("🗑️", key=f"del_{i}"):
                        conn.update(spreadsheet=URL_PLANILHA, data=df.drop(i)[df.columns[:8]])
                        st.cache_data.clear()
                        st.rerun()
