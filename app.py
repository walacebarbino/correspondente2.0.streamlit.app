import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests
import base64

# --- 1. CONFIGURAÇÕES APROVADAS ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

# Link original que você forneceu
LINK_ONEDRIVE = "https://1drv.ms/x/c/348d5d4bf85c1dbc/IQABx7R7JVxrQ4FFlg_8TgrhATyuhRja86cSTgU-47UwQfI?e=jhiCze"

def criar_link_direto(url):
    try:
        # Este método transforma qualquer link do OneDrive em um link de dados puro
        base64_enqueue = base64.b64encode(url.encode("ascii")).decode("ascii")
        base64_enqueue = base64_enqueue.replace("/", "_").replace("+", "-").rstrip("=")
        return f"https://api.onedrive.com/v1.0/shares/u!{base64_enqueue}/root/content"
    except:
        return url

@st.cache_data(ttl=10)
def carregar_dados():
    try:
        direto = criar_link_direto(LINK_ONEDRIVE)
        response = requests.get(direto, timeout=20)
        # Lê a planilha com as colunas reais: DATA, Nome do Comprador, Enquadramento, etc.
        df = pd.read_excel(io.BytesIO(response.content))
        
        # 4º item: Corrigir padrão da data para dd/mm/aaaa
        if 'DATA' in df.columns:
            df['DATA'] = pd.to_datetime(df['DATA']).dt.strftime('%d/%m/%Y')
        return df
    except:
        return pd.DataFrame()

df = carregar_dados()

# --- 2. BARRA LATERAL (CONFIGURAÇÃO ORIGINAL APROVADA) ---
st.sidebar.header("📥 Gestão de Dados")
with st.sidebar.form("form_cadastro"):
    st.subheader("Novo Cadastro Manual")
    # Atenção às colunas de entrada aprovadas
    f_data = st.date_input("DATA", datetime.now(), format="DD/MM/YYYY")
    f_nome = st.text_input("Nome do Comprador")
    f_cpf = st.text_input("CPF")
    f_imovel = st.text_input("Nome do Imóvel / Construtora")
    f_valor = st.number_input("Valor (R$)", min_value=0.0)
    f_imobiliaria = st.text_input("Imobiliária")
    f_enquadramento = st.selectbox("Enquadramento", ["SBPE", "MCMV", "FGTS", "Outros"])
    f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
    
    if st.form_submit_button("Cadastrar"):
        st.info("Dado recebido! Adicione-o na sua planilha do OneDrive para atualizar o BI.")

# --- 3. DASHBOARD DE BI ---
st.title("📊 BI e Gestão de Fluxo - Carteira 2026")

if not df.empty:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    m2.metric("Inconformidades", len(df[df['Status'] == 'Inconformidade']) if 'Status' in df else 0)
    m3.metric("Processos Pagos", len(df[df['Status'] == 'Pago']) if 'Status' in df else 0)
    
    df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0)
    m4.metric("Volume Total", f"R$ {df['Valor (R$)'].sum():,.2f}")

    # --- 4. GESTÃO DA CARTEIRA ---
    st.divider()
    st.subheader("📋 Gestão da Carteira")
    
    # Colunas ajustadas para incluir o Enquadramento
    cols_t = st.columns([1.5, 1, 1, 1, 1, 0.8, 0.5])
    headers = ["**Comprador**", "**Status**", "**Enquadramento**", "**Imobiliária**", "**Valor**", "**Data**", "**🗑️**"]
    for col, text in zip(cols_t, headers):
        col.write(text)

    for index, row in df.iterrows():
        c = st.columns([1.5, 1, 1, 1, 1, 0.8, 0.5])
        c[0].write(row.get('Nome do Comprador', '---'))
        c[1].write(row.get('Status', '---'))
        c[2].write(row.get('Enquadramento', '---'))
        c[3].write(row.get('Imobiliária', '---'))
        c[4].write(f"R$ {row.get('Valor (R$)', 0):,.2f}")
        c[5].write(str(row.get('DATA', '---')))
        if c[6].button("🗑️", key=f"del_{index}"):
            st.warning("Exclua no Excel para remover.")
else:
    # Aviso de erro caso a conexão ainda falhe
    st.error("❌ Erro de Conexão: O sistema não conseguiu acessar o OneDrive automaticamente.")
    st.info("Verifique se o seu arquivo requirements.txt contém: streamlit, pandas, plotly, openpyxl, requests.")
