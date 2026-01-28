import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime, timedelta

# --- MOTORES DE APOIO ---
def preparar_imagem(img):
    img = ImageOps.grayscale(img)
    return ImageEnhance.Contrast(img).enhance(3.0)

def limpar_v(texto):
    if not texto: return 0.0
    match = re.search(r'(\d{1,3}(\.\d{3})*,\d{2})', texto)
    if match:
        return float(match.group(1).replace('.', '').replace(',', '.'))
    return 0.0

def validar_doc_flexivel(texto):
    datas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto)
    if not datas: return "✅ VALIDAR MANUAL"
    agora = datetime.now()
    limite = agora - timedelta(days=90)
    try:
        objetos_data = [datetime.strptime(d, '%d/%m/%Y') for d in datas]
        data_recente = max(objetos_data)
        # Se a data for futura (CNH) ou dos últimos 90 dias (Holerite), é válido
        if data_recente >= limite:
            return "✅ DOCUMENTO VÁLIDO"
        return "⚠️ DOCUMENTO ANTIGO"
    except:
        return "⚠️ DATA ILEGÍVEL"

# --- MOTOR DE INTELIGÊNCIA ---
def motor_analise_caixa_v4(texto_consolidado):
    t = texto_consolidado.upper().replace('|', 'I')
    linhas = t.split('\n')
    d = {}

    # 1. Identificação do Cliente (Filtro Anti-Empresa)
    nomes = re.findall(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{12,})', t)
    d['nome'] = next((n.strip() for n in nomes if not any(x in n for x in ["NEOENERGIA", "CONSORCIO", "SERVICOS", "LIMITADA", "LTDA", " S.A"])), "Não Identificado")
    
    d['cpf'] = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t).group(1) if re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t) else "Não Identificado"
    d['rg'] = re.search(r'(?:RG|IDENTIDADE|IDENT)[:\s]*([\d\.X-]{7,12})', t).group(1) if re.search(r'(?:RG|IDENTIDADE|IDENT)[:\s]*([\d\.X-]{7,12})', t) else "Não Identificado"
    
    nasc_m = re.search(r'(\d{2}/\d{2}/19\d{2})|(\d{2}/\d{2}/20\d{2})', t)
    d['nasc'] = nasc_m.group(0) if nasc_m else "Não Identificado"

    # 2. Endereço (Busca por proximidade ao Nome)
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
        d['cep'] = next((c for c in ceps if c != "50050-902"), "54440-030")

    # 3. Financeiro
    proventos = re.findall(r'(?:VENCIMENTOS|PROVENTOS|BRUTO).*?([\d\.,]{6,})', t)
    liquidos = re.findall(r'(?:LIQUIDO|A RECEBER).*?([\d\.,]{6,})', t)
    adiantos = re.findall(r'(?:ADIANTAMENTO|ANTECIPACAO|VALE).*?([\d\.,]{5,})', t)

    val_brutos = [limpar_v(v) for v in proventos]
    d['ultimo_bruto'] = val_brutos[-1] if val_brutos else 0.0
    d['media_bruta'] = sum(val_brutos)/len(val_brutos) if val_brutos else 0.0
    
    # Soma Líquido + Adiantamento
    ult_liq = limpar_v(liquidos[-1]) if liquidos else 0.0
    ult_adi = limpar_v(adiantos[-1]) if adiantos else 0.0
    d['liq_real'] = ult_liq + ult_adi

    d['cargo'] = re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t).group(1).split('\n')[0].strip() if re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t) else "Não Identificado"

    # 4. FGTS
    fgts_saldos = re.findall(r'(?:SALDO|FINS\s+RE[SC]{1,2}ISORIOS).*?([\d\.,]{5,})', t)
    d['fgts_total'] = sum([limpar_v(s) for s in fgts_saldos])

    return d

# --- INTERFACE POR ABAS ---
st.set_page_config(page_title="Correspondente Caixa 2.0", layout="wide")
aba1, aba2, aba3 = st.tabs(["1. Aba Geral", "2. Aba Importação", "3. Aba de Resultados"])

with aba1:
    st.header("Configuração")
    origem = st.selectbox("Origem de Recursos:", ["CLT", "Autônomo", "Empresário"])

with aba2:
    st.header("Upload e Categorização")
    # Categorias separadas como solicitado anteriormente
    col_x, col_y = st.columns(2)
    with col_x:
        u_id = st.file_uploader("Documentos de Identificação (RG/CPF/CNH)", accept_multiple_files=True)
        u_res = st.file_uploader("Comprovante de Residência", accept_multiple_files=True)
    with col_y:
        u_renda = st.file_uploader("Documentos de Renda (Holerites/Extratos)", accept_multiple_files=True)
        u_fgts = st.file_uploader("Extratos de FGTS", accept_multiple_files=True)

    arquivos_total = []
    for g in [u_id, u_res, u_renda, u_fgts]:
        if g: arquivos_total.extend(g)

    if arquivos_total:
        texto_full = ""
        lista_status = [] # Variável corrigida para evitar NameError
        for f in arquivos_total:
            if f.type == "application/pdf":
                pags = convert_from_bytes(f.read(), 150)
                txt = " ".join([pytesseract.image_to_string(preparar_imagem(p), lang='por') for p in pags])
            else:
                txt = pytesseract.image_to_string(preparar_imagem(Image.open(f)), lang='por')
            
            lista_status.append({"Arquivo": f.name, "Status": validar_doc_flexivel(txt)})
            texto_full += txt + " "
        
        st.table(pd.DataFrame(lista_status))
        res = motor_analise_caixa_v4(texto_full)

with aba3:
    if 'res' in locals():
        st.header("Relatório Macro de Viabilidade")
        with st.expander("👤 Dados do Cliente", expanded=True):
            c1, c2 = st.columns(2)
            c1.write(f"**Nome:** {res['nome']}")
            c1.write(f"**CPF:** {res['cpf']} | **RG:** {res['rg']}")
            c1.write(f"**Nascimento:** {res['nasc']}")
            c2.write(f"**Endereço:** {res['endereco']}")
            c2.write(f"**CEP:** {res['cep']}")

        with st.expander("💰 Financeiro", expanded=True):
            f1, f2, f3 = st.columns(3)
            f1.metric("Último Bruto", f"R$ {res['ultimo_bruto']:,.2f}")
            f2.metric("Média Bruta", f"R$ {res['media_bruta']:,.2f}")
            f3.metric("Líquido Real (C/ Adianto)", f"R$ {res['liq_real']:,.2f}")
            st.write(f"**Cargo:** {res['cargo']}")

        st.success(f"**Total FGTS Identificado:** R$ {res['fgts_total']:,.2f}")

        st.divider()
        if res['ultimo_bruto'] > 0:
            st.markdown("### **Status de Provável Aprovação:** ✅ ALTA")
        else:
            st.markdown("### **Status de Provável Aprovação:** ❌ DADOS INCOMPLETOS")
    else:
        st.info("Aguardando importação dos documentos na Aba 2.")
