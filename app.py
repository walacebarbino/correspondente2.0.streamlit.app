import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io

# --- 1. CONFIGURAÇÕES ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

# Inicializa o estado da base de dados se não existir
if 'db_caixa' not in st.session_state:
    # Estrutura exata da sua planilha do OneDrive
    st.session_state.db_caixa = pd.DataFrame(columns=[
        "DATA", "Nome do Comprador", "CPF", 
        "Nome do Imóvel / Construtora", "Valor (R$)", 
        "Imobiliária", "Status"
    ])

df = st.session_state.db_caixa

# --- 2. INTERFACE LATERAL (CADASTRO MANUAL) ---
st.sidebar.header("📥 Gestão de Dados")

with st.sidebar.form("novo_cadastro"):
    st.subheader("Novo Cadastro")
    data_cad = st.date_input("DATA", datetime.now())
    nome = st.text_input("Nome do Comprador")
    cpf = st.text_input("CPF")
    imovel = st.text_input("Nome do Imóvel / Construtora")
    valor = st.number_input("Valor (R$)", min_value=0.0, step=1000.0)
    imobiliaria = st.text_input("Imobiliária")
    status = st.selectbox("Status", [
        "Triagem", "Análise Manual", "Montagem PAC", 
        "Inconformidade", "Aprovado", "Pago"
    ])
    
    if st.form_submit_button("Salvar no Fluxo"):
        if nome and cpf:
            nova_linha = pd.DataFrame([{
                "DATA": data_cad.strftime('%d/%m/%Y'),
                "Nome do Comprador": nome,
                "CPF": cpf,
                "Nome do Imóvel / Construtora": imovel,
                "Valor (R$)": valor,
                "Imobiliária": imobiliaria,
                "Status": status
            }])
            st.session_state.db_caixa = pd.concat([st.session_state.db_caixa, nova_linha], ignore_index=True)
            st.success(f"Dossiê de {nome} registrado!")
            st.rerun()

# --- 3. DASHBOARD DE BI ---
st.title("📊 BI e Gestão de Fluxo - Carteira 2026")

if not df.empty:
    # Métricas de Topo
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    m2.metric("Inconformidades", len(df[df['Status'] == 'Inconformidade']))
    m3.metric("Processos Pagos", len(df[df['Status'] == 'Pago']))
    m4.metric("Volume Faturado", f"R$ {df[df['Status'] == 'Pago']['Valor (R$)'].sum():,.2f}")

    # Gráficos
    c_left, c_right = st.columns(2)
    with c_left:
        fig_bar = px.bar(df['Status'].value_counts().reset_index(), 
                         x='Status', y='count', color='Status', 
                         title="Dossiês por Etapa")
        st.plotly_chart(fig_bar, use_container_width=True)
    
    with c_right:
        fig_imo = px.pie(df, names='Imobiliária', values='Valor (R$)', 
                         title="Volume por Imobiliária")
        st.plotly_chart(fig_imo, use_container_width=True)

    # --- 4. EXPORTAÇÃO E TABELA ---
    st.divider()
    
    # Preparação do arquivo para sua pasta CORRESPONDENTE2.0 no OneDrive
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    
    st.download_button(
        label="💾 Baixar Planilha Atualizada para OneDrive",
        data=output.getvalue(),
        file_name="database_correspondente.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.subheader("📋 Gestão da Carteira")
    for index, row in df.iterrows():
        cols = st.columns([2, 2, 2, 2, 1, 1])
        cols[0].write(f"**{row['Nome do Comprador']}**")
        cols[1].write(row['Status'])
        cols[2].write(row['Imobiliária'])
        cols[3].write(f"R$ {row['Valor (R$)']:,.2f}")
        cols[4].write(row['DATA'])
        if cols[5].button("🗑️", key=f"del_{index}"):
            st.session_state.db_caixa = df.drop(index)
            st.rerun()
else:
    st.info("Sistema pronto. Utilize a barra lateral para cadastrar os clientes conforme sua planilha do OneDrive.")
