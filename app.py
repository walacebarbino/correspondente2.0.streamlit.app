import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime

# --- CONFIGURAÇÃO DE INTERFACE ---
st.set_page_config(page_title="Caixa Correspondente 2.0", layout="wide")

# --- FUNÇÕES DE PROCESSAMENTO ---
def limpar_v(texto):
    if not texto: return 0.0
    # Remove R$ e limpa formatação brasileira para cálculo
    match = re.search(r'(\d{1,3}(\.\d{3})*,\d{2})', texto)
    if match:
        return float(match.group(1).replace('.', '').replace(',', '.'))
    return 0.0

# --- MOTOR OCR ESPECIALIZADO ---
def motor_analise_caixa_v8(texto_full):
    t = texto_full.upper()
    d = {}

    # 1. EXTRAÇÃO HOLERITE (Conforme image_7c1db8)
    d['colaborador'] = re.search(r'COLABORADOR[:\s]*[\d\s\-]*([A-Z\s]{10,})', t).group(1).strip() if re.search(r'COLABORADOR', t) else "Não Identificado"
    d['cargo'] = re.search(r'CARGO[:\s]*([A-Z\s]{5,})', t).group(1).strip() if re.search(r'CARGO', t) else "Não Identificado"
    d['admissao_h'] = re.search(r'ADMISSÃO[:\s]*(\d{2}/\d{2}/\d{4})', t).group(1) if re.search(r'ADMISSÃO', t) else "---"
    
    # Valores do Holerite
    bruto_match = re.search(r'VENCIMENTOS.*?([\d\.,]{6,})', t)
    d['bruto'] = limpar_v(bruto_match.group(1)) if bruto_match else 0.0
    
    liq_pgto_match = re.search(r'TOTAL LÍQUIDO PGT[Oº][: \s]*([\d\.,]{6,})', t)
    d['liq_pgto'] = limpar_v(liq_pgto_match.group(1)) if liq_pgto_match else 0.0
    
    # REGRA DE OURO: Adiantamento (Destaque amarelo image_7c1db8)
    adt_match = re.search(r'(?:ADIANTAMENTO SALARIAL|ANTECIPAÇÃO).*?([\d\.,]{6,})', t)
    d['adiantamento'] = limpar_v(adt_match.group(1)) if adt_match else 0.0
    
    # SOMA OBRIGATÓRIA
    d['liq_real'] = d['liq_pgto'] + d['adiantamento']

    # 2. EXTRAÇÃO FGTS (Conforme image_7c297d)
    d['empregador'] = re.search(r'EMPREGADOR[:\s]*([A-Z0-9\s\.]{5,})', t).group(1).strip() if re.search(r'EMPREGADOR', t) else "Não Identificado"
    
    fins_rescisorios = re.search(r'VALOR PARA FINS RECISÓRIOS[:\s]*R\$\s*([\d\.,]{5,})', t)
    d['fgts_fins'] = limpar_v(fins_rescisorios.group(1)) if fins_rescisorios else 0.0
    
    # Saldo Atual (Último valor da coluna TOTAL)
    saldos = re.findall(r'([\d\.,]{5,})$', t, re.MULTILINE)
    d['fgts_saldo_atual'] = limpar_v(saldos[-1]) if saldos else 0.0

    return d

# --- INTERFACE POR ABAS ---
tab_import, tab_result = st.tabs(["2. Aba Importação", "3. Aba de Resultados"])

with tab_import:
    u_renda = st.file_uploader("Documentos de Renda (Holerites)", accept_multiple_files=True)
    u_fgts = st.file_uploader("Extratos de FGTS", accept_multiple_files=True)
    
    texto_total = ""
    if st.button("Analisar Documentos"):
        for f in (u_renda or []) + (u_fgts or []):
            if f.type == "application/pdf":
                pags = convert_from_bytes(f.read(), 200)
                txt = " ".join([pytesseract.image_to_string(p, lang='por') for p in pags])
            else:
                txt = pytesseract.image_to_string(Image.open(f), lang='por')
            texto_total += " " + txt
        
        st.session_state['res'] = motor_analise_caixa_v8(texto_total)
        st.success("Análise Concluída!")

with tab_result:
    if 'res' in st.session_state:
        r = st.session_state['res']
        
        # Estilização do Relatório (Conforme image_992ab3 e image_97d51a)
        st.header("Relatório Macro de Viabilidade")
        
        with st.expander("👤 Dados Cliente", expanded=True):
            st.write(f"**Nome completo:** {r['colaborador']}")
            st.write(f"**Cargo/Função:** {r['cargo']}")
            st.write(f"**Tempo de casa:** {r['admissao_h']} (Admissão)")

        with st.expander("💰 Financeiro", expanded=True):
            col1, col2 = st.columns(2)
            col1.metric("Média Salarial Bruta", f"R$ {r['bruto']:,.2f}")
            col1.metric("Último Salário Bruto", f"R$ {r['bruto']:,.2f}")
            
            col2.metric("Média Salarial Líquida", f"R$ {r['liq_pgto']:,.2f}")
            col2.metric("Último Líquido Real", f"R$ {r['liq_real']:,.2f}", delta=f"Adiant.: R$ {r['adiantamento']:,.2f}")
            st.caption("↑ C/ Adiantamento (Reincorporado)")

        with st.expander("📈 FGTS (Vínculos Identificados)", expanded=True):
            st.info(f"**Empregador:** {r['empregador']}")
            st.write(f"**Valor Fins Rescisórios:** R$ {r['fgts_fins']:,.2f}")
            st.write(f"**Saldo Atual:** R$ {r['fgts_saldo_atual']:,.2f}")
            
            st.markdown(f"""
                <div style="background-color: #004d1a; padding: 10px; border-radius: 5px;">
                    <b style="color: white;">Total FGTS Identificado: R$ {r['fgts_saldo_atual']:,.2f}</b>
                </div>
            """, unsafe_allow_html=True)

        # VEREDITO FINAL (Conforme image_992a34)
        st.divider()
        st.subheader(f"Status de Provável Aprovação: {'✅ ALTA' if r['liq_real'] > 0 else '❌ DADOS INCOMPLETOS'}")
        st.button("📄 Gerar Impressão / Relatório PDF")
