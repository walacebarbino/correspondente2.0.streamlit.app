import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests

# --- CONFIGURAÇÕES DE PÁGINA ---
st.set_page_config(page_title="Gestão Correspondente 2026", layout="wide", page_icon="📊")

LINK_PLANILHA = "https://docs.google.com/spreadsheets/d/1n6529TSBqYhwqAq-ZwVleV0b9q0p38PSPT4eU1z-uNc/export?format=xlsx"

@st.cache_data(ttl=10)
def carregar_dados():
    try:
        response = requests.get(LINK_PLANILHA, timeout=20)
        df = pd.read_excel(io.BytesIO(response.content))
        df.columns = [str(c).strip() for c in df.columns]
        
        mapeamento = {
            'Nome_do_Comprador': 'Nome do Comprador',
            'Valor (R$)': 'Valor',
            'Nome do Imóvel / Construtora': 'Imóvel'
        }
        df = df.rename(columns=mapeamento)

        if 'DATA' in df.columns:
            df['DATA_DT'] = pd.to_datetime(df['DATA'], errors='coerce')
            df = df.dropna(subset=['DATA_DT'])
            # 1. AJUSTE DE DATA: Forçando o formato DD/MM/AAAA para exibição
            df['DATA_EXIBIR'] = df['DATA_DT'].dt.strftime('%d/%m/%Y')
            df['MÊS'] = df['DATA_DT'].dt.strftime('%m/%Y')
            
        return df
    except Exception as e:
        return pd.DataFrame()

df = carregar_dados()

# --- BARRA LATERAL (CADASTRO) ---
with st.sidebar:
    st.header("📥 Gestão de Dados")
    with st.form("form_cadastro"):
        st.subheader("Novo Cadastro Manual")
        f_data = st.date_input("DATA", datetime.now(), format="DD/MM/YYYY")
        f_nome = st.text_input("Nome do Comprador")
        f_imovel = st.text_input("Nome do Imóvel / Construtora")
        f_valor = st.number_input("Valor (R$)", min_value=0.0)
        f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
        f_enquadramento = st.selectbox("Enquadramento", ["SBPE", "MCMV", "FGTS", "Outros"])
        
        if st.form_submit_button("Cadastrar"):
            st.info("Dado recebido! Adicione na sua planilha para atualizar.")

# --- NAVEGAÇÃO POR ABAS ---
tab_bi, tab_carteira = st.tabs(["📊 Dashboard Profissional", "📋 Carteira de Clientes"])

if not df.empty:
    # --- ABA 1: BI PROFISSIONAL ---
    with tab_bi:
        st.title("📊 BI e Performance de Vendas - 2026")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total de Dossiês", f"{len(df)} PACs")
        col_valor = 'Valor' if 'Valor' in df.columns else df.columns[-1]
        total_pago = df[df['Status'] == 'Pago'][col_valor].sum() if 'Status' in df.columns else 0
        m2.metric("Volume Pago", f"R$ {total_pago:,.2f}")
        inconf = len(df[df['Status'] == 'Inconformidade']) if 'Status' in df.columns else 0
        m3.metric("Inconformidades", inconf)
        ticket = df[col_valor].mean() if len(df) > 0 else 0
        m4.metric("Ticket Médio", f"R$ {ticket:,.2f}")

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📈 Qtd de PACs por Mês")
            df_mes = df.groupby('MÊS').size().reset_index(name='Qtd')
            fig_lin = px.line(df_mes, x='MÊS', y='Qtd', markers=True)
            st.plotly_chart(fig_lin, use_container_width=True)
        with c2:
            st.subheader("🎯 Mix Enquadramento")
            if 'Enquadramento' in df.columns:
                fig_pie = px.pie(df, names='Enquadramento', hole=0.5)
                st.plotly_chart(fig_pie, use_container_width=True)

    # --- ABA 2: CARTEIRA DE CLIENTES ---
    with tab_carteira:
        st.title("📋 Gestão da Carteira")
        
        busca = st.text_input("🔍 Buscar por Comprador")
        df_view = df.copy()
        if busca:
            col_nome = 'Nome do Comprador' if 'Nome do Comprador' in df.columns else df.columns[1]
            df_view = df_view[df_view[col_nome].astype(str).str.contains(busca, case=False)]

        # 2. OPÇÃO DE EXCLUIR E DATA DD/MM/AAAA
        # Criamos o layout de colunas para simular a tabela com o botão de excluir
        cols = st.columns([1, 2, 1, 1, 1, 1, 0.5])
        titulos = ["**Data**", "**Comprador**", "**Imóvel**", "**Valor**", "**Enquadramento**", "**Status**", " "]
        for col, t in zip(cols, titulos):
            col.write(t)

        for i, row in df_view.iterrows():
            c = st.columns([1, 2, 1, 1, 1, 1, 0.5])
            c[0].write(row.get('DATA_EXIBIR', '---')) # Data formatada
            c[1].write(row.get('Nome do Comprador', '---'))
            c[2].write(row.get('Imóvel', '---'))
            c[3].write(f"R$ {row.get('Valor', 0):,.2f}")
            c[4].write(row.get('Enquadramento', '---'))
            c[5].write(row.get('Status', '---'))
            # Retornando o botão de excluir
            if c[6].button("🗑️", key=f"del_{i}"):
                st.warning("Para excluir definitivamente, remova a linha na planilha do Google Drive.")

else:
    st.error("Planilha não encontrada ou vazia.")
