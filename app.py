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

def analisar_documento(texto):
    dados = {}
    hoje = datetime.now()

    # --- EXTRAÇÃO BÁSICA ---
    nome = re.search(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{5,})', texto, re.I)
    dados['Nome'] = nome.group(1).strip().split('\n')[0] if nome else "Não encontrado"
    
    cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto)
    dados['CPF'] = cpf.group() if cpf else "Não encontrado"
    
    rg = re.search(r'(?:RG|IDENTIDADE|IDENT)[:\s]*([\d\.Xx-]+)', texto, re.I)
    dados['RG'] = rg.group(1).strip() if rg else "Não encontrado"

    # --- ENDEREÇO E CEP ---
    cep_match = re.search(r'(\d{5}-\d{3})', texto)
    dados['CEP'] = cep_match.group(1) if cep_match else "Não encontrado"
    
    rua_match = re.search(r'(?:RUA|AV|AVENIDA|DR|ESTRADA|LOGRADOURO)[:\s]+([A-Z0-9\s,.-]+)', texto, re.I)
    dados['Endereço'] = rua_match.group(0).strip().split('\n')[0] if rua_match else "Não encontrado"

    # --- TRABALHO E RENDA ---
    adm_match = re.search(r'(?:ADMISSÃO|ADM|DATA ADM)[:\s]*(\d{2}/\d{2}/\d{4})', texto, re.I)
    dados['Data Admissão'] = adm_match.group(1) if adm_match else "Não encontrado"
    
    renda_match = re.search(r'(?:LÍQUIDO|TOTAL|BRUTO)[:\s]*R\$\s?(\d{1,3}(\.\d{3})*,\d{2})', texto, re.I)
    renda_str = renda_match.group(1) if renda_match else "0,00"
    dados['Renda'] = f"R$ {renda_str}"

    # --- INTELIGÊNCIA DE REGRAS (CAIXA) ---
    alertas = []
    
    # 1. Regra dos 90 dias (Comprovativo de Residência)
    datas_no_doc = re.findall(r'(\d{2}/\d{2}/\d{4})', texto)
    if datas_no_doc:
        try:
            # Assume que a data mais recente no doc de residência é a emissão
            data_emissao = max([datetime.strptime(d, '%d/%m/%Y') for d in datas_no_doc])
            diferenca_dias = (hoje - data_emissao).days
            if diferenca_dias > 90:
                alertas.append(f"🔴 DOC VENCIDO: Emissão há {diferenca_dias} dias.")
            else:
                dados['Validade Residência'] = "✅ Atualizado"
        except: pass

    # 2. Regra Tempo de Casa
    if dados['Data Admissão'] != "Não encontrado":
        dt_adm = datetime.strptime(dados['Data Admissão'], '%d/%m/%Y')
        tempo = relativedelta(hoje, dt_adm)
        dados['Tempo Casa'] = f"{tempo.years}a {tempo.months}m"
        if tempo.years < 1:
            alertas.append("⚠️ Estabilidade: Menos de 1 ano de registro.")
    
    # 3. Faixas MCMV
    try:
        valor_renda = float(renda_str.replace('.', '').replace(',', '.'))
        if valor_renda <= 2850: dados['Faixa'] = "MCMV Faixa 1"
        elif valor_renda <= 4700: dados['Faixa'] = "MCMV Faixa 2"
        elif valor_renda <= 8000: dados['Faixa'] = "MCMV Faixa 3"
        else: dados['Faixa'] = "SBPE"
    except: dados['Faixa'] = "Análise Manual"

    dados['Inconformidades'] = " | ".join(alertas) if alertas else "✅ Sem pendências"
    return dados

# --- INTERFACE ---
upload = st.file_uploader("Arraste os documentos aqui", accept_multiple_files=True)
if upload:
    resultados = []
    for arq in upload:
        if arq.type == "application/pdf":
            paginas = convert_from_bytes(arq.read())
            img = paginas[0]
        else:
            img = Image.open(arq)
        
        texto = pytesseract.image_to_string(img, lang='por')
        res = analisar_documento(texto)
        res['Arquivo'] = arq.name
        resultados.append(res)

    df = pd.DataFrame(resultados)
    st.dataframe(df, use_container_width=True)
    
    df.to_excel("analise_caixa_v3.xlsx", index=False)
    st.download_button("📥 Baixar Relatório Final", open("analise_caixa_v3.xlsx", "rb"), file_name="analise_correspondente.xlsx")
