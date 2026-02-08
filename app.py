import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests

# --- 1. CONFIGURAÇÕES ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

# Link do seu OneDrive transformado para Download Direto
LINK_ORIGINAL = "https://1drv.ms/x/c/348d5d4bf85c1dbc/IQABx7R7JVxrQ4FFlg_8TgrhATyuhRja86cSTgU-47UwQfI?e=fn9Ig9"
LINK_DIRECT = LINK_ORIGINAL.replace("https://1drv.ms/", "https://onedrive.live.com/download?").replace("x/c/", "resid=").split('?')[0] + "&authkey=" + LINK_ORIGINAL.split('?')[1].split('=')[1]

@st.cache_data(ttl=60) # Atualiza a cada 1 minuto
def carregar_dados_nuvem():
    try:
        # Tenta ler a planilha diretamente da sua nuvem
        response = requests.get(LINK_DIRECT)
        df = pd.read_excel(io.BytesIO(response.content))
        return df
    except Exception as e:
        # Caso o link falhe, retorna um DataFrame vazio com seus cabeçalhos
        return pd.DataFrame(columns=["DATA", "Nome do Comprador", "CPF", "Nome do Imóvel / Construtora", "Valor (R$)", "Imobiliária", "Status"])

# --- 2. CARREGAMENTO ---
df = carregar_dados_nuvem()

st.title("📊 BI e Gestão de Fluxo - Nuvem OneDrive")

# --- 3. DASHBOARD DE BI ---
if not df.empty:
    # Métricas Reais da sua Planilha
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    m2.metric("Inconformidades", len(df[df['Status'] == 'Inconformidade']))
    m3.metric("Processos Pagos", len(df[df['Status'] == 'Pago']))
    
    # Tratamento de valores numéricos para o BI
    df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0)
    m4.metric("Volume Total (R$)", f"{df['Valor (R$)'].sum():,.2f}")

    # Gráficos dinâmicos
    c1, c2 = st.columns(2)
    with c1:
        fig_funil = px.bar(df['Status'].value_counts().reset_index(), x='Status', y='count', color='Status', title="Funil de Vendas")
        st.plotly_chart(fig_funil, use_container_width=True)
    with c2:
        fig_imo = px.pie(df, names='Imobiliária', values='Valor (R$)', title="Volume por Imobiliária")
        st.plotly_chart(fig_imo, use_container_width=True)

    # --- 4. VISUALIZAÇÃO DA CARTEIRA ---
    st.divider()
    st.subheader("📂 Carteira de Clientes (Sincronizada)")
    st.dataframe(df, use_container_width=True, hide_index=True)

else:
    st.warning("⚠️ O sistema ainda não detectou dados na planilha. Verifique se o arquivo no OneDrive possui conteúdo.")

# --- 5. GESTÃO MANUAL (LATERAL) ---
with st.sidebar:
    st.header("📥 Gestão de Dados")
    st.info("Para atualizar o BI, adicione ou remova linhas diretamente na sua planilha do OneDrive e o sistema refletirá aqui.")
    if st.button("🔄 Atualizar BI Agora"):
        st.rerun()
