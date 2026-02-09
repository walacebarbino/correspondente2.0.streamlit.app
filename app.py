import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import io

# --- 1. LOGIN E LOGOUT (REGRA 1) ---
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

    # --- 2. CONEXÃO ---
    conn = st.connection("gsheets", type=GSheetsConnection)
    URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1n6529TSBqYhwqAq-ZwVleV0b9q0p38PSPT4eU1z-uNc/edit"

    df = conn.read(spreadsheet=URL_PLANILHA, ttl=0).dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]

    if not df.empty:
        df['DATA_DT'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True, errors='coerce')
        df['DATA_DT'] = df['DATA_DT'].fillna(datetime.now())
        df['DATA_EXIBIR'] = df['DATA_DT'].dt.strftime('%d/%m/%Y')
        df = df.sort_values('DATA_DT', ascending=False)
        df['MÊS_ANO'] = df['DATA_DT'].dt.strftime('%m/%Y')
        df.iloc[:, 4] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)

    # --- SIDEBAR ---
    try: 
        st.sidebar.image("parceria.JPG", use_container_width=True)
        if st.sidebar.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state["password_correct"] = False
            st.rerun()
    except: pass

    with st.sidebar:
        st.divider()
        st.header("📥 Novo Cadastro")
        with st.form("form_cadastro", clear_on_submit=True):
            f_data = st.date_input("DATA", datetime.now(), format="DD/MM/YYYY")
            f_nome = st.text_input("Nome do Comprador")
            f_cpf = st.text_input("CPF")
            f_imovel = st.text_input("Imóvel")
            f_valor = st.number_input("Valor (R$)", min_value=0.0)
            f_imobiliaria = st.text_input("Imobiliária")
            f_enquadramento = st.selectbox("Enquadramento", ["SBPE", "MCMV", "FGTS", "Outros"])
            f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
            
            if st.form_submit_button("Salvar Cadastro"):
                nova_linha = pd.DataFrame([[f_data.strftime("%d/%m/%Y"), f_nome, f_cpf, f_imovel, f_valor, f_imobiliaria, f_enquadramento, f_status]], columns=df.columns[:8])
                conn.update(spreadsheet=URL_PLANILHA, data=pd.concat([df[df.columns[:8]], nova_linha], ignore_index=True))
                st.cache_data.clear()
                st.rerun()

    tab_bi, tab_carteira = st.tabs(["📊 Dashboard Profissional", "📋 Carteira de Clientes"])

    if not df.empty:
        # --- ABA 1: BI ORIGINAL (RESTAURADO - REGRA 1) ---
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

            # A TABELA AZUL QUE EU TINHA REMOVIDO POR ERRO:
            st.subheader("📑 Resumo Detalhado (Excel Style)")
            df_resumo = df.groupby([df.columns[7], df.columns[6]])[df.columns[4]].sum().reset_index()
            html_code = """<style>.tab-ex{width:100%;border-collapse:collapse;}.st-row{background-color:#D9E1F2;font-weight:bold;}.en-row{background-color:#ffffff;}.tab-ex td{padding:10px;border:1px solid #D9E1F2;}.val{text-align:right;}</style><table class='tab-ex'>"""
            for status in sorted(df_resumo.iloc[:,0].unique()):
                sub_v = df_resumo[df_resumo.iloc[:,0] == status].iloc[:,2].sum()
                html_code += f"<tr class='st-row'><td>{status}</td><td class='val'>{formatar_br(sub_v)}</td></tr>"
                for _, row in df_resumo[df_resumo.iloc[:,0] == status].iterrows():
                    html_code += f"<tr class='en-row'><td style='padding-left:40px'>{row.iloc[1]}</td><td class='val'>{formatar_br(row.iloc[2])}</td></tr>"
            st.markdown(html_code + "</table>", unsafe_allow_html=True)

        # --- ABA 2: CARTEIRA (COM EDITAR STATUS E DIAS) ---
        with tab_carteira:
            st.title("📋 Gestão da Carteira")
            c1, c2, c3 = st.columns(3)
            f_n = c1.multiselect("Filtrar Nome", options=sorted(df.iloc[:, 1].unique()), placeholder="Selecionar...")
            f_s = c2.multiselect("Filtrar Status", options=sorted(df.iloc[:, 7].unique()), placeholder="Selecionar...")
            f_e = c3.multiselect("Filtrar Enquadramento", options=sorted(df.iloc[:, 6].unique()), placeholder="Selecionar...")

            df_f = df.copy()
            if f_n: df_f = df_f[df_f.iloc[:, 1].isin(f_n)]
            if f_s: df_f = df_f[df_f.iloc[:, 7].isin(f_s)]
            if f_e: df_f = df_f[df_f.iloc[:, 6].isin(f_e)]

            st.divider()
            h = st.columns([1, 1.5, 1, 1, 1, 1, 1.2, 0.6, 0.4])
            for col, t in zip(h, ["**Data**", "**Comprador**", "**CPF**", "**Imóvel**", "**Valor**", "**Imobiliária**", "**Status**", "**Dias**", " "]): col.write(t)

            with st.container(height=500):
                for i, r in df_f.iterrows():
                    c = st.columns([1, 1.5, 1, 1, 1, 1, 1.2, 0.6, 0.4])
                    c[0].write(r['DATA_EXIBIR'])
                    c[1].write(r.iloc[1])
                    c[2].write(r.iloc[2])
                    c[3].write(r.iloc[3])
                    c[4].write(formatar_br(r.iloc[4]))
                    c[5].write(r.iloc[5])
                    
                    lista_status = ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"]
                    idx_atual = lista_status.index(r.iloc[7]) if r.iloc[7] in lista_status else 0
                    novo_s = c[6].selectbox(" ", lista_status, index=idx_atual, key=f"edit_{i}", label_visibility="collapsed")
                    if novo_s != r.iloc[7]:
                        df.at[i, df.columns[7]] = novo_s
                        conn.update(spreadsheet=URL_PLANILHA, data=df[df.columns[:8]])
                        st.cache_data.clear()
                        st.rerun()

                    dias = (datetime.now() - r['DATA_DT']).days
                    c[7].write(f"⏱️ {dias}d")
                    if c[8].button("🗑️", key=f"del_{i}"):
                        conn.update(spreadsheet=URL_PLANILHA, data=df.drop(i)[df.columns[:8]])
                        st.cache_data.clear()
                        st.rerun()
            
            st.divider()
            try:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_f[df.columns[:8]].to_excel(writer, index=False, sheet_name='Carteira')
                    for idx, col in enumerate(df_f[df.columns[:8]].columns):
                        writer.sheets['Carteira'].set_column(idx, idx, 20)
                st.download_button("📥 Exportar Excel", data=buffer, file_name="base.xlsx")
            except: st.warning("Erro no módulo de exportação.")
