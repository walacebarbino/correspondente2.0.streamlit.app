import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import io

# --- 1. FUNÇÃO DE LOGIN E LOGOUT (REGRA 1) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if st.session_state["password_correct"]:
        return True

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

    # --- 2. CONEXÃO ---
    conn = st.connection("gsheets", type=GSheetsConnection)
    URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1n6529TSBqYhwqAq-ZwVleV0b9q0p38PSPT4eU1z-uNc/edit"

    df = conn.read(spreadsheet=URL_PLANILHA, ttl=0).dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]

    if not df.empty:
        df['DATA_DT'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True, errors='coerce')
        df['DATA_EXIBIR'] = df['DATA_DT'].dt.strftime('%d/%m/%Y')
        df = df.sort_values('DATA_DT', ascending=False)
        df['MÊS_ANO'] = df['DATA_DT'].dt.strftime('%m/%Y')
        df.iloc[:, 4] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)

    # --- SIDEBAR (LOGO, BOTÃO SAIR E CADASTRO) ---
    try: 
        st.sidebar.image("parceria.JPG", use_container_width=True)
        # BOTÃO SAIR ABAIXO DA LOGO (PEDIDO 3)
        if st.sidebar.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state["password_correct"] = False
            st.rerun()
    except: pass

    with st.sidebar:
        st.divider()
        st.header("📥 Gestão de Dados")
        with st.form("form_cadastro", clear_on_submit=True):
            f_data = st.date_input("DATA", datetime.now(), format="DD/MM/YYYY")
            f_nome = st.text_input("Nome do Comprador")
            f_cpf = st.text_input("CPF")
            f_imovel = st.text_input("Imóvel / Construtora")
            f_valor = st.number_input("Valor (R$)", min_value=0.0)
            f_imobiliaria = st.text_input("Imobiliária")
            f_enquadramento = st.selectbox("Enquadramento", ["SBPE", "MCMV", "FGTS", "Outros"])
            f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
            
            if st.form_submit_button("Cadastrar na Planilha"):
                nova_linha = pd.DataFrame([[f_data.strftime("%d/%m/%Y"), f_nome, f_cpf, f_imovel, f_valor, f_imobiliaria, f_enquadramento, f_status]], columns=df.columns[:8])
                conn.update(spreadsheet=URL_PLANILHA, data=pd.concat([df[df.columns[:8]], nova_linha], ignore_index=True))
                st.cache_data.clear()
                st.rerun()

    tab_bi, tab_carteira = st.tabs(["📊 Dashboard Profissional", "📋 Carteira de Clientes"])

    if not df.empty:
        with tab_bi:
            st.title("📊 BI e Performance")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total de Dossiês", f"{len(df)} PACs")
            m2.metric("Volume Total", formatar_br(df.iloc[:, 4].sum()))
            m3.metric("Total Pago", formatar_br(df[df.iloc[:, 7] == 'Pago'].iloc[:, 4].sum()))
            m4.metric("Ticket Médio", formatar_br(df.iloc[:, 4].mean()))

            st.divider()
            g1, g2 = st.columns(2)
            with g1:
                st.subheader("📈 Volume por Enquadramento")
                st.plotly_chart(px.bar(df, x='MÊS_ANO', y=df.columns[4], color=df.columns[6], barmode='group'), use_container_width=True)
            with g2:
                st.subheader("📊 Volume por Status")
                st.plotly_chart(px.bar(df, x='MÊS_ANO', y=df.columns[4], color=df.columns[7], barmode='group'), use_container_width=True)

            st.subheader("📑 Resumo Detalhado")
            df_resumo = df.groupby([df.columns[7], df.columns[6]])[df.columns[4]].sum().reset_index()
            html_code = """<style>.tab-ex{width:100%;border-collapse:collapse;}.st-row{background-color:#D9E1F2;font-weight:bold;}.en-row{background-color:#ffffff;}.tab-ex td{padding:10px;border:1px solid #D9E1F2;}.val{text-align:right;}</style><table class='tab-ex'>"""
            for status in sorted(df_resumo.iloc[:,0].unique()):
                sub_v = df_resumo[df_resumo.iloc[:,0] == status].iloc[:,2].sum()
                html_code += f"<tr class='st-row'><td>{status}</td><td class='val'>{formatar_br(sub_v)}</td></tr>"
                for _, row in df_resumo[df_resumo.iloc[:,0] == status].iterrows():
                    html_code += f"<tr class='en-row'><td style='padding-left:40px'>{row.iloc[1]}</td><td class='val'>{formatar_br(row.iloc[2])}</td></tr>"
            st.markdown(html_code + "</table>", unsafe_allow_html=True)

        with tab_carteira:
            st.title("📋 Gestão da Carteira")
            
            # FILTROS PADRONIZADOS E EM PORTUGUÊS (PEDIDOS 1 E 2)
            c1, c2, c3 = st.columns(3)
            filtro_nome = c1.multiselect("Filtrar por Nome", options=sorted(df.iloc[:, 1].unique()), placeholder="Selecionar nomes...")
            filtro_status = c2.multiselect("Filtrar por Status", options=sorted(df.iloc[:, 7].unique()), placeholder="Selecionar status...")
            filtro_enq = c3.multiselect("Filtrar por Enquadramento", options=sorted(df.iloc[:, 6].unique()), placeholder="Selecionar enquadramento...")

            df_f = df.copy()
            if filtro_nome: df_f = df_f[df_f.iloc[:, 1].isin(filtro_nome)]
            if filtro_status: df_f = df_f[df_f.iloc[:, 7].isin(filtro_status)]
            if filtro_enq: df_f = df_f[df_f.iloc[:, 6].isin(filtro_enq)]

            st.divider()
            h = st.columns([1, 1.5, 1, 1, 1, 1, 1, 0.5])
            for col, t in zip(h, ["**Data**", "**Comprador**", "**CPF**", "**Imóvel**", "**Valor**", "**Imobiliária**", "**Status**", " "]): col.write(t)

            with st.container(height=500):
                for i, r in df_f.iterrows():
                    c = st.columns([1, 1.5, 1, 1, 1, 1, 1, 0.5])
                    c[0].write(r['DATA_EXIBIR'])
                    c[1].write(r.iloc[1])
                    c[2].write(r.iloc[2])
                    c[3].write(r.iloc[3])
                    c[4].write(formatar_br(r.iloc[4]))
                    c[5].write(r.iloc[5])
                    c[6].write(r.iloc[7])
                    if c[7].button("🗑️", key=f"del_{i}"):
                        conn.update(spreadsheet=URL_PLANILHA, data=df.drop(i)[df.columns[:8]])
                        st.cache_data.clear()
                        st.rerun()
            
            # EXPORTAÇÃO COM AJUSTE DE COLUNAS
            st.divider()
            try:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_exp = df_f[df.columns[:8]]
                    df_exp.to_excel(writer, index=False, sheet_name='Carteira')
                    worksheet = writer.sheets['Carteira']
                    for idx, col in enumerate(df_exp.columns):
                        max_len = max(df_exp[col].astype(str).map(len).max(), len(col)) + 2
                        worksheet.set_column(idx, idx, max_len)
                st.download_button("📥 Exportar Carteira Filtrada (Excel)", data=buffer, file_name="base_clientes.xlsx", mime="application/vnd.ms-excel")
            except Exception:
                st.warning("Verifique se 'xlsxwriter' está no requirements.txt e dê 'Reboot' no app.")
