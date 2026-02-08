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
        
        # Limpeza automática: remove espaços extras nos nomes das colunas para evitar o erro KeyError
        df.columns = [str(c).strip() for c in df.columns]
        
        # Padronização de nomes (corrige o erro das imagens)
        mapeamento = {
            'Nome_do_Comprador': 'Nome do Comprador',
            'Valor (R$)': 'Valor',
            'Nome do Imóvel / Construtora': 'Imóvel'
        }
        df = df.rename(columns=mapeamento)

        if 'DATA' in df.columns:
            df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce')
            df = df.dropna(subset=['DATA']) # Remove linhas sem data
            df['MÊS'] = df['DATA'].dt.strftime('%m/%Y')
            df['DATA_STR'] = df['DATA'].dt.strftime('%d/%m/%Y') # Para exibição amigável
            
        return df
    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")
        return pd.DataFrame()

df = carregar_dados()

# --- BARRA LATERAL (CADASTRO MANTIDO) ---
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
        
        # Métricas
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total de Dossiês", f"{len(df)} PACs")
        
        # Cálculo seguro de valores
        col_valor = 'Valor' if 'Valor' in df.columns else df.columns[-1]
        total_pago = df[df['Status'] == 'Pago'][col_valor].sum() if 'Status' in df.columns else 0
        m2.metric("Volume Pago", f"R$ {total_pago:,.2f}")
        
        inconf = len(df[df['Status'] == 'Inconformidade']) if 'Status' in df.columns else 0
        m3.metric("Inconformidades", inconf)
        
        ticket = df[col_valor].mean() if len(df) > 0 else 0
        m4.metric("Ticket Médio", f"R$ {ticket:,.2f}")

        st.divider()

        # Gráficos de QTD de PACs solicitado
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📈 Qtd de PACs por Mês")
            df_mes = df.groupby('MÊS').size().reset_index(name='Qtd')
            fig_lin = px.line(df_mes, x='MÊS', y='Qtd', markers=True, title="Evolução Mensal")
            st.plotly_chart(fig_lin, use_container_width=True)
            
        with c2:
            st.subheader("🎯 Mix Enquadramento")
            if 'Enquadramento' in df.columns:
                fig_pie = px.pie(df, names='Enquadramento', hole=0.5)
                st.plotly_chart(fig_pie, use_container_width=True)

    # --- ABA 2: CARTEIRA DE CLIENTES ---
    with tab_carteira:
        st.title("📋 Gestão da Carteira")
        
        # Busca dinâmica
        busca = st.text_input("🔍 Buscar por Comprador")
        df_view = df.copy()
        if busca:
            # Filtro que não quebra se a coluna tiver nome diferente
            col_nome = 'Nome do Comprador' if 'Nome do Comprador' in df.columns else df.columns[1]
            df_view = df_view[df_view[col_nome].astype(str).str.contains(busca, case=False)]

        # Tabela profissional (Usa colunas que existirem para não dar erro)
        st.dataframe(df_view, use_container_width=True, hide_index=True)

else:
    st.error("Planilha vazia ou link incorreto. Verifique seu Google Drive.")
