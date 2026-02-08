import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests

# --- 1. CONFIGURAÇÕES APROVADAS ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

# Link de Download Direto (Ajustado para contornar o bloqueio de conexão)
LINK_ONEDRIVE = "https://1drv.ms/x/c/348d5d4bf85c1dbc/IQABx7R7JVxrQ4FFlg_8TgrhATyuhRja86cSTgU-47UwQfI?e=jhiCze"

@st.cache_data(ttl=10)
def carregar_dados():
    try:
        # Uso de Headers para simular um navegador e evitar o erro de conexão
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(LINK_ONEDRIVE, headers=headers, timeout=15)
        df = pd.read_excel(io.BytesIO(response.content))
        
        # 4º item: Data no padrão dd/mm/aaaa conforme solicitado
        if 'DATA' in df.columns:
            df['DATA'] = pd.to_datetime(df['DATA']).dt.strftime('%d/%m/%Y')
        return df
    except:
        return pd.DataFrame()

df = carregar_dados()

# --- 2. BARRA LATERAL (IDÊNTICA ÀS CONFIGURAÇÕES APROVADAS) ---
st.sidebar.header("📥 Gestão de Dados")
with st.sidebar.form("form_cadastro"):
    st.subheader("Novo Cadastro Manual")
    # 3º item: Colunas de entrada idênticas à sua planilha
    f_data = st.date_input("DATA", datetime.now(), format="DD/MM/YYYY")
    f_nome = st.text_input("Nome do Comprador")
    f_cpf = st.text_input("CPF")
    f_imovel = st.text_input("Nome do Imóvel / Construtora")
    f_valor = st.number_input("Valor (R$)", min_value=0.0)
    f_imobiliaria = st.text_input("Imobiliária")
    f_enquadramento = st.selectbox("Enquadramento", ["SBPE", "MCMV", "FGTS", "Outros"]) # Adicionado conforme solicitado
    f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
    
    if st.form_submit_button("Cadastrar"):
        st.info("Para salvar, adicione os dados no seu Excel do OneDrive.")

# --- 3. DASHBOARD DE BI ---
st.title("📊 BI e Gestão de Fluxo - Carteira 2026")

if not df.empty:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    # Filtros baseados na sua planilha real
    m2.metric("Inconformidades", len(df[df['Status'] == 'Inconformidade']))
    m3.metric("Processos Pagos", len(df[df['Status'] == 'Pago']))
    
    df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0)
    m4.metric("Volume Total", f"R$ {df['Valor (R$)'].sum():,.2f}")

    # --- 4. GESTÃO DA CARTEIRA (IDÊNTICA À IMAGEM 1000155553) ---
    st.divider()
    st.subheader("📋 Gestão da Carteira")
    
    # Colunas formatadas para incluir o Enquadramento
    cols_t = st.columns([1.5, 1, 1, 1, 1, 0.8, 0.5])
    cols_t[0].write("**Comprador**")
    cols_t[1].write("**Status**")
    cols_t[2].write("**Enquadramento**")
    cols_t[3].write("**Imobiliária**")
    cols_t[4].write("**Valor**")
    cols_t[5].write("**Data**")
    cols_t[6].write("**🗑️**")

    for index, row in df.iterrows():
        c = st.columns([1.5, 1, 1, 1, 1, 0.8, 0.5])
        c[0].write(row.get('Nome do Comprador', '---'))
        c[1].write(row.get('Status', '---'))
        c[2].write(row.get('Enquadramento', '---'))
        c[3].write(row.get('Imobiliária', '---'))
        c[4].write(f"R$ {row.get('Valor (R$)', 0):,.2f}")
        c[5].write(str(row.get('DATA', '---')))
        if c[6].button("🗑️", key=f"del_{index}"):
            st.warning("Exclua no Excel para remover do BI.")
else:
    # Aviso de erro original
    st.error("❌ Erro de Conexão: O sistema não conseguiu acessar o OneDrive automaticamente.")
    st.info("Verifique se o seu arquivo requirements.txt contém: streamlit, pandas, plotly, openpyxl, requests.")
