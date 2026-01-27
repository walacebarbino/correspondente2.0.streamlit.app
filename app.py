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
    """Função com 'Pente Fino' para documentos imobiliários"""
    dados = {}
    
    # 1. DADOS PESSOAIS (Procura nomes após termos específicos)
    nome = re.search(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{5,})', texto, re.I)
    dados['Nome'] = nome.group(1).strip().split('\n')[0] if nome else "Não encontrado"
    
    cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto)
    dados['CPF'] = cpf.group() if cpf else "Não encontrado"
    
    # Busca RG (numérico ou com pontos/traço)
    rg = re.search(r'(?:RG|IDENTIDADE|IDENT)[:\s]*([\d\.Xx-]+)', texto, re.I)
    dados['RG'] = rg.group(1).strip() if rg else "Não encontrado"
    
    nasc = re.search(r'(?:NASCIMENTO|NASC)[:\s]*(\d{2}/\d{2}/\d{4})', texto, re.I)
    dados['Data Nasc.'] = nasc.group(1) if nasc else "Não encontrado"

    # 2. CNH (Número de Registro)
    registro = re.search(r'(?:REGISTRO)[:\s]*(\d{11})', texto, re.I)
    dados['Nº CNH'] = registro.group(1) if registro else "Não encontrado"

    # 3. ENDEREÇO E CEP
    cep = re.search(r'(\d{5}-\d{3})', texto)
    dados['CEP'] = cep.group(1) if cep else "Não encontrado"
    rua = re.search(r'(?:RUA|AV|AVENIDA|DR|ESTRADA|LOGRADOURO)[:\s]+([A-Z0-9\s,.-]+)', texto, re.I)
    dados['Endereço'] = rua.group(0).strip().split('\n')[0] if rua else "Não encontrado"

    # 4. CONTRACHEQUE / TRABALHO
    cnpj = re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', texto)
    dados['CNPJ Empresa'] = cnpj.group() if cnpj else "Não encontrado"
    
    adm = re.search(r'(?:ADMISSÃO|ADM|DATA ADM)[:\s]*(\d{2}/\d{2}/\d{4})', texto, re.I)
    dados['Data Admissão'] = adm.group(1) if adm else "Não encontrado"
    
    cargo = re.search(r'(?:CARGO|FUNÇÃO)[:\s]+([A-Z\s/]+)', texto, re.I)
    dados['Cargo'] = cargo.group(1).strip().split('\n')[0] if cargo else "Não encontrado"

    # 5. VALORES E BANCO
    # Busca valor líquido próximo a 'Líquido' ou 'Total'
    renda_match = re.search(r'(?:LÍQUIDO|TOTAL|BRUTO)[:\s]*R\$\s?(\d{1,3}(\.\d{3})*,\d{2})', texto, re.I)
    dados['Renda Extraída'] = renda_match.group(1) if renda_match else "0,00"

    # 6. ANÁLISE TÉCNICA (Inteligência)
    alertas = []
    
    # Cálculo Tempo de Casa
    if dados['Data Admissão'] != "Não encontrado":
        try:
            dt_adm = datetime.strptime(dados['Data Admissão'], '%d/%m/%Y')
            tempo = relativedelta(datetime.now(), dt_adm)
            dados['Tempo de Casa'] = f"{tempo.years}a {tempo.months}m"
            if tempo.years < 1:
                alertas.append("⚠️ Estabilidade: Menos de 1 ano.")
        except:
            dados['Tempo de Casa'] = "Erro cálculo"
    else:
        dados['Tempo de Casa'] = "N/A"

    # Enquadramento MCMV (Exemplo simplificado)
    try:
        val_r = float(dados['Renda Extraída'].replace('.', '').replace(',', '.'))
        if val_r <= 2850: dados['Faixa MCMV'] = "Faixa 1"
        elif val_r <= 4700: dados['Faixa MCMV'] = "Faixa 2"
        elif val_r <= 8000: dados['Faixa MCMV'] = "Faixa 3"
        else: dados['Faixa MCMV'] = "SBPE"
    except:
        dados['Faixa MCMV'] = "Análise Manual"

    dados['Inconformidades'] = " | ".join(alertas) if alertas else "✅ Tudo OK"
    
    return dados

# --- INTERFACE ---
st.info("Dica: Para melhores resultados, garanta que os PDFs não estão protegidos por senha.")
upload = st.file_uploader("Upload de Documentos (PDF, JPG, PNG)", accept_multiple_files=True)

if upload:
    lista_final = []
    for arq in upload:
        with st.spinner(f'Processando {arq.name}...'):
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
    st.write("### 📊 Relatório de Conformidade")
    st.dataframe(df, use_container_width=True)

    # Exportação para Excel
    df.to_excel("relatorio_caixa_v2.xlsx", index=False)
    st.download_button("📥 Baixar Planilha Analisada", open("relatorio_caixa_v2.xlsx", "rb"), file_name="analise_correspondente_2.0.xlsx")
