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

def analisar_documento_completo(texto):
    dados = {}
    hoje = datetime.now()

    # --- EXTRAÇÃO DE IDENTIFICAÇÃO ---
    nome = re.search(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{5,})', texto, re.I)
    dados['Nome'] = nome.group(1).strip().split('\n')[0] if nome else "Não encontrado"
    
    cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto)
    dados['CPF'] = cpf.group() if cpf else "Não encontrado"

    # --- EXTRAÇÃO DE ENDEREÇO (Padrão para evitar valores) ---
    cep_match = re.search(r'(\d{5}-\d{3})', texto)
    dados['CEP'] = cep_match.group(1) if cep_match else "Não encontrado"
    rua_match = re.search(r'(?:RUA|AV|AVENIDA|DR|ESTRADA|LOGRADOURO)[:\s]+([A-Z0-9\s,.-]+)', texto, re.I)
    dados['Endereço'] = rua_match.group(0).strip().split('\n')[0] if rua_match else "Não encontrado"

    # --- EXTRAÇÃO DE RENDA E TRABALHO ---
    adm_match = re.search(r'(?:ADMISSÃO|ADM|DATA ADM)[:\s]*(\d{2}/\d{2}/\d{4})', texto, re.I)
    dados['Data Admissão'] = adm_match.group(1) if adm_match else "Não encontrado"
    
    renda_match = re.search(r'(?:LÍQUIDO|TOTAL|BRUTO)[:\s]*R\$\s?(\d{1,3}(\.\d{3})*,\d{2})', texto, re.I)
    renda_str = renda_match.group(1) if renda_match else "0,00"
    dados['Renda'] = f"R$ {renda_str}"

    # --- EXTRAÇÃO DE FGTS ---
    # Busca por saldo total disponível no extrato
    fgts_match = re.search(r'(?:SALDO|TOTAL DISPONÍVEL|FINS RESCISÓRIOS)[:\s]*R\$\s?(\d{1,3}(\.\d{3})*,\d{2})', texto, re.I)
    saldo_fgts = fgts_match.group(1) if fgts_match else "0,00"
    dados['Saldo FGTS'] = f"R$ {saldo_fgts}"

    # --- LÓGICA DE REGRAS CAIXA ---
    alertas = []
    
    # 1. Validade do Comprovante (90 dias)
    datas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto)
    if datas:
        try:
            data_doc = max([datetime.strptime(d, '%d/%m/%Y') for d in datas])
            dias = (hoje - data_doc).days
            if "Neoenergia" in texto or "CEP" in texto: # Filtro simples para saber se é conta
                if dias > 90: alertas.append(f"🔴 Comprovante Residência Antigo ({dias} dias)")
        except: pass

    # 2. Estabilidade (12 meses)
    if dados['Data Admissão'] != "Não encontrado":
        dt_adm = datetime.strptime(dados['Data Admissão'], '%d/%m/%Y')
        tempo = relativedelta(hoje, dt_adm)
        dados['Tempo Casa'] = f"{tempo.years}a {tempo.months}m"
        if tempo.years < 1: alertas.append("⚠️ Estabilidade < 1 ano")
    
    # 3. Faixas MCMV
    try:
        val_renda = float(renda_str.replace('.', '').replace(',', '.'))
        if val_renda <= 2850: dados['Enquadramento'] = "Faixa 1 (MCMV)"
        elif val_renda <= 4700: dados['Enquadramento'] = "Faixa 2 (MCMV)"
        elif val_renda <= 8000: dados['Enquadramento'] = "Faixa 3 (MCMV)"
        else: dados['Enquadramento'] = "SBPE"
    except: dados['Enquadramento'] = "Verificar Renda"

    dados['Inconformidades'] = " | ".join(alertas) if alertas else "✅ Pronto para Montagem"
    return dados

# --- INTERFACE ---
upload = st.file_uploader("Suba Documentos (PDF, JPG, PNG)", accept_multiple_files=True)
if upload:
    lista_analise = []
    for arq in upload:
        with st.spinner(f'Analisando {arq.name}...'):
            if arq.type == "application/pdf":
                paginas = convert_from_bytes(arq.read())
                img = paginas[0]
            else:
                img = Image.open(arq)
            
            texto_ocr = pytesseract.image_to_string(img, lang='por')
            resultado = analisar_documento_completo(texto_ocr)
            resultado['Arquivo'] = arq.name
            lista_analise.append(resultado)

    df = pd.DataFrame(lista_analise)
    st.write("### 🚀 Parecer Técnico - Correspondente 2.0")
    st.dataframe(df, use_container_width=True)
    
    # Exportação
    df.to_excel("relatorio_caixa_completo.xlsx", index=False)
    st.download_button("📥 Baixar Planilha Analisada", open("relatorio_caixa_completo.xlsx", "rb"), file_name="analise_processo.xlsx")
