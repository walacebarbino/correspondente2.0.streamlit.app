import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests

# --- CONFIGURAÇÕES DE PÁGINA ---
st.set_page_config(page_title="Gestão Correspondente 2026", layout="wide", page_icon="📊")

# Link direto do seu Google Drive
LINK_PLANILHA = "https://docs.google.com/spreadsheets/d/1n6529TSBqYhwqAq-ZwVleV0b9q0p38PSPT4eU1z-uNc/export?format=xlsx"

@st.cache_data(ttl=10)
def carregar_dados():
    try:
        response = requests.get(LINK_PLANILHA, timeout=20)
        df = pd.read_excel(io.BytesIO(response.content))
        
        # Tratamento de Datas para os Gráficos
        if 'DATA' in df.columns:
            df['DATA_DT'] = pd.to_datetime(df['DATA'], dayfirst=True)
            df['DATA_STR'] = df['DATA_DT'].dt.strftime('%d/%m/%Y') # Para exibição
            df['MÊS'] = df['DATA_DT'].dt.strftime('%m/%Y')
        return df
    except:
        return pd.DataFrame()

df = carregar_dados()

# --- BARRA LATERAL (CADASTRO MANTIDO) ---
with st.sidebar:
    st.header("📥 Gestão de Dados")
    with st.form("form_cadastro"):
        st.subheader("Novo Cadastro Manual")
        f_data = st.date_input("DATA", datetime.now(), format="DD/MM/YYYY")
        f_nome = st.text_input("Nome do Comprador")
        f_cpf = st.text_input("CPF")
        f_imovel = st.text_input("Nome do Imóvel / Construtora")
        f_valor = st.number_input("Valor (R$)", min_value=0.0)
        f_imobiliaria = st.text_input("Imobiliária")
        f_enquadramento = st.selectbox("Enquadramento", ["SBPE", "MCMV", "FGTS", "Outros"])
        f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
        
        if st.form_submit_button("Cadastrar"):
            st.info("Dado recebido! Adicione na sua planilha do Google Drive para atualizar.")

# --- NAVEGAÇÃO POR ABAS (PÁGINAS SEPARADAS) ---
tab_bi, tab_carteira = st.tabs(["📊 Business Intelligence", "📋 Carteira de Clientes"])

# --- ABA 1: BI PROFISSIONAL ---
with tab_bi:
    st.title("📊 BI e Performance de Vendas - 2026")
    
    if not df.empty:
        # Métricas em destaque
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total de Dossiês", f"{len(df)} PACs")
        
        v_pago = df[df['Status'] == 'Pago']['Valor (R$)'].sum()
        m2.metric("Volume Pago", f"R$ {v_pago:,.2f}")
        
        inconf = len(df[df['Status'] == 'Inconformidade'])
        m3.metric("Inconformidades", inconf, delta=f"{inconf} pendentes", delta_color="inverse")
        
        ticket = df['Valor (R$)'].mean() if len(df) > 0 else 0
        m4.metric("Ticket Médio", f"R$ {ticket:,.2f}")

        st.divider()

        # Gráficos
        col_esq, col_dir = st.columns([2, 1])

        with col_esq:
            st.subheader("📈 Volume Mensal de PACs")
            # Agrupamento por mês para o gráfico solicitado
            df_mensal = df.groupby('MÊS').size().reset_index(name='Qtd')
            fig_mensal = px.line(df_mensal, x='MÊS', y='Qtd', markers=True, 
                                line_shape="spline", color_discrete_sequence=["#00CC96"])
            fig_mensal.update_layout(hovermode="x unified")
            st.plotly_chart(fig_mensal, use_container_width=True)

        with col_dir:
            st.subheader("🎯 Mix por Enquadramento")
            fig_pie = px.pie(df, names='Enquadramento', hole=0.4, 
                            color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("📑 Status dos Processos")
        fig_status = px.bar(df, x='Status', color='Status', barmode='group')
        st.plotly_chart(fig_status, use_container_width=True)
    else:
        st.warning("Aguardando sincronização com o Google Drive...")

# --- ABA 2: CARTEIRA DE CLIENTES ---
with tab_carteira:
    st.title("📋 Gestão da Carteira")
    
    if not df.empty:
        # Filtro rápido na página de carteira
        busca = st.text_input("🔍 Buscar por Comprador ou Imobiliária")
        df_filtrado = df[df['Nome do Comprador'].str.contains(busca, case=False, na=False)] if busca else df

        # Exibição profissional da tabela
        st.dataframe(
            df_filtrado[['DATA_STR', 'Nome_do_Comprador', 'Status', 'Enquadramento', 'Imobiliária', 'Valor (R$)']],
            column_config={
                "DATA_STR": "Data",
                "Valor (R$)": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                "Nome_do_Comprador": "Comprador"
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.error("Erro ao carregar a base de dados.")
