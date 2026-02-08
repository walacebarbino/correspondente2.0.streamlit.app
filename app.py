import streamlit as st
import pandas as pd
from datetime import datetime
import io
import requests

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

# Link do Google Drive convertido para Download Direto
LINK_PLANILHA = "https://docs.google.com/spreadsheets/d/1n6529TSBqYhwqAq-ZwVleV0b9q0p38PSPT4eU1z-uNc/export?format=xlsx"

@st.cache_data(ttl=10)
def carregar_dados():
    try:
        # O Google Drive entrega o arquivo instantaneamente com este link
        response = requests.get(LINK_PLANILHA, timeout=20)
        df = pd.read_excel(io.BytesIO(response.content))
        
        # 4º item: Corrigir padrão da data para dd/mm/aaaa
        if 'DATA' in df.columns:
            df['DATA'] = pd.to_datetime(df['DATA']).dt.strftime('%d/%m/%Y')
        return df
    except Exception as e:
        return pd.DataFrame()

df = carregar_dados()

# --- BARRA LATERAL (IDÊNTICA ÀS CONFIGURAÇÕES APROVADAS) ---
st.sidebar.header("📥 Gestão de Dados")
with st.sidebar.form("form_cadastro"):
    st.subheader("Novo Cadastro Manual")
    f_data = st.date_input("DATA", datetime.now(), format="DD/MM/YYYY")
    f_nome = st.text_input("Nome do Comprador")
    f_cpf = st.text_input("CPF")
    f_imovel = st.text_input("Nome do Imóvel / Construtora")
    f_valor = st.number_input("Valor (R$)", min_value=0.0)
    f_imobiliaria = st.text_input("Imobiliária")
    # Mantendo a coluna Enquadramento solicitada
    f_enquadramento = st.selectbox("Enquadramento", ["SBPE", "MCMV", "FGTS", "Outros"])
    f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
    
    if st.form_submit_button("Cadastrar"):
        st.info("Para salvar, adicione os dados na sua planilha do Google Drive.")

# --- DASHBOARD DE BI ---
st.title("📊 BI e Gestão de Fluxo - Carteira 2026")

if not df.empty:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    # Filtros baseados no Status da sua planilha
    m2.metric("Inconformidades", len(df[df['Status'] == 'Inconformidade']) if 'Status' in df else 0)
    m3.metric("Processos Pagos", len(df[df['Status'] == 'Pago']) if 'Status' in df else 0)
    
    df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0)
    m4.metric("Volume Total", f"R$ {df['Valor (R$)'].sum():,.2f}")

    # --- GESTÃO DA CARTEIRA ---
    st.divider()
    st.subheader("📋 Gestão da Carteira")
    
    # Grid organizado com as colunas aprovadas
    cols_t = st.columns([1.5, 1, 1, 1, 1, 0.8, 0.5])
    titulos = ["**Comprador**", "**Status**", "**Enquadramento**", "**Imobiliária**", "**Valor**", "**Data**", "**🗑️**"]
    for col, texto in zip(cols_t, titulos):
        col.write(texto)

    for index, row in df.iterrows():
        c = st.columns([1.5, 1, 1, 1, 1, 0.8, 0.5])
        c[0].write(row.get('Nome do Comprador', '---'))
        c[1].write(row.get('Status', '---'))
        c[2].write(row.get('Enquadramento', '---'))
        c[3].write(row.get('Imobiliária', '---'))
        c[4].write(f"R$ {row.get('Valor (R$)', 0):,.2f}")
        c[5].write(str(row.get('DATA', '---')))
        if c[6].button("🗑️", key=f"del_{index}"):
            st.warning("Exclua na planilha para remover do BI.")
else:
    # Aviso de segurança caso o link do Google falhe
    st.error("❌ Erro de Conexão: Não foi possível acessar a planilha do Google Drive.")
    st.info("⚠️ Verifique se o seu arquivo requirements.txt no GitHub contém as 6 linhas necessárias.")
