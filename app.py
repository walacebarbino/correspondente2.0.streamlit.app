import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime, timedelta

# --- FUNÇÕES DE APOIO ---
def preparar_imagem(img):
    img = ImageOps.grayscale(img)
    return ImageEnhance.Contrast(img).enhance(3.0)

def limpar_v(texto):
    if not texto: return 0.0
    match = re.search(r'(\d{1,3}(\.\d{3})*,\d{2})', texto)
    if match:
        return float(match.group(1).replace('.', '').replace(',', '.'))
    return 0.0

def validar_documento_inteligente(texto, nome_arquivo):
    datas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto)
    if not datas: return "✅ VALIDAR MANUAL"
    
    agora = datetime.now()
    nome_f = nome_arquivo.upper()
    
    try:
        objetos_data = [datetime.strptime(d, '%d/%m/%Y') for d in datas]
        data_recente = max(objetos_data)
        
        # CNH e Identidade: Valida apenas se não expirou a validade do documento
        if any(x in nome_f for x in ["CNH", "RG", "IDENT"]):
            if data_recente >= agora.replace(hour=0, minute=0, second=0, microsecond=0):
                return "✅ DOCUMENTO VÁLIDO"
            return "⚠️ VENCIDO"
        
        # Outros documentos: Regra de 90 dias
        if data_recente >= (agora - timedelta(days=90)):
            return "✅ DOCUMENTO VÁLIDO"
        return "⚠️ ANTIGO"
    except:
        return "⚠️ DATA ILEGÍVEL"

def motor_analise(texto_consolidado):
    t = texto_consolidado.upper().replace('|', 'I')
    linhas = t.split('\n')
    d = {}

    # Identificação
    nomes = re.findall(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{12,})', t)
    d['nome'] = next((n.strip() for n in nomes if not any(x in n for x in ["NEOENERGIA", "CONSORCIO", "SERVICOS", "LTDA", "S.A"])), "Não Identificado")
    d['cpf'] = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t).group(1) if re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t) else "Não Identificado"
    nasc_m = re.search(r'(\d{2}/\d{2}/19\d{2})|(\d{2}/\d{2}/20\d{2})', t)
    d['nasc'] = nasc_m.group(0) if nasc_m else "Não Identificado"

    # Endereço (Âncora no Nome)
    d['endereco'] = "Não Identificado"
    d['cep'] = "Não Identificado"
    for i, linha in enumerate(linhas):
        if d['nome'] in linha and len(d['nome']) > 5:
            d['endereco'] = f"{linhas[i+1]} {linhas[i+2]}".strip()
            cep_m = re.search(r'(\d{5}-\d{3})', d['endereco'])
            if cep_m: d['cep'] = cep_m.group(1)
            break
    
    if d['cep'] == "Não Identificado":
        ceps = re.findall(r'(\d{5}-\d{3})', t)
        d['cep'] = next((c for c in ceps if c != "50050-902"), "Não Identificado")

    # Financeiro
    proventos = re.findall(r'(?:VENCIMENTOS|PROVENTOS|BRUTO).*?([\d\.,]{6,})', t)
    liquidos = re.findall(r'(?:LIQUIDO|A RECEBER).*?([\d\.,]{6,})', t)
    adiantos = re.findall(r'(?:ADIANTAMENTO|ANTECIPACAO|VALE).*?([\d\.,]{5,})', t)

    val_brutos = [limpar_v(v) for v in proventos]
    d['ultimo_bruto'] = val_brutos[-1] if val_brutos else 0.0
    d['media_bruta'] = sum(val_brutos)/len(val_brutos) if val_brutos else 0.0
    d['liq_real'] = (limpar_v(liquidos[-1]) if liquidos else 0.0) + (limpar_v(adiantos[-1]) if adiantos else 0.0)
    d['cargo'] = re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t).group(1).split('\n')[0].strip() if re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t) else "Não Identificado"

    # FGTS
    saldos = re.findall(r'(?:SALDO|FINS\s+RE[SC]{1,2}ISORIOS).*?([\d\.,]{5,})', t)
    d['fgts_total'] = sum([limpar_v(s) for s in saldos])

    return d

# --- INTERFACE ---
st.set_page_config(page_title="Caixa 2.0", layout="wide")
tab1, tab2, tab3 = st.tabs(["1. Aba Geral", "2. Aba Importação", "3. Aba de Resultados"])

with tab1:
    origem = st.selectbox("Origem:", ["CLT", "Autônomo", "Empresário"])

with tab2:
    st.header("Upload e Categorização")
    c_a, c_b = st.columns(2)
    with c_a:
        u_id = st.file_uploader("Identificação (RG/CPF/CNH)", accept_multiple_files=True)
        u_res = st.file_uploader("Residência", accept_multiple_files=True)
    with c_b:
        u_renda = st.file_uploader("Renda (Holerites)", accept_multiple_files=True)
        u_fgts = st.file_uploader("FGTS", accept_multiple_files=True)

    arquivos = []
    for g in [u_id, u_res, u_renda, u_fgts]:
        if g: arquivos.extend(g)

    if arquivos:
        texto_full = ""
        lista_status = []
        for f in arquivos:
            if f.type == "application/pdf":
                pags = convert_from_bytes(f.read(), 150)
                txt = " ".join([pytesseract.image_to_string(preparar_imagem(p), lang='por') for p in pags])
            else:
                txt = pytesseract.image_to_string(preparar_imagem(Image.open(f)), lang='por')
            lista_status.append({"Arquivo": f.name, "Status": validar_documento_inteligente(txt, f.name)})
            texto_full += txt + " "
        
        st.table(pd.DataFrame(lista_status))
        res = motor_analise(texto_full)

with tab3:
    if 'res' in locals():
        st.header("Relatório Macro de Viabilidade")
        with st.expander("👤 Dados Cliente", expanded=True):
            col1, col2 = st.columns(2)
            col1.write(f"**Nome:** {res['nome']}")
            col1.write(f"**CPF:** {res['cpf']} | **Nasc:** {res['nasc']}")
            col2.write(f"**Endereço:** {res['endereco']}")
            col2.write(f"**CEP:** {res['cep']}")
        with st.expander("💰 Financeiro", expanded=True):
            f1, f2, f3 = st.columns(3)
            f1.metric("Último Bruto", f"R$ {res['ultimo_bruto']:,.2f}")
            f2.metric("Média Bruta", f"R$ {res['media_bruta']:,.2f}")
            f3.metric("Líquido Real", f"R$ {res['liq_real']:,.2f}")
        st.success(f"**FGTS Total:** R$ {res['fgts_total']:,.2f}")
        st.divider()
        st.markdown("### **Aprovação:** ✅ ALTA" if res['ultimo_bruto'] > 0 else "### **Aprovação:** ❌ INCOMPLETO")
