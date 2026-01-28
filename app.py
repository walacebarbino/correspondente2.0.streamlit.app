import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime

st.set_page_config(page_title="Correspondente 2.0", layout="wide")

# --- FUNÇÕES DE TRATAMENTO ---
def tratar_documento(img):
    img = ImageOps.grayscale(img)
    return ImageEnhance.Contrast(img).enhance(3.0)

def extrair_valor(texto):
    if not texto: return 0.0
    val = re.sub(r'[^\d,]', '', texto).replace(',', '.')
    try: return float(val)
    except: return 0.0

# --- MOTOR DE ANÁLISE ---
def processar_analise(texto_completo):
    t = texto_completo.upper()
    d = {}

    # 1. Identificação Completa
    d['nome'] = re.search(r'(?:NOME|CLIENTE)[:\s]+([A-Z\s]{10,})', t).group(1).split('\n')[0].strip() if re.search(r'(?:NOME|CLIENTE)[:\s]+([A-Z\s]{10,})', t) else "N/D"
    d['cpf'] = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t).group(1) if re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t) else "N/D"
    d['est_civil'] = re.search(r'(SOLTEIRO|CASADO|DIVORCIADO|VIUVO)', t).group(1) if re.search(r'(SOLTEIRO|CASADO|DIVORCIADO|VIUVO)', t) else "N/D"

    # 2. Residência (Filtro Anti-CNPJ/Sujeira)
    ceps = re.findall(r'(\d{5}-\d{3})', t)
    # Pega o CEP que não seja da Neoenergia (Exemplo de trava lógica)
    d['cep'] = [c for c in ceps if c != "50050-902"][0] if ceps else "N/D"
    
    # Busca endereço ignorando linhas com CNPJ
    linhas = t.split('\n')
    d['endereco'] = next((l.strip() for l in linhas if "RUA" in l and "CNPJ" not in l), "Não encontrado")

    # 3. Renda (Regra do Adiantamento)
    brutos = re.findall(r'(?:BRUTO|VENCIMENTOS)[:\s]*([\d\.,]{5,})', t)
    liquidos = re.findall(r'(?:LIQUIDO)[:\s]*([\d\.,]{5,})', t)
    adiantos = re.findall(r'(?:ADIANTAMENTO|VALE)[:\s]*([\d\.,]{5,})', t)

    val_bruto = extrair_valor(brutos[-1]) if brutos else 0.0
    val_liq = extrair_valor(liquidos[-1]) if liquidos else 0.0
    val_adi = extrair_valor(adiantos[-1]) if adiantos else 0.0

    d['ultimo_bruto'] = val_bruto
    d['liq_real'] = val_liq + val_adi # Reincorporação do adiantamento
    d['cargo'] = re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]+)', t).group(1).split('\n')[0].strip() if re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]+)', t) else "N/D"

    # 4. FGTS (Consolidação de Múltiplos Docs)
    saldos = re.findall(r'VALOR PARA FINS RESCISORIOS.*?([\d\.,]{5,})', t)
    d['fgts_lista'] = [extrair_valor(s) for s in saldos]
    d['fgts_total'] = sum(d['fgts_lista'])

    return d

# --- INTERFACE ---
tab1, tab2, tab3 = st.tabs(["Geral", "Importação", "Resultados"])

with tab1:
    origem = st.selectbox("Origem de Recursos", ["CLT", "Autônomo", "Empresário"])

with tab2:
    arquivos = st.file_uploader("Subir Dossiê", accept_multiple_files=True)
    if arquivos:
        st.write("✅ Documentos recebidos e categorizados.")
        textos_ocr = []
        for f in arquivos:
            if f.type == "application/pdf":
                paginas = convert_from_bytes(f.read(), 200)
                for p in paginas: textos_ocr.append(pytesseract.image_to_string(tratar_documento(p), lang='por'))
            else:
                textos_ocr.append(pytesseract.image_to_string(tratar_documento(Image.open(f)), lang='por'))
        res = processar_analise(" ".join(textos_ocr))

with tab3:
    if 'res' in locals():
        st.subheader("📊 Relatório de Viabilidade")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Nome:** {res['nome']}")
            st.write(f"**CEP:** {res['cep']}")
            st.write(f"**Endereço:** {res['endereco']}")
            st.write(f"**Cargo:** {res['cargo']}")
        with col2:
            st.metric("Último Bruto", f"R$ {res['ultimo_bruto']:,.2f}")
            st.metric("Líquido Real (C/ Adiant.)", f"R$ {res['liq_real']:,.2f}")
            st.success(f"**Total FGTS:** R$ {res['fgts_total']:,.2f}")

        st.divider()
        # Regra de Negócio
        enquad = "SBPE" if res['ultimo_bruto'] > 8000 else "MCMV"
        st.subheader(f"Enquadramento: {enquad}")
        st.write(f"Capacidade de Parcela (30%): R$ {res['liq_real']*0.3:,.2f}")
