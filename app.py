import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import re
from pdf2image import convert_from_bytes
from datetime import datetime
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Parceria 2.0 - Gestão de Processos", layout="wide")
st.title("🏦 Parceria 2.0: Analista Digital & Checklist")

def analisar_macro_e_checklist(textos_combinados):
    full_text = " ".join(textos_combinados).upper()
    hoje = datetime.now()
    dados = {}
    checklist = {
        "Identificação (RG/CNH)": False,
        "Comprovativo de Renda": False,
        "Comprovativo de Residência": False,
        "Extrato FGTS": False
    }

    # --- EXTRAÇÃO DE DADOS (LÓGICA CONSOLIDADA) ---
    nome = re.search(r'(?:NOME|COLABORADOR|CLIENTE)[:\s-]*([A-Z\s]{10,})', full_text)
    dados['Nome'] = nome.group(1).split('\n')[0].strip() if nome else "Não identificado"
    
    cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', full_text)
    dados['CPF'] = cpf.group() if cpf else "Não identificado"

    # --- VERIFICAÇÃO DO CHECKLIST ---
    if "REGISTRO" in full_text or "IDENTIDADE" in full_text or "CNH" in full_text:
        checklist["Identificação (RG/CNH)"] = True
    
    if "RECIBO DE PAGAMENTO" in full_text or "CONTRACHEQUE" in full_text or "SALÁRIO" in full_text:
        checklist["Comprovativo de Renda"] = True
        # Extração de Renda
        renda_match = re.findall(r'(?:LÍQUIDO|TOTAL)[:\s]*R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
        dados['Renda'] = f"R$ {renda_match[-1]}" if renda_match else "R$ 0,00"
    else:
        dados['Renda'] = "R$ 0,00"

    if "NEOENERGIA" in full_text or "CONTA DE LUZ" in full_text or "COMPROVANTE DE RESIDÊNCIA" in full_text:
        checklist["Comprovativo de Residência"] = True
        cep = re.search(r'(\d{5}-\d{3})', full_text)
        dados['CEP'] = cep.group(1) if cep else "Não encontrado"
    else:
        dados['CEP'] = "Não encontrado"

    if "FGTS" in full_text or "FUNDO DE GARANTIA" in full_text:
        checklist["Extrato FGTS"] = True
        fgts_vals = re.findall(r'(?:FGTS)[:\s]*R?\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
        total_fgts = sum([float(v.replace('.','').replace(',','.')) for v in fgts_vals])
        dados['FGTS'] = f"R$ {total_fgts:,.2f}"
    else:
        dados['FGTS'] = "R$ 0,00"

    return dados, checklist

# --- INTERFACE ---
st.sidebar.header("Configurações")
st.sidebar.info("Sobe todos os documentos de uma vez para análise completa.")

upload = st.file_uploader("Arraste os documentos do cliente (PDF/JPG)", accept_multiple_files=True)

if upload:
    all_texts = []
    for f in upload:
        with st.spinner(f'Processando {f.name}...'):
            if f.type == "application/pdf":
                pages = convert_from_bytes(f.read())
                for p in pages: all_texts.append(pytesseract.image_to_string(p, lang='por'))
            else:
                all_texts.append(pytesseract.image_to_string(Image.open(f), lang='por'))
    
    res_dados, res_checklist = analisar_macro_e_checklist(all_texts)
    
    # Exibição de Resultados
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📋 Ficha Consolidada do Cliente")
        st.write(f"**Nome:** {res_dados['Nome']}")
        st.write(f"**CPF:** {res_dados['CPF']}")
        st.write(f"**Renda Identificada:** {res_dados['Renda']}")
        st.write(f"**Saldo FGTS Estimado:** {res_dados['FGTS']}")
        st.write(f"**CEP:** {res_dados['CEP']}")
        
    with col2:
        st.subheader("✅ Checklist de Documentos")
        for item, status in res_checklist.items():
            if status:
                st.success(f"{item}: OK")
            else:
                st.error(f"{item}: FALTANDO")

    # Alerta de Próximos Passos
    if all(res_checklist.values()):
        st.balloons()
        st.success("🚀 Documentação completa! O processo pode ser montado para a Caixa.")
    else:
        st.warning("⚠️ Atenção: O checklist indica documentos em falta ou ilegíveis.")
