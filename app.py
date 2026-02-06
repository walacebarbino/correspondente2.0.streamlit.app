import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import requests
import io

# --- 1. CONFIGURAÇÕES ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

# COLE O SEU LINK DE PARTILHA DO ONEDRIVE AQUI
LINK_PLANILHA = "SEU_LINK_DO_ONEDRIVE_AQUI"

def converter_link_onedrive(url):
    # Função simples para tentar converter link de partilha em link de download direto
    if "1drv.ms" in url:
        # Se for link encurtado, esta lógica pode variar, o ideal é o link direto do arquivo
        return url.replace("redir?", "download?").replace("view?", "download?")
    return url

@st.cache_data(ttl=60) # Atualiza a cada 1 minuto
def carregar_dados_nuvem(url):
    try:
        # Tenta ler o Excel diretamente do OneDrive
        response = requests.get(url)
        df = pd.read_excel(io.BytesIO(response.content))
        return df
    except:
        # Se falhar (link privado), inicia base vazia com os seus cabeçalhos
        return pd.DataFrame(columns=[
            "DATA", "Nome do Comprador", "CPF", 
            "Nome do Imóvel / Construtora", "Valor (R$)", 
            "Imobiliária", "Status"
        ])

# --- 2. CARREGAMENTO DOS DADOS ---
# O sistema lê a planilha que você já iniciou com os 24 exemplos
df = carregar_dados_nuvem(converter_link_onedrive(LINK_PLANILHA))

st.title("📊 BI e Gestão de Fluxo - Conectado ao OneDrive")

# --- 3. DASHBOARD DE BI (Baseado na sua planilha real) ---
if not df.empty:
    # Métricas calculadas dos dados da sua planilha
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    m2.metric("Em Análise", len(df[df['Status'] == 'Análise Manual']))
    m3.metric("Processos Pagos", len(df[df['Status'] == 'Pago']))
    
    # Tratamento do valor para garantir que é numérico
    df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0)
    m4.metric("Volume Total", f"R$ {df['Valor (R$)'].sum():,.2f}")

    # Gráficos dinâmicos
    col_a, col_b = st.columns(2)
    with col_a:
        fig_status = px.pie(df, names='Status', title="Estado dos Processos")
        st.plotly_chart(fig_status, use_container_width=True)
    
    with col_b:
        # Evolução baseada na coluna DATA da sua planilha
        df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce')
        df_evol = df.groupby(df['DATA'].dt.date).size().reset_index(name='qtd')
        fig_evol = px.line(df_evol, x='DATA', y='qtd', title="Entradas por Data", markers=True)
        st.plotly_chart(fig_evol, use_container_width=True)

    # --- 4. VISUALIZAÇÃO DA TABELA ---
    st.divider()
    st.subheader("📋 Lista de Clientes (Sincronizada)")
    st.dataframe(df, use_container_width=True)
else:
    st.warning("Não foi possível ler os dados. Verifique se o link do OneDrive permite 'Acesso Público' ou use o cadastro manual.")

# --- 5. CADASTRO (LADO ESQUERDO) ---
with st.sidebar:
    st.header("📥 Novo Registro")
    with st.form("form_novo"):
        n_nome = st.text_input("Nome do Comprador")
        n_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
        n_valor = st.number_input("Valor (R$)", min_value=0.0)
        if st.form_submit_button("Adicionar"):
            st.info("Para salvar permanentemente no OneDrive, adicione a linha na sua planilha e o sistema atualizará aqui.")
