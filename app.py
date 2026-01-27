import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import re
from pdf2image import convert_from_bytes
from datetime import datetime
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Parceria - Correspondente 2.0", layout="wide")
st.title("🏦 Parceria - Correspondente 2.0")

def extrair_dados_especificos(texto):
    """Função com 'Pente Fino' para documentos da Caixa"""
    dados = {}
    
    # --- DADOS PESSOAIS ---
    nome = re.search(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{5,})', texto, re.I)
    dados['Nome'] = nome.group(1).strip().split('\n')[0] if nome else "Não encontrado"
    
    cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto)
    dados['CPF'] = cpf.group() if cpf else "Não encontrado"
    
    rg = re.search(r'(?:RG|IDENTIDADE)[:\s]*([\d\.Xx-]+)', texto, re.I)
    dados['RG'] = rg.group(1).strip() if rg else "Não encontrado"
    
    nasc = re.search(r'(?:NASCIMENTO|NASC)[:\s]*(\d{2}/\d{2}/\d{4})', texto, re.I)
    dados['Data Nasc.'] = nasc.group(1) if nasc else "Não encontrado"

    # --- CNH ---
    registro = re.search(r'(?:REGISTRO)[:\s]*(\d{11})', texto, re.I)
    dados['Nº CNH'] = registro.group(1) if registro else "Não encontrado"

    # --- ENDEREÇO ---
    cep = re.search(r'(\d{5}-\d{3})', texto)
    dados['CEP'] = cep.group(1) if cep else "Não encontrado"
    rua = re.search(r'(?:RUA|AV|AVENIDA|DR|ESTRADA)[:\s]+([A-Z0-9\s,.-]+)', texto, re.I)
    dados['Endereço'] = rua.group(0).strip().split('\n')[0] if rua else "Não encontrado"

    # --- CONTRACHEQUE / EMPRESA ---
    cnpj = re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', texto)
    dados['CNPJ Empresa'] = cnpj.group() if cnpj else "Não encontrado"
    
    adm = re.search(r'(?:ADMISSÃO|ADM)[:\s]*(\d{2}/\d{2}/\d{4})', texto, re.I)
    dados['Data Admissão'] = adm.group(1) if adm else "Não encontrado"
    
    cargo = re.search(r'(?:CARGO|FUNÇÃO)[:\s]+([A-Z\s/]+)', texto, re.I)
    dados['Cargo'] = cargo.group(1).strip().split('\n')[0] if cargo else "Não encontrado"

    # --- DADOS BANCÁRIOS ---
    banco = re.search(r'(?:BANCO)[:\s]+([A-Z\s]+)', texto, re.I)
    dados['Banco'] = banco.group(1).strip().split('\n')[0] if banco else "Não encontrado"

    # --- ANÁLISE DE CONFORMIDADE ---
    alertas = []
    if dados['Data Admissão'] != "Não encontrado":
        dt_adm = datetime.strptime(dados['Data Admissão'], '%d/%m/%Y')
        tempo = relativedelta(datetime.now(), dt_adm)
        dados['Tempo de Casa'] = f"{tempo.years} anos e {tempo.months} meses"
        if tempo.years < 1:
            alertas.append("⚠️ Menos de 1 ano de registro (Alerta de Estabilidade).")
    else:
        dados['Tempo de Casa'] = "N/A"

    dados['Análise'] = " | ".join(alertas) if alertas else "✅ OK"
    
    return dados

# --- INTERFACE STREAMLIT ---
upload = st.file_uploader("Suba Documentos (PDF, JPG, PNG)", accept_multiple_files=True)

if upload:
    lista_final = []
    for arq in upload:
        with st.spinner(f'Analisando {arq.name}...'):
            # Converte PDF ou Imagem
            if arq.type == "application/pdf":
                paginas = convert_from_bytes(arq.read())
                img = paginas[0]
            else:
                img = Image.open(arq)
            
            texto = pytesseract.image_to_string(img, lang='por')
            res = extrair_dados_especificos(texto)
            res['Arquivo'] = arq.name
            lista_final.append(res)

    df = pd.DataFrame(lista_final)
    st.write("### Relatório de Análise Técnica")
    st.dataframe(df)

    # Botão de Exportação
    df.to_excel("analise_parceria.xlsx", index=False)
    st.download_button("📥 Baixar Planilha para a Caixa", open("analise_parceria.xlsx", "rb"), file_name="analise_caixa.xlsx")
