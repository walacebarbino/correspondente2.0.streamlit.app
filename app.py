import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import re
from pdf2image import convert_from_bytes
from datetime import datetime
from dateutil.relativedelta import relativedelta
import io

# Configuração Visual
st.set_page_config(page_title="Parceria - Correspondente 2.0", layout="wide")
st.title("🏦 Parceria - Correspondente 2.0")
st.subheader("Analista de Crédito Inteligente e Subsídio MCMV")

def calcular_subsidio_mcmv(renda):
    """Lógica de estimativa de subsídio conforme faixas atuais da Caixa"""
    if renda <= 2850: return 55000.00
    elif renda <= 4700: return 29000.00
    elif renda <= 8000: return 0.00
    return 0.00

def analisar_processo_completo(textos_das_paginas):
    texto_unificado = " ".join(textos_das_paginas)
    hoje = datetime.now()
    dados = {}

    # 1. Identificação
    nome = re.search(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{5,})', texto_unificado, re.I)
    dados['Nome'] = nome.group(1).strip().split('\n')[0] if nome else "Não encontrado"
    
    # 2. Endereço e CEP (Filtro para evitar confundir com valores)
    cep = re.search(r'(\d{5}-\d{3})', texto_unificado)
    dados['CEP'] = cep.group(1) if cep else "Não encontrado"
    
    rua = re.search(r'(?:RUA|AV|AVENIDA|DR|ESTRADA|LOGRADOURO)[:\s]+([A-Z0-9\s,.-]+)', texto_unificado, re.I)
    dados['Endereço'] = rua.group(0).strip().split('\n')[0] if rua else "Não encontrado"

    # 3. Financeiro (Renda e FGTS Total)
    renda_match = re.search(r'(?:LÍQUIDO|TOTAL|BRUTO)[:\s]*R\$\s?(\d{1,3}(\.\d{3})*,\d{2})', texto_unificado, re.I)
    renda_valor = float(renda_match.group(1).replace('.', '').replace(',', '.')) if renda_match else 0.0
    dados['Renda Extraída'] = f"R$ {renda_valor:,.2f}"

    saldos_fgts = re.findall(r'(?:SALDO|DISPONÍVEL|RESCISÓRIOS)[:\s]*R\$\s?(\d{1,3}(\.\d{3})*,\d{2})', texto_unificado, re.I)
    total_fgts = sum([float(s[0].replace('.', '').replace(',', '.')) for s in saldos_fgts])
    dados['Soma FGTS'] = f"R$ {total_fgts:,.2f}"

    # 4. Análise de Regras Caixa
    alertas = []
    subsidio = calcular_subsidio_mcmv(renda_valor)
    dados['Subsídio Est.'] = f"R$ {subsidio:,.2f}"
    
    # Validade Residência (90 dias)
    datas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto_unificado)
    if datas:
        try:
            data_doc = max([datetime.strptime(d, '%d/%m/%Y') for d in datas])
            dias_vencido = (hoje - data_doc).days
            if dias_vencido > 90:
                alertas.append(f"🔴 DOC ANTIGO ({dias_vencido} dias)")
        except: pass

    # Estabilidade
    adm = re.search(r'(?:ADMISSÃO|ADM)[:\s]*(\d{2}/\d{2}/\d{4})', texto_unificado, re.I)
    if adm:
        dt_adm = datetime.strptime(adm.group(1), '%d/%m/%Y')
        tempo = relativedelta(hoje, dt_adm)
        dados['Tempo Casa'] = f"{tempo.years}a {tempo.months}m"
        if tempo.years < 1: alertas.append("⚠️ Estabilidade < 1 ano")
    else: dados['Tempo Casa'] = "N/A"

    dados['Inconformidades'] = " | ".join(alertas) if alertas else "✅ Pronto para Enviar"
    return dados

# --- UI do Streamlit ---
upload = st.file_uploader("Suba os documentos do cliente (PDFs ou Imagens)", accept_multiple_files=True)

if upload:
    relatorio = []
    for f in upload:
        with st.spinner(f'Processando {f.name}...'):
            paginas_texto = []
            if f.type == "application/pdf":
                imgs = convert_from_bytes(f.read())
                for img in imgs:
                    paginas_texto.append(pytesseract.image_to_string(img, lang='por'))
            else:
                img = Image.open(f)
                paginas_texto.append(pytesseract.image_to_string(img, lang='por'))
            
            res = analisar_processo_completo(paginas_texto)
            res['Arquivo'] = f.name
            relatorio.append(res)

    df = pd.DataFrame(relatorio)
    st.write("### 📊 Análise Técnica de Viabilidade")
    st.dataframe(df, use_container_width=True)

    # Botão de Exportação
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Baixar Planilha para a Caixa", output.getvalue(), file_name="analise_correspondente_final.xlsx")
