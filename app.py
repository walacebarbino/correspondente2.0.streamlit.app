import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests

# --- 1. CONFIGURAÇÕES (Mantendo o aprovado) ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

# Link ajustado para download direto do OneDrive
LINK_ONEDRIVE = "https://onedrive.live.com/download?resid=348D5D4BF85C1DBC%21124&authkey=!AEHHtHslXGtDgUU"

@st.cache_data(ttl=30)
def carregar_dados():
    try:
        response = requests.get(LINK_ONEDRIVE)
        df = pd.read_excel(io.BytesIO(response.content))
        
        # 4º item: Corrigir padrão da data para dd/mm/aaaa
        if 'DATA' in df.columns:
            df['DATA'] = pd.to_datetime(df['DATA']).dt.strftime('%d/%m/%Y')
        return df
    except:
        return pd.DataFrame()

df = carregar_dados()

# --- 2. BARRA LATERAL (3º item: Atenção total às colunas de entrada) ---
st.sidebar.header("📥 Gestão de Dados")
with st.sidebar.form("form_cadastro"):
    st.subheader("Novo Cadastro Manual")
    f_data = st.date_input("DATA", datetime.now(), format="DD/MM/YYYY")
    f_nome = st.text_input("Nome do Comprador")
    f_cpf = st.text_input("CPF")
    f_imovel = st.text_input("Nome do Imóvel / Construtora")
    f_valor = st.number_input("Valor (R$)", min_value=0.0)
    f_imobiliaria = st.text_input("Imobiliária")
    # Adicionado item: Enquadramento
    f_enquadramento = st.selectbox("Enquadramento", ["SBPE", "MCMV", "FGTS", "Outros"])
    f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
    
    if st.form_submit_button("Cadastrar"):
        st.info("Dado recebido! Adicione-o na sua planilha do OneDrive para atualizar o BI.")

# --- 3. DASHBOARD E BI ---
st.title("📊 BI e Gestão de Fluxo - Carteira 2026")

if not df.empty:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    m2.metric("Inconformidades", len(df[df['Status'] == 'Inconformidade']) if 'Status' in df else 0)
    m3.metric("Processos Pagos", len(df[df['Status'] == 'Pago']) if 'Status' in df else 0)
    m4.metric("Volume Total", f"R$ {df['Valor (R$)'].sum():,.2f}" if 'Valor (R$)' in df else "0,00")

    # --- 4. GESTÃO DA CARTEIRA (Com coluna Enquadramento incluída) ---
    st.divider()
    st.subheader("📋 Gestão da Carteira")
    
    # Cabeçalho da tabela para melhor visualização
    cols_tit = st.columns([1.5, 1.5, 1.5, 1.5, 1.5, 1, 0.5])
    cols_tit[0].write("**Comprador**")
    cols_tit[1].write("**Status**")
    cols_tit[2].write("**Enquadramento**")
    cols_tit[3].write("**Imobiliária**")
    cols_tit[4].write("**Valor**")
    cols_tit[5].write("**Data**")
    cols_tit[6].write("**Excluir**")

    for index, row in df.iterrows():
        cols = st.columns([1.5, 1.5, 1.5, 1.5, 1.5, 1, 0.5])
        cols[0].write(row.get('Nome do Comprador', '---'))
        cols[1].write(row.get('Status', '---'))
        cols[2].write(row.get('Enquadramento', '---')) # Coluna Enquadramento
        cols[3].write(row.get('Imobiliária', '---'))
        valor = row.get('Valor (R$)', 0)
        cols[4].write(f"R$ {valor:,.2f}")
        cols[5].write(str(row.get('DATA', '---')))
        if cols[6].button("🗑️", key=f"del_{index}"):
            st.warning("Remova a linha no seu Excel para excluir.")
else:
    # Resposta ao 1º item: Se o erro persistir, o sistema mostrará este aviso
    st.error("❌ Erro de Conexão: O sistema não conseguiu acessar o OneDrive automaticamente.")
    st.info("1. Verifique se o link no código é o de 'Download Direto'.\n2. Certifique-se de que a planilha tem a coluna 'Enquadramento' criada.")
