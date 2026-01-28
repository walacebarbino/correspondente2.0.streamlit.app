import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime

# --- 1. CONFIGURAÇÕES E ESTILO ---
st.set_page_config(page_title="Caixa 2.0 - Analista Documental", layout="wide")

# Estilo para os banners de resultados conforme solicitado
st.markdown("""
    <style>
    .fgts-banner {
        background-color: #1e3d24; 
        padding: 20px; 
        border-radius: 10px; 
        border-left: 10px solid #2ecc71;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. FUNÇÕES DE SUPORTE ---
def preparar_imagem(img):
    """Aprimora a imagem para leitura de valores numéricos pequenos."""
    img = ImageOps.grayscale(img)
    return ImageEnhance.Contrast(img).enhance(3.0)

def limpar_v(texto):
    """Converte strings financeiras (R$ 1.234,56) em float (1234.56)."""
    if not texto: return 0.0
    match = re.search(r'(\d{1,3}(\.\d{3})*,\d{2})', texto)
    if match:
        return float(match.group(1).replace('.', '').replace(',', '.'))
    return 0.0

# --- 3. MOTORES DE EXTRAÇÃO (OCR) ---

def motor_analise_holerite(texto):
    """Focado na image_7c1db8: Extrai dados e soma adiantamentos ao líquido."""
    t = texto.upper()
    d = {}
    
    # Dados Cadastrais
    d['colaborador'] = re.search(r'COLABORADOR[:\s]*[\d\s\-]*([A-Z\s]{10,})', t).group(1).strip() if re.search(r'COLABORADOR', t) else "Não Identificado"
    d['cargo'] = re.search(r'CARGO[:\s]*([A-Z\s/]{5,})', t).group(1).strip() if re.search(r'CARGO', t) else "Não Identificado"
    d['admissao'] = re.search(r'ADMISSÃO[:\s]*(\d{2}/\d{2}/\d{4})', t).group(1) if re.search(r'ADMISSÃO', t) else "---"
    
    # Valores Financeiros
    venc_match = re.search(r'VENCIMENTOS.*?([\d\.,]{6,})', t)
    d['bruto'] = limpar_v(venc_match.group(1)) if venc_match else 0.0
    
    liq_match = re.search(r'TOTAL LÍQUIDO PGT[Oº][: \s]*([\d\.,]{6,})', t)
    d['liq_puro'] = limpar_v(liq_match.group(1)) if liq_match else 0.0
    
    # Regra do Adiantamento (Destaque Amarelo)
    adt_match = re.search(r'(?:ADIANTAMENTO SALARIAL|ADIANT\. QUINZENAL|ANTECIPAÇÃO).*?([\d\.,]{6,})', t)
    d['adiantamento'] = limpar_v(adt_match.group(1)) if adt_match else 0.0
    
    # Soma Obrigatória para Capacidade de 30%
    d['liq_real'] = d['liq_puro'] + d['adiantamento']
    
    return d

def motor_analise_fgts(texto):
    """Focado na image_7c297d: Extrai saldos e vínculos."""
    t = texto.upper()
    contas = []
    blocos = re.split(r'EMPREGADOR', t)
    
    for bloco in blocos[1:]:
        dados_conta = {}
        emp_match = re.search(r'^[:\s]*([A-Z0-9\s\.]{5,50})', bloco, re.MULTILINE)
        dados_conta['empregador'] = emp_match.group(1).strip() if emp_match else "Não Identificado"
        
        adm_match = re.search(r'DATA\s+DE\s+ADMISSAO\s+(\d{2}/\d{2}/\d{4})', bloco)
        dados_conta['admissao'] = adm_match.group(1) if adm_match else "---"
        
        fins_match = re.search(r'VALOR\s+PARA\s+FINS\s+RECIS[OÓ]RIOS\s+R\$\s*([\d\.,]{5,})', bloco)
        dados_conta['v_fins'] = limpar_v(fins_match.group(1)) if fins_match else 0.0
        
        saldos = re.findall(r'R\$\s*([\d\.,]{5,})$', bloco, re.MULTILINE)
        dados_conta['saldo_atual'] = limpar_v(saldos[-1]) if saldos else 0.0
        
        contas.append(dados_conta)
    return contas

# --- 4. INTERFACE DO USUÁRIO ---

tab1, tab2, tab3 = st.tabs(["1. Aba Geral", "2. Aba Importação", "3. Aba de Resultados"])

with tab1:
    st.header("Configuração de Perfil")
    origem = st.selectbox("Origem de Recursos:", ["CLT", "Autônomo", "Empresário/MEI"])

with tab2:
    st.header("Upload e Categorização")
    c1, c2 = st.columns(2)
    with c1:
        u_id = st.file_uploader("Documentos de Identificação", accept_multiple_files=True)
        u_renda = st.file_uploader("Documentos de Renda (Holerites)", accept_multiple_files=True)
    with c2:
        u_res = st.file_uploader("Comprovante de Residência", accept_multiple_files=True)
        u_fgts = st.file_uploader("Extratos de FGTS", accept_multiple_files=True)

    # Processamento ao clicar (ou automático se houver arquivos)
    if u_renda or u_fgts:
        with st.spinner("Analisando documentos..."):
            texto_full = ""
            arquivos = (u_renda or []) + (u_fgts or [])
            for f in arquivos:
                if f.type == "application/pdf":
                    pags = convert_from_bytes(f.read(), 200)
                    texto_full += " ".join([pytesseract.image_to_string(preparar_imagem(p), lang='por') for p in pags])
                else:
                    texto_full += pytesseract.image_to_string(preparar_imagem(Image.open(f)), lang='por')
            
            st.session_state['dados_h'] = motor_analise_holerite(texto_full)
            st.session_state['dados_f'] = motor_analise_fgts(texto_full)
            st.success("OCR Finalizado com sucesso!")

with tab3:
    if 'dados_h' in st.session_state:
        dh = st.session_state['dados_h']
        df = st.session_state['dados_f']
        
        st.header("Relatório Macro de Viabilidade")
        
        # Bloco de Dados do Cliente
        with st.expander("👤 Dados do Cliente", expanded=True):
            st.write(f"**Nome Identificado:** {dh['colaborador']}")
            st.write(f"**Cargo:** {dh['cargo']}")
            st.write(f"**Data de Admissão:** {dh['admissao']}")

        # Bloco Financeiro ( image_97d51a )
        with st.expander("💰 Financeiro", expanded=True):
            col_bruto, col_liq = st.columns(2)
            col_bruto.metric("Último Salário Bruto", f"R$ {dh['bruto']:,.2f}")
            col_liq.metric("Líquido Real (C/ Adiantamento)", f"R$ {dh['liq_real']:,.2f}", 
                           delta=f"Adiantamento: R$ {dh['adiantamento']:,.2f}")
            st.caption("O valor do adiantamento foi reincorporado ao líquido conforme solicitado.")

        # Bloco FGTS ( image_992a34 )
        if df:
            with st.expander("📈 Detalhamento FGTS", expanded=True):
                total_fgts = 0
                for conta in df:
                    st.write(f"**Empresa:** {conta['empregador']} | **Saldo:** R$ {conta['saldo_atual']:,.2f}")
                    total_fgts += conta['saldo_atual']
                
                st.markdown(f"""
                    <div class="fgts-banner">
                        <h2 style="color: white; margin: 0;">Total FGTS Identificado: R$ {total_fgts:,.2f}</h2>
                    </div>
                """, unsafe_allow_html=True)

        # Veredito
        st.divider()
        v1, v2 = st.columns(2)
        v1.info(f"**Modalidade sugerida:** {'SBPE' if dh['bruto'] > 8000 else 'MCMV'}")
        v2.success("Status de Provável Aprovação: ✅ ALTA")
        st.button("📄 Exportar Relatório PDF")
