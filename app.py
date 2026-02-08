import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests

# --- 1. CONFIGURAÇÕES ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

# Link do seu OneDrive
LINK_ORIGINAL = "https://1drv.ms/x/c/348d5d4bf85c1dbc/IQABx7R7JVxrQ4FFlg_8TgrhATyuhRja86cSTgU-47UwQfI?e=fn9Ig9"
# Transformação para link de download direto
LINK_DIRECT = LINK_ORIGINAL.replace("https://1drv.ms/", "https://onedrive.live.com/download?").replace("x/c/", "resid=").split('?')[0] + "&authkey=" + LINK_ORIGINAL.split('?')[1].split('=')[1]

@st.cache_data(ttl=60)
def carregar_dados_nuvem():
    try:
        response = requests.get(LINK_DIRECT)
        df = pd.read_excel(io.BytesIO(response.content))
        return df
    except:
        # Se falhar, mantém a estrutura de colunas aprovada
        return pd.DataFrame(columns=["DATA", "Nome do Comprador", "CPF", "Nome do Imóvel / Construtora", "Valor (R$)", "Imobiliária", "Status"])

# --- 2. CARREGAMENTO ---
df = carregar_dados_nuvem()

# --- 3. INTERFACE LATERAL (CONFIGURAÇÃO ORIGINAL MANTIDA) ---
st.sidebar.header("📥 Gestão de Dados")

with st.sidebar.form("form_cadastro"):
    st.subheader("Novo Cadastro Manual")
    f_data = st.date_input("DATA", datetime.now())
    f_nome = st.text_input("Nome do Comprador")
    f_cpf = st.text_input("CPF")
    f_imovel = st.text_input("Nome do Imóvel / Construtora")
    f_valor = st.number_input("Valor (R$)", min_value=0.0, step=1000.0)
    f_imobiliaria = st.text_input("Imobiliária")
    f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
    
    if st.form_submit_button("Cadastrar"):
        st.info("Para salvar permanentemente, adicione a linha na sua planilha do OneDrive e o sistema atualizará o BI.")

# --- 4. DASHBOARD DE BI (CONFIGURAÇÃO ORIGINAL MANTIDA) ---
st.title("📊 BI e Gestão de Fluxo - Carteira 2026")

if not df.empty:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    m2.metric("Inconformidades", len(df[df['Status'] == 'Inconformidade']))
    m3.metric("Processos Pagos", len(df[df['Status'] == 'Pago']))
    
    df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0)
    m4.metric("Volume Total (R$)", f"{df['Valor (R$)'].sum():,.2f}")

    col_l, col_r = st.columns(2)
    with col_l:
        fig_status = px.bar(df['Status'].value_counts().reset_index(), x='Status', y='count', color='Status', title="Funil de Vendas")
        st.plotly_chart(fig_status, use_container_width=True)
    with col_r:
        fig_imo = px.pie(df, names='Imobiliária', values='Valor (R$)', title="Volume por Imobiliária")
        st.plotly_chart(fig_imo, use_container_width=True)

    # --- 5. CARTEIRA E GESTÃO (CONFIGURAÇÃO ORIGINAL MANTIDA) ---
    st.divider()
    st.subheader("📂 Carteira de Clientes Completa")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("📋 Gestão da Carteira")
    for index, row in df.iterrows():
        cols = st.columns([2, 2, 2, 2, 1, 1])
        cols[0].write(f"**{row['Nome do Comprador']}**")
        cols[1].write(row['Status'])
        cols[2].write(row['Imobiliária'])
        cols[3].write(f"R$ {row['Valor (R$)']:,.2f}")
        cols[4].write(str(row['DATA']))
        if cols[5].button("🗑️", key=f"del_{index}"):
            st.warning("Exclua a linha diretamente no seu Excel do OneDrive para remover do sistema.")
else:
    st.info("Conectando à nuvem... Se não aparecer nada, verifique os dados no seu OneDrive.")
