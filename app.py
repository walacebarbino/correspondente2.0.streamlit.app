import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests

# --- 1. CONFIGURAÇÕES ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

# Link original que você me passou
LINK_ONEDRIVE = "https://1drv.ms/x/c/348d5d4bf85c1dbc/IQABx7R7JVxrQ4FFlg_8TgrhATyuhRja86cSTgU-47UwQfI?e=fn9Ig9"

def obter_link_direto(url):
    # Transforma o link de visualização em link de download direto
    import base64
    base64_enqueue = base64.b64encode(url.encode("ascii")).decode("ascii")
    base64_enqueue = base64_enqueue.replace("/", "_").replace("+", "-").rstrip("=")
    return f"https://api.onedrive.com/v1.0/shares/u!{base64_enqueue}/root/content"

@st.cache_data(ttl=30) # Atualiza a cada 30 segundos para ser rápido
def carregar_dados():
    try:
        url_direta = obter_link_direto(LINK_ONEDRIVE)
        response = requests.get(url_direta)
        # Lê a planilha exatamente com os nomes que você criou
        df = pd.read_excel(io.BytesIO(response.content))
        return df
    except Exception as e:
        return pd.DataFrame()

# Tenta carregar os dados
df = carregar_dados()

# --- 2. BARRA LATERAL (MANTIDA ORIGINAL) ---
st.sidebar.header("📥 Gestão de Dados")
with st.sidebar.form("novo_cadastro"):
    st.subheader("Novo Cadastro Manual")
    st.text_input("Nome do Comprador")
    st.text_input("CPF")
    st.number_input("Valor (R$)", min_value=0.0)
    st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
    if st.form_submit_button("Cadastrar"):
        st.info("Dado recebido! Adicione-o na sua planilha do OneDrive para atualizar o BI.")

# --- 3. DASHBOARD E BI ---
st.title("📊 BI e Gestão de Fluxo - Carteira 2026")

if not df.empty:
    # Verificação das colunas reais
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    m2.metric("Inconformidades", len(df[df['Status'] == 'Inconformidade']))
    m3.metric("Processos Pagos", len(df[df['Status'] == 'Pago']))
    
    # BI Financeiro
    df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0)
    m4.metric("Volume Total", f"R$ {df['Valor (R$)'].sum():,.2f}")

    c1, c2 = st.columns(2)
    with c1:
        fig_bar = px.bar(df['Status'].value_counts().reset_index(), x='Status', y='count', color='Status', title="Funil de Vendas")
        st.plotly_chart(fig_bar, use_container_width=True)
    with c2:
        fig_pie = px.pie(df, names='Imobiliária', values='Valor (R$)', title="Volume por Imobiliária")
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 4. GESTÃO DA CARTEIRA ---
    st.divider()
    st.subheader("📋 Gestão da Carteira")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    # Caso continue sem aparecer, mostra o erro para corrigirmos
    st.error("❌ Erro de Conexão: O Streamlit não conseguiu acessar o arquivo no OneDrive.")
    st.info("Verifique se o arquivo está com 'Acesso Público' (Qualquer pessoa com o link pode exibir).")
