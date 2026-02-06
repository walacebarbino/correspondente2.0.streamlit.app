import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import io

# --- 1. CONFIGURAÇÕES E BANCO DE DADOS ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")
DB_NOME = 'fluxo_correspondente.db'

def conectar_bd():
    conn = sqlite3.connect(DB_NOME)
    c = conn.cursor()
    # Mantendo os cabeçalhos exatos da sua planilha
    c.execute('''CREATE TABLE IF NOT EXISTS processos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data TEXT, 
                  comprador TEXT, 
                  cpf TEXT,
                  imovel TEXT,
                  valor REAL,
                  imobiliaria TEXT,
                  status TEXT)''')
    conn.commit()
    return conn

def deletar_cliente(id_cliente):
    conn = conectar_bd()
    c = conn.cursor()
    c.execute("DELETE FROM processos WHERE id = ?", (id_cliente,))
    conn.commit()
    conn.close()

# --- 2. INTERFACE LATERAL (CADASTRO MANUAL) ---
# Mantendo o formulário aprovado
st.sidebar.header("📥 Gestão de Dados")

with st.sidebar.form("form_cadastro"):
    st.subheader("Novo Registro")
    f_data = st.date_input("DATA", datetime.now())
    f_nome = st.text_input("Nome do Comprador")
    f_cpf = st.text_input("CPF")
    f_imovel = st.text_input("Nome do Imóvel / Construtora")
    f_valor = st.number_input("Valor (R$)", min_value=0.0, step=1000.0)
    f_imobiliaria = st.text_input("Imobiliária")
    f_status = st.selectbox("Status", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
    
    if st.form_submit_button("Cadastrar no Fluxo"):
        if f_nome and f_cpf:
            conn = conectar_bd()
            c = conn.cursor()
            c.execute("""INSERT INTO processos (data, comprador, cpf, imovel, valor, imobiliaria, status) 
                         VALUES (?,?,?,?,?,?,?)""", 
                      (f_data.strftime('%d/%m/%Y'), f_nome, f_cpf, f_imovel, f_valor, f_imobiliaria, f_status))
            conn.commit()
            conn.close()
            st.success("Registrado com sucesso!")
            st.rerun()

# --- 3. DASHBOARD DE BI ---
st.title("📊 BI e Gestão de Fluxo - Carteira 2026")

conn = conectar_bd()
df = pd.read_sql_query("SELECT * FROM processos", conn)
conn.close()

if not df.empty:
    # Indicadores de Topo
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Dossiês", len(df))
    m2.metric("Inconformidades", len(df[df['status'] == 'Inconformidade']))
    m3.metric("Processos Pagos", len(df[df['status'] == 'Pago']))
    m4.metric("Volume Total (R$)", f"{df['valor'].sum():,.2f}")

    # Gráficos
    col_l, col_r = st.columns(2)
    with col_l:
        fig_status = px.bar(df['status'].value_counts().reset_index(), x='status', y='count', color='status', title="Funil de Vendas")
        st.plotly_chart(fig_status, use_container_width=True)
    with col_r:
        fig_imo = px.pie(df, names='imobiliaria', values='valor', title="Volume por Imobiliária")
        st.plotly_chart(fig_imo, use_container_width=True)

    # --- 4. NOVA OPÇÃO: VISUALIZAÇÃO DA CARTEIRA DE CLIENTES ---
    st.divider()
    st.subheader("📂 Carteira de Clientes Completa")
    
    # Exibe a tabela de forma interativa para consulta rápida
    df_view = df.drop(columns=['id']).rename(columns={
        'data': 'DATA', 'comprador': 'Nome do Comprador', 'imovel': 'Imóvel/Construtora',
        'valor': 'Valor (R$)', 'imobiliaria': 'Imobiliária', 'status': 'Status'
    })
    st.dataframe(df_view, use_container_width=True, hide_index=True)

    # --- 5. EXPORTAÇÃO E GESTÃO ---
    st.divider()
    
    # Exportação para o OneDrive
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_view.to_excel(writer, index=False)

    st.download_button(
        label="💾 Baixar Base de Dados para OneDrive",
        data=output.getvalue(),
        file_name="database_correspondente.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.subheader("📋 Gestão e Exclusão")
    for index, row in df.iterrows():
        cols = st.columns([2, 2, 2, 2, 1, 1])
        cols[0].write(f"**{row['comprador']}**")
        cols[1].write(row['status'])
        cols[2].write(row['imobiliaria'])
        cols[3].write(f"R$ {row['valor']:,.2f}")
        cols[4].write(row['data'])
        if cols[5].button("🗑️", key=f"del_{row['id']}"):
            deletar_cliente(row['id'])
            st.rerun()
else:
    st.info("Nenhum dado cadastrado. Use o menu lateral para iniciar seu fluxo.")
