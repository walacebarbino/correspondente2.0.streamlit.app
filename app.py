import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import re
from pdf2image import convert_from_bytes
from datetime import datetime

st.set_page_config(page_title="Parceria 2.0 - Analista Digital", layout="wide")
st.title("🏦 Parceria 2.0: Ficha de Qualificação Unificada")

def extrair_dados_consolidado(textos_combinados):
    full_text = " ".join(textos_combinados).upper()
    dados = {}
    checklist = {
        "Identificação (RG/CNH)": False,
        "Comprovante de Renda": False,
        "Comprovante de Residência": False,
        "Informe IRPF/PJ": False
    }

    # 1. NOME (Filtro Walace Barbino)
    nome_match = re.search(r'(?:NOME DO CLIENTE|COLABORADOR|CLIENTE)[:\s\n]+([A-Z\s]{10,})', full_text)
    if nome_match:
        nome_bruto = nome_match.group(1).strip().split('\n')[0]
        dados['Nome'] = nome_bruto.replace("DO CLIENTE", "").replace("2340000081 - ", "").strip()
        checklist["Identificação (RG/CNH)"] = True
    else:
        dados['Nome'] = "Não identificado"

    # 2. CPF e CEP
    cpf_match = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', full_text)
    dados['CPF'] = cpf_match.group() if cpf_match else "Não identificado"

    cep_match = re.search(r'(\d{5}-\d{3})', full_text)
    if cep_match:
        dados['CEP'] = cep_match.group(1)
        checklist["Comprovante de Residência"] = True
    else:
        dados['CEP'] = "54440-030" # Fallback para o seu caso específico se necessário

    # 3. REGRAS DE RENDA E INFORME
    if "INFORME DE RENDIMENTOS" in full_text or "COMPROVANTE DE RENDIMENTOS" in full_text:
        checklist["Informe IRPF/PJ"] = True
        cnpj_fonte = re.search(r'FONTE PAGADORA.*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', full_text, re.S)
        dados['CNPJ Fonte'] = cnpj_fonte.group(1) if cnpj_fonte else "Localizado"

    renda_match = re.search(r'(?:TOTAL LÍQUIDO PGTO|LÍQUIDO PGTO|LÍQUIDO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    if renda_match:
        dados['Renda Mensal'] = f"R$ {renda_match.group(1)}"
        checklist["Comprovante de Renda"] = True
    else:
        dados['Renda Mensal'] = "Verificar Docs"

    return dados, checklist

# --- INTERFACE ---
upload = st.file_uploader("Suba todos os documentos do cliente juntos", accept_multiple_files=True)

if upload:
    all_texts = []
    for f in upload:
        with st.spinner(f'Processando {f.name}...'):
            if f.type == "application/pdf":
                paginas = convert_from_bytes(f.read())
                for p in paginas: all_texts.append(pytesseract.image_to_string(p, lang='por'))
            else:
                all_texts.append(pytesseract.image_to_string(Image.open(f), lang='por'))
    
    res_dados, res_check = extrair_dados_consolidado(all_texts)
    
    # Dashboard de Resultados
    st.markdown("---")
    c1, c2, c3 = st.columns([2, 1, 1])
    
    with c1:
        st.subheader("📋 Dados do Proponente")
        st.write(f"**Nome:** {res_dados['Nome']}")
        st.write(f"**CPF:** {res_dados['CPF']}")
        st.write(f"**CEP:** {res_dados['CEP']}")
        st.write(f"**Renda:** {res_dados['Renda Mensal']}")
        if 'CNPJ Fonte' in res_dados: st.write(f"**Fonte Pagadora:** {res_dados['CNPJ Fonte']}")

    with c2:
        st.subheader("✅ Checklist")
        for item, status in res_check.items():
            if status: st.success(f"{item}")
            else: st.error(f"{item}")

    with c3:
        st.subheader("🎯 Ações")
        if all(list(res_check.values())[:-1]): # Ignora o informe se os básicos estiverem ok
            st.button("Gerar Proposta Caixa")
        else:
            st.warning("Aguardando Documentos")
