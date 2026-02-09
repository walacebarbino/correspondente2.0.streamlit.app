import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. FUNÇÃO DE LOGIN (REGRA 1) ---
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
    try: 
        v = float(valor)
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

if check_password():
    st.set_page_config(page_title="Gestão Correspondente 2026", layout="wide", page_icon="📊")

    # --- 2. CONEXÃO REAL ---
    conn = st.connection("gsheets", type=GSheetsConnection)
    URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1n6529TSBqYhwqAq-ZwVleV0b9q0p38PSPT4eU1z-uNc/edit"

    # Lendo os dados sem cache (ttl=0)
    df = conn.read(spreadsheet=URL_PLANILHA, ttl=0).dropna(how="all")
    # Limpando nomes de colunas para evitar erros de espaço
    df.columns = [str(c).strip() for c in df.columns]

    # --- SIDEBAR E LOGO (REGRA 1) ---
    try: st.sidebar.image("parceria.JPG", use_container_width=True)
    except: pass

    with st.sidebar:
        st.divider()
        st.header("📥 Gestão de Dados")
        with st.form("form_cadastro", clear_on_submit=True):
            f_data = st.date_input("DATA", datetime.now())
            f_nome = st.text_input("Nome do Comprador")
            f_cpf = st.text_input("CPF")
            f_imovel = st.text_input("Nome do Imóvel / Construtora")
            f_valor = st.number_input("Valor (R$)", min_value=0.0)
            f_imobiliaria = st.text_input("Imobiliária")
            f_enquadramento = st.selectbox("Enquadramento", ["SBPE", "MCMV", "FGTS", "Outros"])
            f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
            
            if st.form_submit_button("Cadastrar na Planilha"):
                # Criando nova linha mapeada exatamente nas colunas existentes
                nova_linha = pd.DataFrame([{
                    df.columns[0]: f_data.strftime("%d/%m/%Y"),
                    df.columns[1]: f_nome,
                    df.columns[2]: f_cpf,
                    df.columns[3]: f_imovel,
                    df.columns[4]: f_valor,
                    df.columns[5]: f_imobiliaria,
                    df.columns[6]: f_enquadramento,
                    df.columns[7]: f_status
                }])
                
                df_updated = pd.concat([df, nova_linha], ignore_index=True)
                conn.update(spreadsheet=URL_PLANILHA, data=df_updated)
                st.cache_data.clear()
                st.success("✅ Gravado com sucesso!")
                st.rerun()

    # --- ABAS ---
    tab_bi, tab_carteira = st.tabs(["📊 Dashboard Profissional", "📋 Carteira de Clientes"])

    with tab_bi:
        st.title("📊 BI e Performance")
        if not df.empty:
            m1, m2, m3 = st.columns(3)
            # Usando posição da coluna (iloc) para não depender de nomes exatos
            total_valor = pd.to_numeric(df.iloc[:, 4], errors='coerce').sum()
            total_pago = pd.to_numeric(df[df.iloc[:, 7] == 'Pago'].iloc[:, 4], errors='coerce').sum()

            m1.metric("Total de Dossiês", f"{len(df)} PACs")
            m2.metric("Volume Total", formatar_br(total_valor))
            m3.metric("Total Pago", formatar_br(total_pago))

            st.subheader("📑 Resumo Financeiro Detalhado")
            # Tabela Estilo Excel (REGRA 1)
            df_resumo = df.groupby([df.columns[7], df.columns[6]])[df.columns[4]].sum().reset_index()
            df_resumo.columns = ['Status', 'Enquadramento', 'Valor']
            
            html_code = "<style>.tab-ex{width:100%;border-collapse:collapse;}.st-row{background-color:#D9E1F2;font-weight:bold;}.en-row{background-color:#ffffff;}.tab-ex td{padding:10px;border:1px solid #D9E1F2;}.val{text-align:right;}</style><table class='tab-ex'>"
            for status in sorted(df_resumo['Status'].unique()):
                sub_v = df_resumo[df_resumo['Status'] == status]['Valor'].sum()
                html_code += f"<tr class='st-row'><td>{status}</td><td class='val'>{formatar_br(sub_v)}</td></tr>"
                for _, row in df_resumo[df_resumo['Status'] == status].iterrows():
                    html_code += f"<tr class='en-row'><td style='padding-left:40px'>{row['Enquadramento']}</td><td class='val'>{formatar_br(row['Valor'])}</td></tr>"
            st.markdown(html_code + "</table>", unsafe_allow_html=True)

    with tab_carteira:
        st.title("📋 Gestão da Carteira")
        # ROLAGEM AMARELA (REGRA 1)
        with st.container(height=500): 
            for i, r in df.iterrows():
                c = st.columns([3, 2, 1, 0.5])
                c[0].write(f"**{r.iloc[1]}**")
                c[1].write(f"{r.iloc[7]}")
                c[2].write(formatar_br(r.iloc[4]))
                
                if c[3].button("🗑️", key=f"del_{i}"):
                    df_dropped = df.drop(i)
                    conn.update(spreadsheet=URL_PLANILHA, data=df_dropped)
                    st.cache_data.clear()
                    st.rerun()
