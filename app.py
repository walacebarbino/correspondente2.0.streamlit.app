import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import random
import plotly.express as px
import os

# --- 1. CONFIGURAÇÕES E CONEXÃO ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

DB_NOME = 'fluxo_caixa.db'

def conectar_bd():
    conn = sqlite3.connect(DB_NOME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS processos 
                 (id INTEGER PRIMARY KEY, 
                  data_entrada DATE, 
                  cliente TEXT, 
                  cpf TEXT,
                  status TEXT, 
                  pendencia TEXT, 
                  valor_financiamento REAL,
                  obs TEXT)''')
    conn.commit()
    return conn

# --- 2. FUNÇÕES DE BANCO DE DADOS ---
def gerar_carteira_2026():
    conn = conectar_bd()
    c = conn.cursor()
    c.execute("DELETE FROM processos")
    nomes = ["Walace Barbino", "Ana Paula", "Ricardo Mello", "Sonia Oliveira", "Bruno Henrique", 
             "Carla Diaz", "Marcos Frota", "Julia Roberts", "Fernando Pessoa", "Clarice Lispector"]
    status_opcoes = ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"]
    data_base = datetime(2026, 1, 1)
    for i in range(24):
        data_random = data_base + timedelta(days=random.randint(0, 36))
        nome = random.choice(nomes) + f" {i+1}"
        status = random.choice(status_opcoes)
        valor = random.uniform(150000, 450000)
        c.execute("INSERT INTO processos (data_entrada, cliente, cpf, status, pendencia, valor_financiamento, obs) VALUES (?,?,?,?,?,?,?)", 
                  (data_random.date(), nome, f"000.000.000-{i:02}", status, "Sim" if status == "Inconformidade" else "Não", valor, "Carga automática"))
    conn.commit()
    conn.close()

def deletar_cliente(id_cliente):
    conn = conectar_bd()
    c = conn.cursor()
    c.execute("DELETE FROM processos WHERE id = ?", (id_cliente,))
    conn.commit()
    conn.close()

# --- 3. INTERFACE LATERAL ---
st.sidebar.header("📥 Gestão de Dados")
if st.sidebar.button("🚀 Gerar Carteira 24 Clientes (2026)"):
    gerar_carteira_2026()
    st.sidebar.success("Carteira de 2026 inserida!")
    st.rerun()

# --- 4. EXPORTAÇÃO DO ARQUIVO .DB (PEDIDO) ---
if os.path.exists(DB_NOME):
    with open(DB_NOME, "rb") as f:
        st.sidebar.download_button(
            label="💾 Baixar Banco de Dados (.db)",
            data=f,
            file_name=DB_NOME,
            mime="application/octet-stream"
        )

# --- 5. PROCESSAMENTO E BI ---
conn = conectar_bd()
df = pd.read_sql_query("SELECT * FROM processos", conn)
conn.close()

st.title("📊 BI e Gestão de Fluxo - Carteira 2026")

if not df.empty:
    # Indicadores de Topo
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    m2.metric("Inconformidades", len(df[df['status'] == 'Inconformidade']), delta_color="inverse")
    m3.metric("Processos Pagos", len(df[df['status'] == 'Pago']))
    m4.metric("Total Financiado", f"R$ {df['valor_financiamento'].sum():,.2f}")

    # Gráficos
    c_left, c_right = st.columns(2)
    with c_left:
        fig_bar = px.bar(df['status'].value_counts().reset_index(), x='status', y='count', color='status', title="Funil de Vendas")
        st.plotly_chart(fig_bar, use_container_width=True)
    with c_right:
        df['data_entrada'] = pd.to_datetime(df['data_entrada'])
        df_evolucao = df.groupby(df['data_entrada'].dt.date).size().reset_index(name='qtd')
        fig_line = px.line(df_evolucao, x='data_entrada', y='qtd', title="Entradas em 2026", markers=True)
        st.plotly_chart(fig_line, use_container_width=True)

    # --- 6. TABELA COM FUNÇÃO DELETAR ---
    st.divider()
    st.subheader("📋 Gestão da Carteira")
    for index, row in df.iterrows():
        cols = st.columns([3, 2, 2, 2, 1])
        cols[0].write(row['cliente'])
        cols[1].write(row['status'])
        cols[2].write(f"R$ {row['valor_financiamento']:,.2f}")
        cols[3].write(row['data_entrada'])
        if cols[4].button("🗑️", key=f"del_{row['id']}"):
            deletar_cliente(row['id'])
            st.rerun()
else:
    st.warning("Nenhum dado cadastrado. Use o botão na lateral para gerar a carteira.")
