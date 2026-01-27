import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="Analista de Crédito 2.0", layout="wide")
st.title("🏦 Analista de Crédito Inteligente")

# --- FUNÇÕES DE TRATAMENTO E EXTRAÇÃO ---

def tratar_imagem(imagem_pil):
    """Melhora a imagem para leitura de endereços e valores"""
    img = ImageOps.grayscale(imagem_pil)
    enhancer = ImageEnhance.Contrast(img)
    return enhancer.enhance(2.5)

def extrair_dados_completo(textos_paginas):
    full_text = " ".join(textos_paginas).upper()
    # Limpeza de ruído comum em OCR
    full_text = full_text.replace('|', 'I').replace('$', 'S')
    
    dados = {
        "Nome": "Não encontrado",
        "CPF": "Não encontrado",
        "RG": "Não encontrado",
        "CNH": "Não encontrado",
        "Endereço": "Não encontrado",
        "CEP": "Não encontrado",
        "Estado Civil": "Verificar Certidão",
        "Renda Bruta": 0.0,
        "Renda Líquida": 0.0,
        "Descontos": 0.0
    }

    # 1. Identificação (Nome, CPF, RG, CNH)
    nome_match = re.search(r'(?:NOME|NOME DO CLIENTE|COLABORADOR|NOME DO BENEFICIARIO)[:\s\n]+([A-Z\s]{10,})', full_text)
    if nome_match:
        dados["Nome"] = nome_match.group(1).split('\n')[0].strip()

    cpf_match = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', full_text)
    if cpf_match:
        dados["CPF"] = cpf_match.group()

    rg_match = re.search(r'(?:RG|IDENTIDADE)[:\s]*([\d\.X-]{7,12})', full_text)
    if rg_match:
        dados["RG"] = rg_match.group(1).strip()

    # 2. Endereço Completo e CEP (Refinado)
    # Busca por CEP explicitamente ou padrão numérico
    cep_match = re.search(r'(?:CEP)[:\s]*(\d{5}-\d{3})|(\d{5}-\d{3})', full_text)
    if cep_match:
        dados["CEP"] = cep_match.group(1) if cep_match.group(1) else cep_match.group(2)

    # Busca endereço aproximado baseado em palavras-chave
    end_match = re.search(r'(?:ENDEREÇO|LOGRADOURO|RUA|AV)[:\s\n]+([^,]+,[^,]+,[^,]+)', full_text)
    if end_match:
        dados["Endereço"] = end_match.group(1).strip()

    # 3. Estado Civil
    est_civil = re.search(r'\b(SOLTEIRO|CASADO|DIVORCIADO|VIÚVO|UNIÃO ESTÁVEL|SOLTEIRA|CASADA|DIVORCIADA|VIÚVA)\b', full_text)
    if est_civil:
        dados["Estado Civil"] = est_civil.group(1)

    # 4. Análise Financeira (Correção de busca de valores)
    # Procura valores após palavras-chave financeiras
    bruto = re.findall(r'(?:BRUTO|VENCIMENTOS|TOTAL PROVENTOS)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    desc = re.findall(r'(?:DESCONTOS|TOTAL DESCONTOS)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    liq = re.findall(r'(?:LÍQUIDO|VALOR LÍQUIDO|PAGAMENTO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)

    if bruto: dados["Renda Bruta"] = float(bruto[0].replace('.', '').replace(',', '.'))
    if desc: dados["Descontos"] = float(desc[0].replace('.', '').replace(',', '.'))
    if liq: dados["Renda Líquida"] = float(liq[-1].replace('.', '').replace(',', '.'))

    return dados

# --- INTERFACE STREAMLIT ---

st.subheader("📂 Documentos Importados e Checklist")
upload = st.file_uploader("Suba os documentos do cliente (PDFs ou Imagens)", accept_multiple_files=True)

if upload:
    all_texts = []
    file_info = []
    
    # Processamento dos arquivos
    for f in upload:
        with st.spinner(f'Processando {f.name}...'):
            text_per_file = ""
            if f.type == "application/pdf":
                paginas = convert_from_bytes(f.read())
                for p in paginas:
                    text_per_file += pytesseract.image_to_string(tratar_imagem(p), lang='por')
            else:
                img = Image.open(f)
                text_per_file = pytesseract.image_to_string(tratar_imagem(img), lang='por')
            
            all_texts.append(text_per_file)
            
            # Checklist por arquivo
            status = "🔴 Pendente"
            upper_text = text_per_file.upper()
            if "CPF" in upper_text or "CNH" in upper_text or "IDENTIDADE" in upper_text:
                status = "🟢 Identificação OK"
            elif "RENDIMENTOS" in upper_text or "CONTRACHEQUE" in upper_text or "VENCIMENTOS" in upper_text:
                status = "🟢 Renda OK"
            elif "RUA" in upper_text or "CEP" in upper_text or "COMPROVANTE" in upper_text:
                status = "🟢 Endereço OK"
            
            file_info.append({"Arquivo": f.name, "Tamanho": f"{f.size/1024:.1f} KB", "Status": status})

    # 1. Lista de Documentos Maior com Checklist [Ajuste Solicitado]
    st.table(file_info)

    if all_texts:
        res = extrair_dados_completo(all_texts)
        
        st.divider()
        
        # 2. Identificação Proponente Completa [Ajuste Solicitado]
        st.subheader("👤 Identificação do Proponente")
        c1, c2 = st.columns(2)
        
        with c1:
            st.write(f"**Nome:** {res['Nome']}")
            st.write(f"**CPF:** {res['CPF']}")
            st.write(f"**RG:** {res['RG']}")
            st.write(f"**CNH:** {res['CNH']}")
        
        with c2:
            st.write(f"**Estado Civil:** {res['Estado Civil']}")
            st.write(f"**CEP:** {res['CEP']}")
            st.write(f"**Endereço Completo:** {res['Endereço']}")

        st.divider()

        # 3. Análise Financeira [Ajuste Solicitado]
        st.subheader("💰 Análise Financeira")
        f1, f2, f3 = st.columns(3)
        
        f1.metric("Renda Bruta", f"R$ {res['Renda Bruta']:,.2f}")
        f2.metric("Total Descontos", f"R$ {res['Descontos']:,.2f}")
        f3.metric("Renda Líquida Final", f"R$ {res['Renda Líquida']:,.2f}")
        
        if res['Renda Líquida'] == 0:
            st.warning("⚠️ Atenção: Renda não identificada automaticamente. Verifique os documentos de rendimentos.")

# 4. Simulação de Financiamento Removida [Ajuste Solicitado]
