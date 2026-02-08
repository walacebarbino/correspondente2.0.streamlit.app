import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests

# --- 1. FUNÇÃO DE LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    st.title("🔐 Login Correspondente 2.0")
    with st.form("login_form"):
        password = st.text_input("Digite a senha para acessar:", type="password")
        submit_button = st.form_submit_button("Entrar")
        if submit_button:
            if password == "1234":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("😕 Senha incorreta.")
    return False

# Formatação BR (R$ 1.234,56)
def formatar_br(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

if check_password():
    st.set_page_config(page_title="Gestão Correspondente 2026", layout="wide", page_icon="📊")

    # Botão para forçar atualização sem precisar de F5
    if st.sidebar.button("🔄 Atualizar Dados Agora"):
        st.cache_data.clear()
        st.rerun()

    if st.sidebar.button("🚪 Sair do Sistema"):
        st.session_state["password_correct"] = False
        st.rerun()

    LINK_PLANILHA = "https://docs.google.com/spreadsheets/d/1n6529TSBqYhwqAq-ZwVleV0b9q0p38PSPT4eU1z-uNc/export?format=xlsx"

    # REMOVI O CACHE LONGO PARA FORÇAR A ATUALIZAÇÃO
    def carregar_dados():
        try:
            # Adicionando um parâmetro aleatório no link para enganar o cache do Google
            url = f"{LINK_PLANILHA}&cache={datetime.now().timestamp()}"
            response = requests.get(url, timeout=20)
            df = pd.read_excel(io.BytesIO(response.content))
            df.columns = [str(c).strip() for c in df.columns]
            mapeamento = {'Nome_do_Comprador': 'Nome do Comprador', 'Valor (R$)': 'Valor', 'Nome do Imóvel / Construtora': 'Imóvel'}
            df = df.rename(columns=mapeamento)
            if 'DATA' in df.columns:
                df['DATA_DT'] = pd.to_datetime(df['DATA'], errors='coerce')
                df = df.dropna(subset=['DATA_DT'])
                df['DATA_EXIBIR'] = df['DATA_DT'].dt.strftime('%d/%m/%Y')
                df['MÊS'] = df['DATA_DT'].dt.strftime('%m/%Y')
            return df
        except:
            return pd.DataFrame()

    df = carregar_dados()

    # --- BARRA LATERAL (REGRA 1 - MANTIDA) ---
    with st.sidebar:
        st.divider()
        st.header("📥 Gestão de Dados")
        with st.form("form_cadastro"):
            st.subheader("Novo Cadastro Manual")
            f_data = st.date_input("DATA", datetime.now(), format="DD/MM/YYYY")
            f_nome = st.text_input("Nome do Comprador")
            f_cpf = st.text_input("CPF")
            f_imovel = st.text_input("Nome do Imóvel / Construtora")
            f_valor = st.number_input("Valor (R$)", min_value=0.0)
            f_imobiliaria = st.text_input("Imobiliária")
            f_enquadramento = st.selectbox("Enquadramento", ["SBPE", "MCMV", "FGTS", "Outros"])
            f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
            if st.form_submit_button("Cadastrar"):
                st.info("Dado recebido!")

    tab_bi, tab_carteira = st.tabs(["📊 Dashboard Profissional", "📋 Carteira de Clientes"])

    if not df.empty:
        with tab_bi:
            st.title("📊 BI e Performance de Processos")
            
            m1, m2, m3, m4 = st.columns(4)
            total_v = df['Valor'].sum()
            pago = df[df['Status'] == 'Pago']['Valor'].sum()
            ticket = (total_v / len(df)) if len(df) > 0 else 0

            m1.metric("Total de Dossiês", f"{len(df)} PACs")
            m2.metric("Volume Total", formatar_br(total_v)) 
            m3.metric("Total Pago", formatar_br(pago))       
            m4.metric("Ticket Médio", formatar_br(ticket))   

            st.divider()
            
            st.subheader("📑 Resumo Financeiro Detalhado")
            df_resumo = df.groupby(['Status', 'Enquadramento'])['Valor'].sum().reset_index()
            
            html_code = """
            <style>
                .tab-ex { width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; }
                .st-row { background-color: #D9E1F2; font-weight: bold; border: 1px solid #8EA9DB; }
                .en-row { background-color: #ffffff; border: 1px solid #D9E1F2; }
                .tab-ex td { padding: 10px; border: 1px solid #D9E1F2; }
                .val { text-align: right; }
            </style>
            <table class='tab-ex'>
            """
            for status in sorted(df_resumo['Status'].unique()):
                subtotal = df_resumo[df_resumo['Status'] == status]['Valor'].sum()
                html_code += f"<tr class='st-row'><td>{status}</td><td class='val'>{formatar_br(subtotal)}</td></tr>"
                for _, row in df_resumo[df_resumo['Status'] == status].iterrows():
                    html_code += f"<tr class='en-row'><td style='padding-left:40px'>{row['Enquadramento']}</td><td class='val'>{formatar_br(row['Valor'])}</td></tr>"
            
            html_code += f"<tr style='background-color:#f0f0f0; font-weight:bold'><td>TOTAL GERAL</td><td class='val'>{formatar_br(total_v)}</td></tr></table>"
            st.markdown(html_code, unsafe_allow_html=True)

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                df_mes = df.groupby('MÊS').size().reset_index(name='Qtd')
                st.plotly_chart(px.line(df_mes, x='MÊS', y='Qtd', title="📈 Qtd de PACs por Mês"), use_container_width=True)
            with c2:
                st.plotly_chart(px.pie(df, names='Enquadramento', hole=0.5, title="🎯 Mix Enquadramento"), use_container_width=True)

        with tab_carteira:
            st.title("📋 Gestão da Carteira")
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1: s_sel = st.selectbox("Filtrar Status", ["Todos"] + sorted(df['Status'].unique().tolist()))
            with col_f2: e_sel = st.selectbox("Filtrar Enquadramento", ["Todos"] + sorted(df['Enquadramento'].unique().tolist()))
            with col_f3: busca = st.text_input("🔍 Buscar Comprador")

            df_v = df.copy()
            if s_sel != "Todos": df_v = df_v[df_v['Status'] == s_sel]
            if e_sel != "Todos": df_v = df_v[df_v['Enquadramento'] == e_sel]
            if busca: df_v = df_v[df_v['Nome do Comprador'].str.contains(busca, case=False)]

            st.divider()
            h = st.columns([1, 1.5, 1, 1, 1, 1, 1, 0.5])
            for col, t in zip(h, ["**Data**", "**Comprador**", "**CPF**", "**Imóvel**", "**Valor**", "**Imobiliária**", "**Status**", " "]): col.write(t)

            with st.container(height=500):
                for i, r in df_v.iterrows():
                    c = st.columns([1, 1.5, 1, 1, 1, 1, 1, 0.5])
                    c[0].write(r.get('DATA_EXIBIR', ''))
                    c[1].write(r.get('Nome do Comprador', ''))
                    c[2].write(r.get('CPF', ''))
                    c[3].write(r.get('Imóvel', ''))
                    c[4].write(formatar_br(r.get('Valor', 0))) 
                    c[5].write(r.get('Imobiliária', ''))
                    c[6].write(r.get('Status', ''))
                    if c[7].button("🗑️", key=f"d_{i}"): st.warning("Exclua na planilha.")

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer) as w: df_v.to_excel(w, index=False)
            st.download_button("📥 Exportar Excel", buffer.getvalue(), "base.xlsx", use_container_width=True)
