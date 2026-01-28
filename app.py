import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DE AMBIENTE ---
# Caso o Tesseract não esteja no PATH, descomente e ajuste a linha abaixo:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- MOTORES DE APOIO ---
def preparar_imagem(img):
    img = ImageOps.grayscale(img)
    return ImageEnhance.Contrast(img).enhance(3.0)

def limpar_v(texto):
    if not texto: return 0.0
    # Remove tudo que não é número ou vírgula, depois trata decimais
    val = re.sub(r'[^\d,]', '', texto).replace(',', '.')
    try: return float(val)
    except: return 0.0

def validar_doc_90_dias(texto):
    datas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto)
    if not datas: return "⚠️ DATA NÃO DETECTADA"
    try:
        data_doc = max([datetime.strptime(d, '%d/%m/%Y') for d in datas])
        if datetime.now() - data_doc > timedelta(days=90):
            return "⚠️ DOCUMENTO EXPIRADO"
        return "✅ DOCUMENTO VÁLIDO"
    except:
        return "⚠️ ERRO DE VALIDAÇÃO"

# --- MOTOR DE INTELIGÊNCIA DE EXTRAÇÃO UNIVERSAL ---
def motor_analise_universal(texto_consolidado):
    t = texto_consolidado.upper().replace('|', 'I')
    d = {}

    # 1. IDENTIFICAÇÃO (Regra de Exclusão de Empresas)
    # Busca nomes e filtra palavras-chave de empresas (Neoenergia, Consórcio, etc)
    nomes_encontrados = re.findall(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{10,})', t)
    d['nome'] = next((n.strip() for n in nomes_encontrados if not any(x in n for x in ["CONSORCIO", "SERVICOS", "NEOENERGIA", "CIA", "S/A", "LTDA", "ELETRI"])), "Não Identificado")

    d['cpf'] = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t).group(1) if re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t) else "Não Identificado"
    d['rg'] = re.search(r'(\d{7,10})\s*(?:SESP|SSP|IDENT)', t).group(1) if re.search(r'(\d{7,10})\s*(?:SESP|SSP|IDENT)', t) else "Não Identificado"
    d['nasc'] = re.search(r'(\d{2}/\d{2}/\d{4})', t).group(1) if re.search(r'(\d{2}/\d{2}/\d{4})', t) else "Não Identificado"

    # 2. RESIDÊNCIA (Hierarquia de busca e Filtro Anti-CNPJ)
    ceps = re.findall(r'(\d{5}-\d{3})', t)
    # Ignora CEP fixo da Neoenergia (50050-902)
    d['cep'] = next((c for c in ceps if c != "50050-902"), "Não Identificado")
    
    linhas = t.split('\n')
    # Busca endereço residencial ignorando linhas com CNPJ
    d['endereco'] = next((l.strip() for l in linhas if any(x in l for x in ["RUA", "AV.", "ESTRADA"]) and "CNPJ" not in l), "Não Detectado")

    # 3. RENDA (Média, Último Bruto e Reincorporação de Adiantamento)
    # Extrai todos os valores de vencimentos e líquidos
    brutos_encontrados = re.findall(r'(?:VENCIMENTOS|TOTAL PROVENTOS|BRUTO)[:\s]*([\d\.,]{5,})', t)
    liquidos_encontrados = re.findall(r'(?:TOTAL LIQUIDO|LIQUIDO PGTO)[:\s]*([\d\.,]{5,})', t)
    adiantamentos_encontrados = re.findall(r'(?:ADIANTAMENTO|ANTECIPACAO|VALE)[:\s]*([\d\.,]{5,})', t)

    val_brutos = [limpar_v(v) for v in brutos_encontrados]
    d['ultimo_bruto'] = val_brutos[-1] if val_brutos else 0.0
    d['media_bruta'] = sum(val_brutos)/len(val_brutos) if val_brutos else 0.0

    # Lógica do Líquido Real (Líquido + Adiantamento)
    val_liq_ult = limpar_v(liquidos_encontrados[-1]) if liquidos_encontrados else 0.0
    val_adi_ult = limpar_v(adiantamentos_encontrados[-1]) if adiantamentos_encontrados else 0.0
    d['ultimo_liq_real'] = val_liq_ult + val_adi_ult
    
    # Média Líquida considerando todos os holerites com adiantamento
    d['media_liq_real'] = d['ultimo_liq_real'] # Valor base simplificado

    d['cargo'] = re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t).group(1).split('\n')[0].strip() if re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t) else "Não Identificado"

    # 4. FGTS (Consolidação de Múltiplos Vínculos por CNPJ)
    cnpjs = re.findall(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', t)
    saldos = re.findall(r'(?:SALDO|FINS\s+RE[SC]{1,2}ISORIOS).*?([\d\.,]{5,})', t)
    
    d['fgts_contas'] = []
    for i, valor_s in enumerate(saldos):
        val = limpar_v(valor_s)
        if val > 0:
            cnpj = cnpjs[i] if i < len(cnpjs) else "CNPJ Desconhecido"
            d['fgts_contas'].append({"cnpj": cnpj, "valor": val})
    
    d['fgts_total'] = sum([c['valor'] for c in d['fgts_contas']])

    return d

# --- INTERFACE POR ABAS ---
st.set_page_config(page_title="Correspondente Caixa 2.0", layout="wide")

tab_geral, tab_import, tab_result = st.tabs(["< 1. Aba Geral >", "< 2. Aba Importação >", "< 3. Aba de Resultados >"])

with tab_geral:
    st.header("Configuração da Proposta")
    origem_rec = st.selectbox("Origem de Recursos:", ["CLT", "Autônomos e Profissionais Liberais", "Empresários/MEI"])

with tab_import:
    st.header("Upload e Categorização")
    col1, col2 = st.columns(2)
    with col1:
        u_id = st.file_uploader("Identificação (RG/CPF/CNH)", accept_multiple_files=True)
        u_res = st.file_uploader("Residência", accept_multiple_files=True)
    with col2:
        u_renda = st.file_uploader("Renda (Holerites/Extratos)", accept_multiple_files=True)
        u_fgts = st.file_uploader("FGTS (Extratos)", accept_multiple_files=True)

    arquivos_upload = []
    for grupo in [u_id, u_res, u_renda, u_fgts]:
        if grupo: arquivos_upload.extend(grupo)

    if arquivos_upload:
        texto_dossie = ""
        status_lista = []
        for f in arquivos_upload:
            # Processamento de PDF ou Imagem
            if f.type == "application/pdf":
                paginas = convert_from_bytes(f.read(), 150)
                txt_f = " ".join([pytesseract.image_to_string(preparar_imagem(p), lang='por') for p in paginas])
            else:
                txt_f = pytesseract.image_to_string(preparar_imagem(Image.open(f)), lang='por')
            
            validez = validar_doc_90_dias(txt_f)
            status_lista.append({"Arquivo": f.name, "Status": validez})
            texto_dossie += txt_f + " "
        
        # Correção do Erro de Variável
        st.table(pd.DataFrame(status_lista))
        res_final = motor_analise_universal(texto_dossie)

with tab_result:
    if 'res_final' in locals():
        st.header("Relatório Macro de Viabilidade")
        
        with st.expander("👤 Dados do Cliente", expanded=True):
            r1, r2 = st.columns(2)
            r1.write(f"**Nome completo:** {res_final['nome']}")
            r1.write(f"**CPF:** {res_final['cpf']} | **RG:** {res_final['rg']}")
            r1.write(f"**Data de nascimento:** {res_final['nasc']}")
            r2.write(f"**Endereço residencial:** {res_final['endereco']}")
            r2.write(f"**CEP:** {res_final['cep']}")

        with st.expander("💰 Financeiro", expanded=True):
            f1, f2, f3 = st.columns(3)
            f1.write(f"**Origem:** {origem_rec}")
            f1.write(f"**Cargo:** {res_final['cargo']}")
            f2.metric("Média Bruta", f"R$ {res_final['media_bruta']:,.2f}")
            f2.metric("Último Bruto", f"R$ {res_final['ultimo_bruto']:,.2f}")
            f3.metric("Último Líquido Real", f"R$ {res_final['ultimo_liq_real']:,.2f}", delta="C/ Adiantamento")

        with st.expander("📈 FGTS (Vínculos Identificados)", expanded=True):
            for i, c in enumerate(res_final['fgts_contas']):
                st.write(f"**Conta {i+1} (CNPJ {c['cnpj']}):** R$ {c['valor']:,.2f}")
            st.success(f"**Total FGTS:** R$ {res_final['fgts_total']:,.2f}")

        st.divider()
        # Regras de Negócio Caixa
        enquadramento = "SBPE" if res_final['ultimo_bruto'] > 8000 else "MCMV"
        subsidio = 55000.00 if enquadramento == "MCMV" else 0.0
        capacidade_30 = res_final['ultimo_liq_real'] * 0.30

        v1, v2, v3 = st.columns(3)
        v1.info(f"**Enquadramento:** {enquadramento}")
        v2.metric("Subsídio Estimado", f"R$ {subsidio:,.2f}")
        v3.metric("Capacidade Parcela (30%)", f"R$ {capacidade_30:,.2f}")

        # Correção do Status de Aprovação
        if res_final['ultimo_liq_real'] > 0 and res_final['ultimo_bruto'] > 0:
            st.markdown("### **Status de Provável Aprovação:** ✅ ALTA")
        else:
            st.markdown("### **Status de Provável Aprovação:** ❌ PENDENTE (Dados Insuficientes)")
            
        st.button("🖨️ Gerar Impressão / Relatório PDF")
    else:
        st.info("Aguardando upload e processamento na Aba 2.")
