import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
import cv2
import numpy as np
from pdf2image import convert_from_bytes
from datetime import datetime

st.set_page_config(page_title="Parceria 2.0 - Analista Expert", layout="wide")
st.title("🏦 Parceria 2.0: Analista de Crédito & Documentação")

def tratar_imagem(imagem_pil):
    """Aplica filtros para melhorar a legibilidade do OCR"""
    # Converte para escala de cinza
    img = ImageOps.grayscale(imagem_pil)
    # Aumenta o contraste
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    return img

def extrair_dados_pro(textos):
    full_text = " ".join(textos).upper()
    dados = {}
    
    # 1. IDENTIFICAÇÃO E ESTADO CIVIL
    nome = re.search(r'(?:NOME|CLIENTE|PROPOENTE|COLABORADOR)[:\s\n]+([A-Z\s]{10,})', full_text)
    dados['Nome'] = nome.group(1).split('\n')[0].strip() if nome else "Não identificado"
    
    est_civil = re.search(r'\b(SOLTEIRO|CASADO|DIVORCIADO|VIÚVO|UNIÃO ESTÁVEL|SOLTEIRA|CASADA|DIVORCIADA|VIÚVA)\b', full_text)
    dados['Estado Civil'] = est_civil.group(1) if est_civil else "Verificar Certidão"

    # 2. CEP RESIDENCIAL (Refinado)
    # Busca o padrão de CEP, priorizando o que vier após palavras de endereço
    ceps = re.findall(r'\d{5}-\d{3}', full_text)
    dados['CEP'] = ceps[0] if ceps else "Não encontrado"

    # 3. FINANCEIRO DETALHADO (Bruto, Descontos, Saldo)
    # Captura Salário Bruto
    bruto_match = re.findall(r'(?:VENCIMENTOS|TOTAL VENCIMENTOS|VALOR BRUTO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    val_bruto = bruto_match[0] if bruto_match else "0,00"
    
    # Captura Descontos
    desc_match = re.findall(r'(?:TOTAL DESCONTOS|DESCONTOS|VALOR DESCONTOS)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    val_desc = desc_match[0] if desc_match else "0,00"
    
    # Captura Líquido Final
    liq_match = re.findall(r'(?:LÍQUIDO|TOTAL LÍQUIDO|LÍQUIDO PGTO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    val_liq = liq_match[-1] if liq_match else "0,00"

    dados['Salário Bruto'] = f"R$ {val_bruto}"
    dados['Total Descontos'] = f"R$ {val_desc}"
    dados['Saldo Líquido'] = f"R$ {val_liq}"

    return dados

# --- INTERFACE ---
st.markdown("### 📑 Upload de Documentos para Análise")
upload = st.file_uploader("Suba os arquivos (PDF, JPG, PNG)", accept_multiple_files=True)

if upload:
    all_texts = []
    for f in upload:
        with st.spinner(f'Processando e limpando {f.name}...'):
            if f.type == "application/pdf":
                paginas = convert_from_bytes(f.read())
                for p in paginas:
                    img_tratada = tratar_imagem(p)
                    all_texts.append(pytesseract.image_to_string(img_tratada, lang='por'))
            else:
                img_tratada = tratar_imagem(Image.open(f))
                all_texts.append(pytesseract.image_to_string(img_tratada, lang='por'))
    
    if all_texts:
        res = extrair_dados_pro(all_texts)
        
        # EXIBIÇÃO EM PAINEL
        st.write("---")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.subheader("👤 Identificação")
            st.metric("Cliente", res['Nome'])
            st.info(f"**Estado Civil:** {res['Estado Civil']}")
            st.info(f"**CEP:** {res['CEP']}")

        with c2:
            st.subheader("💰 Financeiro")
            st.write(f"**Bruto:** {res['Salário Bruto']}")
            st.write(f"**Descontos:** {res['Total Descontos']}")
            st.metric("Líquido Final", res['Saldo Líquido'], delta="Saldo em conta")

        with c3:
            st.subheader("📊 Capacidade de Pagamento")
            try:
                # Cálculo simples de margem consignável ou parcela (30%)
                liquido_num = float(res['Saldo Líquido'].replace('R$ ', '').replace('.', '').replace(',', '.'))
                parcela_max = liquido_num * 0.3
                st.metric("Parcela Máxima (30%)", f"R$ {parcela_max:,.2f}")
                st.caption("Estimativa baseada no líquido identificado.")
            except:
                st.write("Não foi possível calcular a margem.")

        # Tabela para conferência
        st.write("---")
        st.dataframe(pd.DataFrame([res]), use_container_width=True)
