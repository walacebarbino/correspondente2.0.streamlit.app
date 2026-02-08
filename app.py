import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests
import base64

# --- 1. CONFIGURAÇÕES ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

# Link original fornecido por você
LINK_ONEDRIVE = "https://1drv.ms/x/c/348d5d4bf85c1dbc/IQABx7R7JVxrQ4FFlg_8TgrhATyuhRja86cSTgU-47UwQfI?e=fn9Ig9"

def obter_download_direto(url):
    try:
        # Método oficial para converter link de compartilhamento em download para o Python
        base64_url = base64.b64encode(url.encode("ascii")).decode("ascii").replace("/", "_").replace("+", "-").rstrip("=")
        return f"https://api.onedrive.com/v1.0/shares/u!{base64_url}/root/content"
    except:
        return url

@st.cache_data(ttl=60)
def carregar_dados():
    try:
        url_direta = obter_download_direto(LINK_ONEDRIVE)
        response = requests.get(url_direta)
        # Lê a planilha exatamente com os nomes que você criou: DATA, Nome do Comprador, CPF, etc.
        df = pd.read_excel(io.BytesIO(response.content))
        return df
    except:
        return pd.DataFrame()

# Carregamento dos dados
df = carregar_dados()

# --- 2. INTERFACE LATERAL (CONFIGURAÇÃO ORIGINAL APROVADA - SEM MUDANÇAS) ---
st.sidebar.header("📥 Gestão de Dados")
with st.sidebar.form("form_cadastro"):
    st.subheader("Novo Cadastro Manual")
    f_nome = st.text_input("Nome do Comprador")
    f_cpf = st.text_input("CPF")
    f_valor = st.number_input("Valor (R$)", min_value=0.0, step=1000.0)
    f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
    f_data = st.date_input("DATA", datetime.now())
    
    if st.form_submit_button("Cadastrar"):
        st.info("Dado recebido! Adicione-o na sua planilha do OneDrive para atualizar o BI automaticamente.")

# --- 3. DASHBOARD DE BI (CONFIGURAÇÃO ORIGINAL APROVADA - SEM MUDANÇAS) ---
st.title("📊 BI e Gestão de Fluxo - Carteira 2026")

if not df.empty:
    # Métricas de Topo
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    m2.metric("Inconformidades", len(df[df['Status'] == 'Inconformidade']))
    m3.metric("Processos Pagos", len(df[df['Status'] == 'Pago']))
    
    df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0)
    m4.metric("Volume Total (R$)", f"R$ {df['Valor (R$)'].sum():,.2f}")

    # Gráficos
    col_l, col_r = st.columns(2)
    with col_l:
        fig_status = px.bar(df['Status'].value_counts().reset_index(), x='Status', y='count', color='Status', title="Funil de Vendas")
        st.plotly_chart(fig_status, use_container_width=True)
    with col_r:
        fig_imo = px.pie(df, names='Imobiliária', values='Valor (R$)', title="Volume por Imobiliária")
        st.plotly_chart(fig_imo, use_container_width=True)

    # --- 4. GESTÃO DA CARTEIRA E LIXEIRA (CONFIGURAÇÃO ORIGINAL APROVADA) ---
    st.divider()
    st.subheader("📋 Gestão da Carteira")
    
    # Exibe a tabela completa vinda do OneDrive
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Mantém a lixeira para cada linha (Configuração original)
    for index, row in df.iterrows():
        cols = st.columns([2, 2, 2, 2, 1, 1])
        cols[0].write(f"**{row['Nome do Comprador']}**")
        cols[1].write(row['Status'])
        cols[2].write(row['Imobiliária'])
        cols[3].write(f"R$ {row['Valor (R$)']:,.2f}")
        cols[4].write(str(row['DATA']))
        if cols[5].button("🗑️", key=f"del_{index}"):
            st.warning("Remova a linha no Excel do OneDrive para excluir permanentemente do sistema.")
else:
    st.error("❌ Erro de Conexão: Verifique se o link do OneDrive está como 'Qualquer pessoa pode exibir'.")
