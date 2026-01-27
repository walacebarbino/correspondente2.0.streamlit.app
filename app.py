import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import re
from pdf2image import convert_from_bytes

st.set_page_config(page_title="Analista de Crédito 2.0", layout="wide")
st.title("🏦 Sistema de Análise Técnica de Viabilidade")

def extrair_dados_avancados(textos):
    full_text = " ".join(textos).upper()
    dados = {}
    
    # --- 1. ANÁLISE DETALHADA DO CONTRACHEQUE ---
    # Busca Salário Bruto (Vencimentos Totais)
    bruto = re.findall(r'(?:TOTAL VENCIMENTOS|VALOR BRUTO|VENCIMENTOS)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    dados['Salário Bruto'] = f"R$ {bruto[0]}" if bruto else "Não identificado"
    
    # Busca Total de Descontos
    descontos = re.findall(r'(?:TOTAL DESCONTOS|DESCONTOS)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    dados['Total Descontos'] = f"R$ {descontos[0]}" if descontos else "Não identificado"
    
    # Saldo Líquido Final (O que cai na conta)
    liquido = re.findall(r'(?:LÍQUIDO|TOTAL LÍQUIDO|VALOR LÍQUIDO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    dados['Saldo Líquido'] = f"R$ {liquido[-1]}" if liquido else "R$ 0,00"

    # --- 2. REFINAMENTO DE CEP (PADRÃO UNIVERSAL) ---
    # Busca qualquer CEP que não seja o da empresa (geralmente o segundo ou terceiro CEP encontrado no bolo de docs)
    ceps_encontrados = re.findall(r'\d{5}-\d{3}', full_text)
    # Filtra CEPs comuns de empresas conhecidas se necessário, ou pega o que estiver perto de "ENDEREÇO"
    dados['CEP Residencial'] = ceps_encontrados[0] if ceps_encontrados else "Não encontrado"

    # --- 3. ESTADO CIVIL (CERTIDÕES/DOCUMENTOS) ---
    estado_civil_match = re.search(r'(SOLTEIRO|CASADO|DIVORCIADO|VIÚVO|UNIÃO ESTÁVEL)', full_text)
    dados['Estado Civil'] = estado_civil_match.group(1) if estado_civil_match else "Não identificado"

    # --- DADOS BÁSICOS ---
    nome = re.search(r'(?:NOME|CLIENTE|PROPOENTE)[:\s\n]+([A-Z\s]{10,})', full_text)
    dados['Nome'] = nome.group(1).split('\n')[0].strip() if nome else "Não identificado"

    return dados

# --- INTERFACE ---
upload = st.file_uploader("Suba a documentação completa (PDF/JPG/PNG)", accept_multiple_files=True)

if upload:
    all_texts = []
    for f in upload:
        if f.type == "application/pdf":
            paginas = convert_from_bytes(f.read())
            for p in paginas: all_texts.append(pytesseract.image_to_string(p, lang='por'))
        else:
            all_texts.append(pytesseract.image_to_string(Image.open(f), lang='por'))
    
    res = extrair_dados_avancados(all_texts)
    
    # EXIBIÇÃO ORGANIZADA
    st.subheader("📋 Ficha de Análise de Crédito")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("### Identificação")
        st.info(f"**Cliente:** {res['Nome']}")
        st.info(f"**Estado Civil:** {res['Estado Civil']}")
        st.info(f"**CEP Identificado:** {res['CEP Residencial']}")
        
    with col2:
        st.write("### Financeiro (Contracheque)")
        st.success(f"**Salário Bruto:** {res['Salário Bruto']}")
        st.error(f"**Total Descontos:** {res['Total Descontos']}")
        st.metric("Saldo Líquido Final", res['Saldo Líquido'])

    # Tabela para conferência rápida
    st.write("---")
    st.write("### Resumo para Exportação")
    st.dataframe(pd.DataFrame([res]))
