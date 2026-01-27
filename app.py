import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import re
from pdf2image import convert_from_bytes

st.set_page_config(page_title="Parceria - Correspondente 2.0", layout="wide")
st.title("🏦 Parceria - Correspondente 2.0")

def extrair_campos_avancados(texto):
    """Refina a busca de campos específicos usando padrões contextuais"""
    dados = {}
    
    # 1. Identificação Pessoal
    dados['CPF'] = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto).group() if re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto) else "Não encontrado"
    dados['RG'] = re.search(r'RG[:\s]*([\d\.Xx-]+)', texto, re.I).group(1) if re.search(r'RG[:\s]*([\d\.Xx-]+)', texto, re.I) else "Não encontrado"
    dados['Data Nascimento'] = re.search(r'(\d{2}/\d{2}/\d{4})', texto).group(1) if re.search(r'(\d{2}/\d{2}/\d{4})', texto) else "Não encontrado"
    
    # 2. Dados da CNH
    cnh_num = re.search(r'REGISTRO[:\s]*(\d{11})', texto, re.I)
    dados['Nº CNH'] = cnh_num.group(1) if cnh_num else "Não encontrado"

    # 3. Endereço e CEP
    cep = re.search(r'(\d{5}-\d{3})', texto)
    dados['CEP'] = cep.group(1) if cep else "Não encontrado"
    # Procura rua (geralmente após RUA, AV, DR)
    rua = re.search(r'(?:RUA|AV|AVENIDA|DR|RODOVIA)[:\s]+([A-Z0-9\s,.-]+)', texto, re.I)
    dados['Endereço'] = rua.group(0).strip() if rua else "Não encontrado"

    # 4. Dados do Contra-Cheque (Trabalho)
    # Procura data de admissão perto da palavra 'Admissão'
    adm = re.search(r'(?:Admissão|ADM)[:\s]+(\d{2}/\d{2}/\d{4})', texto, re.I)
    dados['Data Admissão'] = adm.group(1) if adm else "Não encontrado"
    
    # Cargo (procura após a palavra 'Cargo')
    cargo = re.search(r'Cargo[:\s]+([A-Z\s-]+)', texto, re.I)
    dados['Cargo'] = cargo.group(1).strip() if cargo else "Não encontrado"
    
    # Empresa e CNPJ
    cnpj = re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', texto)
    dados['CNPJ Empresa'] = cnpj.group() if cnpj else "Não encontrado"
    
    # 5. Assinaturas e Outros
    dados['Assinatura Detectada'] = "Sim" if "assinatura" in texto.lower() or "assinado" in texto.lower() else "Não detectada"

    return dados

# --- Interface ---
arquivos = st.file_uploader("Upload de Documentos", accept_multiple_files=True)

if arquivos:
    resultados = []
    for arq in arquivos:
        if arq.type == "application/pdf":
            paginas = convert_from_bytes(arq.read())
            img = paginas[0]
        else:
            img = Image.open(arq)
        
        texto_bruto = pytesseract.image_to_string(img, lang='por')
        
        # Processa os campos
        campos = extrair_campos_avancados(texto_bruto)
        campos['Arquivo'] = arq.name
        resultados.append(campos)

    df = pd.DataFrame(resultados)
    st.write("### Análise de Dados Extraídos")
    st.dataframe(df)
    
    # Exportação
    df.to_excel("relatorio_completo.xlsx", index=False)
    st.download_button("📥 Baixar Relatório Completo", open("relatorio_completo.xlsx", "rb"), file_name="analise_detalhada.xlsx")
