import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests

# --- 1. CONFIGURAÇÕES (Mantendo o que foi aprovado) ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

# Link direto para leitura (ajustado para evitar o erro de conexão)
LINK_ONEDRIVE = "https://onedrive.live.com/download?resid=348D5D4BF85C1DBC%21124&authkey=!AEHHtHslXGtDgUU"

@st.cache_data(ttl=30)
def carregar_dados():
    try:
        # Tenta ler o arquivo Excel da nuvem
        response = requests.get(LINK_ONEDRIVE)
        df = pd.read_excel(io.BytesIO(response.content))
        # Ajusta o padrão da data para dd/mm/aaaa conforme solicitado
        if 'DATA' in df.columns:
            df['DATA'] = pd.to_datetime(df['DATA']).dt.strftime('%d/%m/%Y')
        return df
    except:
        return pd.DataFrame()

df = carregar_dados()

# --- 2. BARRA LATERAL (IDÊNTICA À IMAGEM image_ed2685) ---
st.sidebar.header("📥 Gestão de Dados")
with st.sidebar.form("form_cadastro"):
    st.subheader("Novo Cadastro Manual")
    # Atenção total às colunas de entrada
    f_data = st.date_input("DATA", datetime.now(), format="DD/MM/YYYY")
    f_nome = st.text_input("Nome do Comprador")
    f_cpf = st.text_input("CPF")
    f_imovel = st.text_input("Nome do Imóvel / Construtora")
    f_valor = st.number_input("Valor (R$)", min_value=0.0)
    f_imobiliaria = st.text_input("Imobiliária")
    f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
    
    if st.form_submit_button("Cadastrar"):
        st.info("Dado recebido! Adicione-o na sua planilha do OneDrive para atualizar o BI.")

# --- 3. DASHBOARD E BI (IDÊNTICO ÀS CONFIGURAÇÕES ORIGINAIS) ---
st.title("📊 BI e Gestão de Fluxo - Carteira 2026")

if not df.empty:
    # Métricas de Topo
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    m2.metric("Inconformidades", len(df[df['Status'] == 'Inconformidade']).sum() if 'Status' in df else 0)
    m3.metric("Processos Pagos", len(df[df['Status'] == 'Pago']).sum() if 'Status' in df else 0)
    m4.metric("Volume Total", f"R$ {df['Valor (R$)'].sum():,.2f}" if 'Valor (R$)' in df else "0,00")

    # --- 4. GESTÃO DA CARTEIRA (IDÊNTICO À IMAGEM 1000155553) ---
    st.divider()
    st.subheader("📋 Gestão da Carteira")
    
    # Exatamente como na imagem 1000155553
    for index, row in df.iterrows():
        cols = st.columns([2, 2, 2, 2, 1, 1])
        cols[0].write(f"**{row['Nome do Comprador']}**")
        cols[1].write(row['Status'])
        cols[2].write(row['Imobiliária'])
        cols[3].write(f"R$ {row['Valor (R$)']:,.2f}")
        cols[4].write(row['DATA'])
        if cols[5].button("🗑️", key=f"del_{index}"):
            st.warning("Remova a linha no seu Excel para excluir permanentemente.")
else:
    # Mensagem de erro que você viu na imagem
    st.info("Conectando à nuvem... Se não aparecer nada, verifique se o link do OneDrive está com permissão de 'Qualquer pessoa'.")
