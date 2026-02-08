import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests

# --- 1. CONFIGURAÇÕES (Mantendo o aprovado) ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

# LINK CORRIGIDO PARA DOWNLOAD DIRETO (Elimina o erro de conexão)
LINK_ONEDRIVE = "https://onedrive.live.com/download?resid=348D5D4BF85C1DBC!124&authkey=!AEHHtHslXGtDgUU"

@st.cache_data(ttl=10)
def carregar_dados():
    try:
        response = requests.get(LINK_ONEDRIVE, timeout=10)
        # 4º item: Corrigir padrão da data para dd/mm/aaaa
        df = pd.read_excel(io.BytesIO(response.content))
        if 'DATA' in df.columns:
            df['DATA'] = pd.to_datetime(df['DATA']).dt.strftime('%d/%m/%Y')
        return df
    except Exception as e:
        return pd.DataFrame()

df = carregar_dados()

# --- 2. BARRA LATERAL (IDÊNTICA ÀS CONFIGURAÇÕES APROVADAS) ---
st.sidebar.header("📥 Gestão de Dados")
with st.sidebar.form("form_cadastro"):
    st.subheader("Novo Cadastro Manual")
    # 3º item: Atenção total às colunas de entrada
    f_data = st.date_input("DATA", datetime.now(), format="DD/MM/YYYY")
    f_nome = st.text_input("Nome do Comprador")
    f_cpf = st.text_input("CPF")
    f_imovel = st.text_input("Nome do Imóvel / Construtora")
    f_valor = st.number_input("Valor (R$)", min_value=0.0)
    f_imobiliaria = st.text_input("Imobiliária")
    # Item adicionado: Enquadramento
    f_enquadramento = st.selectbox("Enquadramento", ["SBPE", "MCMV", "FGTS", "Outros"])
    f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
    
    if st.form_submit_button("Cadastrar"):
        st.info("Para salvar, adicione os dados na planilha OneDrive e o BI atualizará.")

# --- 3. DASHBOARD DE BI ---
st.title("📊 BI e Gestão de Fluxo - Carteira 2026")

if not df.empty:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    # Filtros baseados no Status da planilha
    m2.metric("Inconformidades", len(df[df['Status'] == 'Inconformidade']))
    m3.metric("Processos Pagos", len(df[df['Status'] == 'Pago']))
    
    df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0)
    m4.metric("Volume Total", f"R$ {df['Valor (R$)'].sum():,.2f}")

    # --- 4. GESTÃO DA CARTEIRA (CONFORME 1000155553 COM ENQUADRAMENTO) ---
    st.divider()
    st.subheader("📋 Gestão da Carteira")
    
    # Cabeçalho organizado para as colunas aprovadas
    cols_t = st.columns([1.5, 1, 1, 1, 1.2, 0.8, 0.5])
    cols_t[0].write("**Comprador**")
    cols_t[1].write("**Status**")
    cols_t[2].write("**Enquadramento**")
    cols_t[3].write("**Imobiliária**")
    cols_t[4].write("**Valor**")
    cols_t[5].write("**Data**")
    cols_t[6].write("**🗑️**")

    for index, row in df.iterrows():
        c = st.columns([1.5, 1, 1, 1, 1.2, 0.8, 0.5])
        c[0].write(row.get('Nome do Comprador', '---'))
        c[1].write(row.get('Status', '---'))
        c[2].write(row.get('Enquadramento', '---'))
        c[3].write(row.get('Imobiliária', '---'))
        c[4].write(f"R$ {row.get('Valor (R$)', 0):,.2f}")
        c[5].write(str(row.get('DATA', '---')))
        if c[6].button("🗑️", key=f"del_{index}"):
            st.warning("Exclua a linha no seu Excel para remover do BI.")
else:
    # 1º item: Mensagem se o link ainda falhar
    st.error("❌ Erro de Conexão: O sistema não conseguiu acessar o OneDrive automaticamente.")
    st.markdown("1. Verifique se o arquivo está na pasta **CORRESPONDENTE2.0**.\n2. No OneDrive, o arquivo deve estar como **'Qualquer pessoa com o link pode exibir'**.")
