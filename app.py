import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.express as px

# --- 1. CONFIGURAÇÕES E BANCO DE DADOS ---
st.set_page_config(page_title="CRM Correspondente 2.0", layout="wide")

def conectar_bd():
    conn = sqlite3.connect('fluxo_caixa.db')
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

# --- 2. FUNÇÕES DE APOIO ---
def salvar_processo(nome, cpf, status, valor, obs, data=None):
    conn = conectar_bd()
    c = conn.cursor()
    data_final = data if data else datetime.now().date()
    pendencia = "Sim" if status == "Inconformidade" else "Não"
    c.execute("""INSERT INTO processos (data_entrada, cliente, cpf, status, pendencia, valor_financiamento, obs) 
                 VALUES (?,?,?,?,?,?,?)""", (data_final, nome, cpf, status, pendencia, valor, obs))
    conn.commit()
    conn.close()

# --- 3. INTERFACE LATERAL (CADASTRO) ---
st.sidebar.header("📥 Novo Atendimento")
with st.sidebar.form("form_cadastro"):
    nome = st.text_input("Nome do Cliente")
    cpf = st.text_input("CPF")
    valor = st.number_input("Valor do Financiamento", min_value=0.0, step=1000.0)
    status_ini = st.selectbox("Status Inicial", ["Triagem", "Análise Manual", "Montagem PAC", "Inconformidade", "Aprovado", "Pago"])
    data_retroativa = st.date_input("Data de Entrada", datetime.now())
    obs = st.text_area("Observações")
    
    if st.form_submit_button("Cadastrar no Fluxo"):
        if nome and cpf:
            salvar_processo(nome, cpf, status_ini, valor, obs, data_retroativa)
            st.success("Registrado!")
        else:
            st.error("Preencha Nome e CPF.")

# --- 4. DASHBOARD DE BI ---
st.title("📊 BI e Gestão de Fluxo")

conn = conectar_bd()
df = pd.read_sql_query("SELECT * FROM processos", conn)
conn.close()

if not df.empty:
    # Métricas principais
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total de Dossiês", len(df))
    m2.metric("Em Inconformidade", len(df[df['status'] == 'Inconformidade']), delta_color="inverse")
    m3.metric("Processos Pagos", len(df[df['status'] == 'Pago']))
    m4.metric("Volume Total (R$)", f"{df['valor_financiamento'].sum():,.2f}")

    # Gráficos
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Processos por Etapa")
        fig_status = px.bar(df['status'].value_counts().reset_index(), x='status', y='count', 
                            labels={'count':'Qtd', 'status':'Etapa'}, color='status')
        st.plotly_chart(fig_status, use_container_width=True)

    with col_chart2:
        st.subheader("Evolução Mensal (Entradas)")
        df['data_entrada'] = pd.to_datetime(df['data_entrada'])
        df_mes = df.resample('M', on='data_entrada').size().reset_index(name='qtd')
        fig_mes = px.line(df_mes, x='data_entrada', y='qtd', markers=True)
        st.plotly_chart(fig_mes, use_container_width=True)

    # --- 5. TABELA DE GESTÃO ---
    st.divider()
    st.subheader("📋 Lista Geral de Atendimentos")
    
    # Filtro rápido
    filtro = st.multiselect("Filtrar Status:", df['status'].unique(), default=df['status'].unique())
    df_f = df[df['status'].isin(filtro)]
    
    # Exibição estilizada
    def style_status(val):
        color = '#ff4b4b' if val == 'Inconformidade' else '#00cc66' if val == 'Pago' else None
        return f'background-color: {color}' if color else ''

    st.dataframe(df_f.style.applymap(style_status, subset=['status']), use_container_width=True)

else:
    st.info("Nenhum dado cadastrado. Use o menu lateral para iniciar seu fluxo desde Janeiro.")
