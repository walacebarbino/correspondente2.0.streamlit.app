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

def validar_doc_90_dias(texto):
    # Procura datas no formato DD/MM/AAAA
    datas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto)
    if not datas: return "⚠️ DATA NÃO DETECTADA"
    
    try:
        # Pega a data mais recente encontrada no documento
        data_doc = max([datetime.strptime(d, '%d/%m/%Y') for d in datas])
        if datetime.now() - data_doc > timedelta(days=90):
            return "⚠️ DOCUMENTO EXPIRADO (>90 dias)"
        return "✅ DOCUMENTO VÁLIDO"
    except:
        return "⚠️ ERRO AO VALIDAR DATA"

# --- MOTOR DE INTELIGÊNCIA DE EXTRAÇÃO ---
def motor_analise_universal(texto_consolidado):
    t = texto_consolidado.upper().replace('|', 'I')
    d = {}

    # 1. IDENTIFICAÇÃO (Regra de Exclusão de Empresas)
    nomes = re.findall(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{10,})', t)
    d['nome'] = next((n.strip() for n in nomes if not any(x in n for x in ["CONSORCIO", "SERVICOS", "NEOENERGIA", "CIA", "S/A", "LTDA"])), "Não Identificado")
    
    d['cpf'] = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t).group(1) if re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t) else "Não Identificado"
    d['rg'] = re.search(r'(\d{7,10})\s*(?:SESP|SSP|IDENT)', t).group(1) if re.search(r'(\d{7,10})\s*(?:SESP|SSP|IDENT)', t) else "Não Identificado"
    d['nasc'] = re.search(r'(\d{2}/\d{2}/\d{4})', t).group(1) if re.search(r'(\d{2}/\d{2}/\d{4})', t) else "Não Identificado"

    # 2. RESIDÊNCIA (Regra Anti-Erro de Concessionária)
    ceps = re.findall(r'(\d{5}-\d{3})', t)
    d['cep'] = next((c for c in ceps if c != "50050-902"), "Não Identificado")
    
    linhas = t.split('\n')
    # Busca endereço ignorando linhas que contenham CNPJ (Filtro de Exclusão)
    d['endereco'] = next((l.strip() for l in linhas if any(x in l for x in ["RUA", "AV.", "ESTRADA"]) and "CNPJ" not in l), "Endereço não detectado")

    # 3. RENDA (Regra de Adiantamento e Médias)
    brutos = re.findall(r'(?:VENCIMENTOS|TOTAL PROVENTOS|BRUTO)[:\s]*([\d\.,]{5,})', t)
    liquidos = re.findall(r'(?:TOTAL LIQUIDO|LIQUIDO PGTO)[:\s]*([\d\.,]{5,})', t)
    adiantos = re.findall(r'(?:ADIANTAMENTO|ANTECIPACAO|VALE)[:\s]*([\d\.,]{5,})', t)

    val_brutos = [limpar_v(v) for v in brutos]
    d['ultimo_bruto'] = val_brutos[-1] if val_brutos else 0.0
    d['media_bruta'] = sum(val_brutos)/len(val_brutos) if val_brutos else 0.0

    # Líquido Real (Reincorporação de Adiantamento)
    val_liq = limpar_v(liquidos[-1]) if liquidos else 0.0
    val_adi = limpar_v(adiantos[-1]) if adiantos else 0.0
    d['ultimo_liq_real'] = val_liq + val_adi
    d['media_liq_real'] = d['ultimo_liq_real'] # Simplificado

    d['cargo'] = re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t).group(1).split('\n')[0].strip() if re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t) else "Não Identificado"

    # 4. FGTS (Validação de Vínculo por CNPJ)
    cnpjs_fgts = re.findall(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', t)
    saldos_fgts = re.findall(r'(?:SALDO|FINS\s+RE[SC]{1,2}ISORIOS).*?([\d\.,]{5,})', t)
    
    contas = []
    for i, valor_str in enumerate(saldos_fgts):
        valor = limpar_v(valor_str)
        if valor > 0:
            cnpj = cnpjs_fgts[i] if i < len(cnpjs_fgts) else "CNPJ Desconhecido"
            contas.append({"cnpj": cnpj, "valor": valor})
    
    d['fgts_lista'] = contas
    d['fgts_total'] = sum([c['valor'] for c in contas])

    return d

# --- INTERFACE POR ABAS ---
tab1, tab2, tab3 = st.tabs(["< 1. Aba Geral >", "< 2. Aba Importação >", "< 3. Aba de Resultados >"])

with tab1:
    st.header("Configuração da Origem")
    origem = st.selectbox("Sinalizar origem de recursos:", ["CLT", "Autônomos e Profissionais Liberais", "Empresários/MEI"])
    st.info(f"O sistema está pronto para analisar perfis de: {origem}")

with tab2:
    st.header("Upload e Categorização")
    col_a, col_b = st.columns(2)
    with col_a:
        u_id = st.file_uploader("Documentos de Identificação (RG/CPF/CNH)", accept_multiple_files=True)
        u_res = st.file_uploader("Comprovante de Residência", accept_multiple_files=True)
    with col_b:
        u_renda = st.file_uploader("Documentos de Renda (Holerites/Extratos)", accept_multiple_files=True)
        u_fgts = st.file_uploader("Extratos de FGTS", accept_multiple_files=True)

    arquivos_totais = []
    for g in [u_id, u_res, u_renda, u_fgts]:
        if g: arquivos_totais.extend(g)

    if arquivos_totais:
        texto_dossie = ""
        status_docs = []
        for f in arquivos_totais:
            if f.type == "application/pdf":
                paginas = convert_from_bytes(f.read(), 150)
                txt_f = " ".join([pytesseract.image_to_string(preparar_imagem(p), lang='por') for p in paginas])
            else:
                txt_f = pytesseract.image_to_string(preparar_imagem(Image.open(f)), lang='por')
            
            status_validade = validar_doc_90_dias(txt_f)
            status_docs.append({"Arquivo": f.name, "Validação": status_validade})
            texto_dossie += txt_f + " "
        
        st.table(pd.DataFrame(status_status_docs))
        res = motor_analise_universal(texto_dossie)

with tab3:
    if 'res' in locals():
        st.header("Relatório Macro de Viabilidade")
        
        with st.expander("👤 Dados Cliente", expanded=True):
            c1, c2 = st.columns(2)
            c1.write(f"**Nome completo:** {res['nome']}")
            c1.write(f"**CPF:** {res['cpf']} | **RG:** {res['rg']}")
            c1.write(f"**Nascimento:** {res['nasc']}")
            c2.write(f"**Endereço:** {res['endereco']}")
            c2.write(f"**CEP:** {res['cep']}")

        with st.expander("💰 Financeiro", expanded=True):
            f1, f2, f3 = st.columns(3)
            f1.write(f"**Origem:** {origem}")
            f1.write(f"**Cargo/Função:** {res['cargo']}")
            f2.metric("Média Salarial Bruta", f"R$ {res['media_bruta']:,.2f}")
            f2.metric("Último Salário Bruto", f"R$ {res['ultimo_bruto']:,.2f}")
            f3.metric("Último Líquido Real", f"R$ {res['ultimo_liq_real']:,.2f}", delta="C/ Adiantamento")

        with st.expander("📈 FGTS (Contas Distintas)", expanded=True):
            for i, c in enumerate(res['fgts_lista']):
                st.write(f"**Conta {i+1} (CNPJ {c['cnpj']}):** R$ {c['valor']:,.2f}")
            st.success(f"**Total FGTS:** R$ {res['fgts_total']:,.2f}")

        st.divider()
        # Regras de Negócio Caixa
        enquad = "SBPE" if res['ultimo_bruto'] > 8000 else "MCMV"
        subsidio = 55000.0 if enquad == "MCMV" else 0.0
        parcela_max = res['ultimo_liq_real'] * 0.30

        v1, v2, v3 = st.columns(3)
        v1.info(f"**Enquadramento:** {enquad}")
        v2.metric("Subsídio Estimado", f"R$ {subsidio:,.2f}")
        v3.metric("Parcela Máxima (30%)", f"R$ {parcela_max:,.2f}")

        if res['fgts_total'] < 10000 and enquad == "SBPE":
            st.warning("⚠️ Alerta: Necessidade de Complementação de Recursos (Entrada insuficiente).")
        
        st.button("🖨️ Gerar Impressão / Relatório PDF")
    else:
        st.info("Aguardando upload de documentos para processar.")
