import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime, timedelta

# --- CONFIGURAÇÕES DE INTERFACE ---
st.set_page_config(page_title="Caixa Correspondente 2.0", layout="wide")

# --- MOTORES DE APOIO ---
def preparar_imagem(img):
    img = ImageOps.grayscale(img)
    return ImageEnhance.Contrast(img).enhance(3.0)

def limpar_v(texto):
    if not texto: return 0.0
    val = re.sub(r'[^\d,]', '', texto).replace(',', '.')
    try: return float(val)
    except: return 0.0

# CORREÇÃO DA LÓGICA DE DATA (Últimos 3 meses / 90 dias)
def validar_doc_90_dias(texto):
    datas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto)
    if not datas: return "✅ DATA NÃO DETECTADA (VALIDAR MANUAL)"
    
    agora = datetime.now()
    limite = agora - timedelta(days=90)
    
    try:
        # Pega a data mais recente no documento para validar
        data_doc = max([datetime.strptime(d, '%d/%m/%Y') for d in datas])
        if data_doc >= limite:
            return "✅ DOCUMENTO VÁLIDO"
        return "⚠️ DOCUMENTO EXPIRADO"
    except:
        return "⚠️ ERRO DE FORMATAÇÃO"

# --- MOTOR DE INTELIGÊNCIA DE EXTRAÇÃO UNIVERSAL ---
def motor_analise_universal(texto_consolidado):
    t = texto_consolidado.upper().replace('|', 'I')
    d = {}

    # 1. IDENTIFICAÇÃO (Filtro Anti-Empresa)
    nomes_encontrados = re.findall(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{10,})', t)
    # Descarta nomes de empresas conhecidas para focar no cliente
    d['nome'] = next((n.strip() for n in nomes_encontrados if not any(x in n for x in ["CONSORCIO", "SERVICOS", "NEOENERGIA", "CIA", "S/A", "LTDA"])), "Não Identificado")

    d['cpf'] = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t).group(1) if re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t) else "Não Identificado"
    d['rg'] = re.search(r'(\d{7,10})\s*(?:SESP|SSP|IDENT)', t).group(1) if re.search(r'(\d{7,10})\s*(?:SESP|SSP|IDENT)', t) else "Não Identificado"
    d['nasc'] = re.search(r'(\d{2}/\d{2}/\d{4})', t).group(1) if re.search(r'(\d{2}/\d{2}/\d{4})', t) else "Não Identificado"

    # 2. RESIDÊNCIA (Filtro de CEP e Destinatário)
    ceps = re.findall(r'(\d{5}-\d{3})', t)
    # Filtra o CEP da Neoenergia (50050-902) para não pegar endereço errado
    d['cep'] = next((c for c in ceps if c != "50050-902"), "Não Identificado")
    
    linhas = t.split('\n')
    # Procura endereço em linhas que não tenham CNPJ (evita pegar dados da empresa)
    d['endereco'] = next((l.strip() for l in linhas if any(x in l for x in ["RUA", "AV.", "ESTRADA"]) and "CNPJ" not in l), "Endereço não detectado")

    # 3. RENDA (Média e Reincorporação de Adiantamento)
    brutos = re.findall(r'(?:VENCIMENTOS|TOTAL PROVENTOS|BRUTO)[:\s]*([\d\.,]{5,})', t)
    liquidos = re.findall(r'(?:TOTAL LIQUIDO|LIQUIDO PGTO)[:\s]*([\d\.,]{5,})', t)
    adiantos = re.findall(r'(?:ADIANTAMENTO|ANTECIPACAO|VALE)[:\s]*([\d\.,]{5,})', t)

    val_brutos = [limpar_v(v) for v in brutos]
    d['ultimo_bruto'] = val_brutos[-1] if val_brutos else 0.0
    d['media_bruta'] = sum(val_brutos)/len(val_brutos) if val_brutos else 0.0

    # Lógica do Líquido Real (Soma Adiantamento)
    val_liq = limpar_v(liquidos[-1]) if liquidos else 0.0
    val_adi = limpar_v(adiantos[-1]) if adiantos else 0.0
    d['ultimo_liq_real'] = val_liq + val_adi
    d['media_liq_real'] = d['ultimo_liq_real']

    d['cargo'] = re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t).group(1).split('\n')[0].strip() if re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t) else "Não Identificado"

    # 4. FGTS (Consolidação Múltipla)
    saldos = re.findall(r'(?:SALDO|FINS\s+RE[SC]{1,2}ISORIOS).*?([\d\.,]{5,})', t)
    d['fgts_total'] = sum([limpar_v(s) for s in saldos])

    return d

# --- INTERFACE ---
tab1, tab2, tab3 = st.tabs(["< 1. Aba Geral >", "< 2. Aba Importação >", "< 3. Aba de Resultados >"])

with tab1:
    origem_rec = st.selectbox("Origem de Recursos:", ["CLT", "Autônomo", "Empresário/MEI"])

with tab2:
    st.header("Upload e Categorização")
    u_id = st.file_uploader("Identificação", accept_multiple_files=True)
    u_res = st.file_uploader("Residência", accept_multiple_files=True)
    u_renda = st.file_uploader("Renda", accept_multiple_files=True)
    u_fgts = st.file_uploader("FGTS", accept_multiple_files=True)

    arquivos = []
    for g in [u_id, u_res, u_renda, u_fgts]:
        if g: arquivos.extend(g)

    if arquivos:
        texto_dossie = ""
        lista_status = [] # CORREÇÃO DO NameError: status_status_docs
        for f in arquivos:
            if f.type == "application/pdf":
                paginas = convert_from_bytes(f.read(), 150)
                txt_f = " ".join([pytesseract.image_to_string(preparar_imagem(p), lang='por') for p in paginas])
            else:
                txt_f = pytesseract.image_to_string(preparar_imagem(Image.open(f)), lang='por')
            
            validez = validar_doc_90_dias(txt_f)
            lista_status.append({"Arquivo": f.name, "Status": validez})
            texto_dossie += txt_f + " "
        
        st.table(pd.DataFrame(lista_status))
        res = motor_analise_universal(texto_dossie)

with tab3:
    if 'res' in locals():
        st.header("Relatório Macro de Viabilidade")
        
        with st.expander("👤 Dados Cliente", expanded=True):
            r1, r2 = st.columns(2)
            r1.write(f"**Nome:** {res['nome']}")
            r1.write(f"**CPF:** {res['cpf']} | **RG:** {res['rg']}")
            r2.write(f"**Endereço:** {res['endereco']}")
            r2.write(f"**CEP:** {res['cep']}")

        with st.expander("💰 Financeiro", expanded=True):
            f1, f2, f3 = st.columns(3)
            f1.write(f"**Cargo:** {res['cargo']}")
            f2.metric("Média Bruta", f"R$ {res['media_bruta']:,.2f}")
            f3.metric("Líquido Real", f"R$ {res['ultimo_liq_real']:,.2f}", delta="C/ Adiantamento")

        with st.expander("📈 FGTS", expanded=True):
            st.success(f"**Total FGTS Identificado:** R$ {res['fgts_total']:,.2f}")

        st.divider()
        enquad = "SBPE" if res['ultimo_bruto'] > 8000 else "MCMV"
        st.info(f"**Enquadramento:** {enquad}")
        
        # Só libera aprovação se houver dados consistentes
        if res['ultimo_bruto'] > 0:
            st.markdown("### **Status de Provável Aprovação:** ✅ ALTA")
        else:
            st.markdown("### **Status de Provável Aprovação:** ❌ DADOS INCOMPLETOS")
