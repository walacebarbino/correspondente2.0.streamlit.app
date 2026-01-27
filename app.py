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
st.markdown("### Analista de Crédito e Subsídio MCMV")

def calcular_subsidio(renda, regiao="Geral"):
    """Calcula estimativa de subsídio MCMV baseada na renda bruta"""
    if renda <= 2850:
        return 55000.00  # Máximo Faixa 1 (Estimado)
    elif renda <= 4700:
        return 29000.00  # Média Faixa 2 (Estimado)
    elif renda <= 8000:
        return 0.00      # Faixa 3 geralmente não tem subsídio direto, apenas juros reduzidos
    return 0.00

def analisar_texto_completo(texto_paginas):
    # Une o texto de todas as páginas para uma análise global
    texto_total = " ".join(texto_paginas)
    hoje = datetime.now()
    dados = {}

    # --- EXTRAÇÃO DE IDENTIDADE ---
    nome = re.search(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{5,})', texto_total, re.I)
    dados['Nome'] = nome.group(1).strip().split('\n')[0] if nome else "Não encontrado"
    
    cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto_total)
    dados['CPF'] = cpf.group() if cpf else "Não encontrado"

    # --- EXTRAÇÃO DE RENDA E FGTS (SOMA GLOBAL) ---
    renda_match = re.search(r'(?:LÍQUIDO|TOTAL|BRUTO)[:\s]*R\$\s?(\d{1,3}(\.\d{3})*,\d{2})', texto_total, re.I)
    renda_val = float(renda_match.group(1).replace('.', '').replace(',', '.')) if renda_match else 0.0
    dados['Renda Bruta'] = renda_val

    # Soma todos os saldos de FGTS encontrados nas páginas
    saldos_fgts = re.findall(r'(?:SALDO|DISPONÍVEL|RESCISÓRIOS)[:\s]*R\$\s?(\d{1,3}(\.\d{3})*,\d{2})', texto_total, re.I)
    total_fgts = sum([float(s[0].replace('.', '').replace(',', '.')) for s in saldos_fgts])
    dados['FGTS Total'] = total_fgts

    # --- REGRAS DE NEGÓCIO ---
    alertas = []
    
    # 1. Enquadramento e Subsídio
    dados['Subsídio Est.'] = calcular_subsidio(renda_val)
    if renda_val <= 8000:
        dados['Modalidade'] = "MCMV"
    else:
        dados['Modalidade'] = "SBPE"

    # 2. Validade de Documento (90 dias)
    datas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto_total)
    if datas:
        try:
            data_doc = max([datetime.strptime(d, '%d/%m/%Y') for d in datas])
            dias = (hoje - data_doc).days
            if dias > 90:
                alertas.append(f"🔴 DOC ANTIGO: {dias} dias.")
        except: pass

    # 3. Tempo de Casa
    adm = re.search(r'(?:ADMISSÃO|ADM)[:\s]*(\d{2}/\d{2}/\d{4})', texto_total, re.I)
    if adm:
        dt_adm = datetime.strptime(adm.group(1), '%d/%m/%Y')
        tempo = relativedelta(hoje, dt_adm)
        if tempo.years < 1:
            alertas.append("⚠️ Estabilidade < 1 ano")
        dados['Tempo Casa'] = f"{tempo.years}a {tempo.months}m"
    else:
        dados['Tempo Casa'] = "N/A"

    dados['Parecer Final'] = " | ".join(alertas) if alertas else "✅ Processo Saneado"
    return dados

# --- INTERFACE ---
upload = st.file_uploader("Suba os documentos do processo (PDF multi-páginas)", accept_multiple_files=True)

if upload:
    lista_final = []
    for arq in upload:
        with st.spinner(f'Analisando todas as páginas de {arq.name}...'):
            texto_das_paginas = []
            if arq.type == "application/pdf":
                paginas_img = convert_from_bytes(arq.read())
                for p in paginas_img:
                    texto_das_paginas.append(pytesseract.image_to_string(p, lang='por'))
            else:
                img = Image.open(arq)
                texto_das_paginas.append(pytesseract.image_to_string(img, lang='por'))
            
            res = analisar_texto_completo(texto_das_paginas)
            res['Arquivo'] = arq.name
            lista_final.append(res)

    df = pd.DataFrame(lista_final)
    st.write("### 📊 Resultado da Pré-Análise Técnica")
    st.dataframe(df, use_container_width=True)
    
    # Exportação formatada
    df.to_excel("analise_correspondente_v4.xlsx", index=False)
    st.download_button("📥 Baixar Planilha de Montagem de Processo", open("analise_correspondente_v4.xlsx", "rb"), file_name="analise_caixa_completa.xlsx")
