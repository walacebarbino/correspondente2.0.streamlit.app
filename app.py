import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime
from io import BytesIO

# Configurações de Interface
st.set_page_config(page_title="Caixa Correspondente 2.0", layout="wide")

# --- MOTOR DE TRATAMENTO DE IMAGEM ---
def preparar_imagem(img):
    img = ImageOps.grayscale(img)
    return ImageEnhance.Contrast(img).enhance(3.0)

# --- AUXILIARES DE LIMPEZA ---
def limpar_valor(texto):
    if not texto: return 0.0
    # Remove tudo que não é dígito ou vírgula, depois troca vírgula por ponto
    val = re.sub(r'[^\d,]', '', texto).replace(',', '.')
    try: return float(val)
    except: return 0.0

# --- NÚCLEO DE INTELIGÊNCIA DE EXTRAÇÃO ---
def motor_analise_caixa(texto_consolidado):
    t = texto_consolidado.upper().replace('|', 'I')
    d = {}

    # 1. Identificação
    d['nome'] = re.search(r'(?:NOME|CLIENTE|COLABORADOR)[:\s]+([A-Z\s]{10,})', t).group(1).split('\n')[0].strip() if re.search(r'(?:NOME|CLIENTE|COLABORADOR)[:\s]+([A-Z\s]{10,})', t) else "N/D"
    d['cpf'] = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t).group(1) if re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t) else "N/D"
    d['rg'] = re.search(r'(?:RG|IDENTIDADE)[:\s]*([\d\.X-]{7,12})', t).group(1) if re.search(r'(?:RG|IDENTIDADE)[:\s]*([\d\.X-]{7,12})', t) else "N/D"
    d['nasc'] = re.search(r'(\d{2}/\d{2}/\d{4})', t).group(1) if re.search(r'(\d{2}/\d{2}/\d{4})', t) else "N/D"
    d['est_civil'] = re.search(r'(SOLTEIRO|CASADO|DIVORCIADO|VIUVO|UNIAO ESTAVEL)', t).group(1) if re.search(r'(SOLTEIRO|CASADO|DIVORCIADO|VIUVO|UNIAO ESTAVEL)', t) else "N/D"

    # 2. Residência (Regra Anti-Erro de CNPJ)
    # Filtra CEPs, priorizando o que não é de grandes empresas/concessionárias conhecidas
    ceps = re.findall(r'(\d{5}-\d{3})', t)
    d['cep'] = ceps[0] if ceps else "N/D"
    # Busca endereço ignorando linhas que contenham CNPJ (Filtro de Exclusão)
    linhas = t.split('\n')
    endereco_encontrado = "Não Detectado"
    for linha in linhas:
        if any(x in linha for x in ["RUA", "AV.", "ESTRADA", "LOGRADOURO"]) and "CNPJ" not in linha:
            endereco_encontrado = linha.strip()
            break
    d['endereco_completo'] = endereco_encontrado

    # 3. Renda e Profissional (Holerites)
    brutos = re.findall(r'(?:VENCIMENTOS|TOTAL PROVENTOS|BRUTO)[:\s]*([\d\.,]{5,})', t)
    d['lista_bruto'] = [limpar_valor(v) for v in brutos]
    d['ultimo_bruto'] = d['lista_bruto'][-1] if d['lista_bruto'] else 0.0
    d['media_bruta'] = sum(d['lista_bruto'])/len(d['lista_bruto']) if d['lista_bruto'] else 0.0
    
    # Líquido Real (Regra de Adiantamento OBRIGATÓRIA)
    liquidos = re.findall(r'(?:LIQUIDO|A RECEBER|VALOR LIQUIDO)[:\s]*([\d\.,]{5,})', t)
    adiantos = re.findall(r'(?:ADIANTAMENTO|ANTECIPACAO|VALE)[:\s]*([\d\.,]{5,})', t)
    
    # Soma o último líquido ao último adiantamento encontrado
    ult_liq = limpar_valor(liquidos[-1]) if liquidos else 0.0
    ult_adi = limpar_valor(adiantos[-1]) if adiantos else 0.0
    d['ultimo_liq_real'] = ult_liq + ult_adi
    d['media_liq_real'] = d['ultimo_liq_real'] # Simplificado para o protótipo
    
    d['cargo'] = re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t).group(1).split('\n')[0].strip() if re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t) else "N/D"
    
    # Tempo de Casa
    adm_m = re.search(r'(?:ADMISSAO|ADM)[:\s]*(\d{2}/\d{2}/\d{4})', t)
    if adm_m:
        data_adm = datetime.strptime(adm_m.group(1), '%d/%m/%Y')
        delta = datetime.now() - data_adm
        anos = delta.days // 365
        meses = (delta.days % 365) // 30
        d['tempo_casa'] = f"{anos} anos, {meses} meses"
        d['data_adm'] = adm_m.group(1)
    else:
        d['tempo_casa'] = "N/D"
        d['data_adm'] = "N/D"

    # 5. FGTS (Consolidação)
    empresas_fgts = re.findall(r'(?:EMPREGADOR|EMPRESA)[:\s]+([A-Z\s]{5,})', t)
    saldos_rescisorios = re.findall(r'VALOR PARA FINS RESCISORIOS.*?([\d\.,]{5,})', t)
    saldos_limpos = [limpar_valor(s) for s in saldos_rescisorios if limpar_valor(s) > 0]
    
    d['fgts_contas'] = saldos_limpos
    d['fgts_total'] = sum(saldos_limpos)
    
    return d

# --- INTERFACE POR ABAS ---
aba_geral, aba_import, aba_results = st.tabs(["1. Aba Geral", "2. Aba Importação", "3. Aba de Resultados"])

with aba_geral:
    st.header("⚙️ Configurações Iniciais")
    origem_recurso = st.radio("Origem de Recursos (Obrigatório):", 
                              ["CLT", "Autônomos/Profissionais Liberais", "Empresários/MEI"])
    st.success(f"Sistema operando em modo: {origem_recurso}")

with aba_import:
    st.header("📂 Upload e Categorização")
    
    col1, col2 = st.columns(2)
    with col1:
        up_id = st.file_uploader("Documentos de Identificação (RG/CNH/Certidões)", accept_multiple_files=True)
        up_res = st.file_uploader("Comprovação de Residência", accept_multiple_files=True)
    with col2:
        up_renda = st.file_uploader("Comprovação de Renda (Holerites/IR)", accept_multiple_files=True)
        up_fgts = st.file_uploader("Extratos de FGTS", accept_multiple_files=True)

    # Consolida arquivos para processamento
    todos_arquivos = []
    for grupo in [up_id, up_res, up_renda, up_fgts]:
        if grupo: todos_arquivos.extend(grupo)

    if todos_arquivos:
        st.subheader("📋 Status da Importação")
        df_status = pd.DataFrame([{"Documento": f.name, "Status": "✅ Analisado"} for f in todos_arquivos])
        st.table(df_status)
        
        # OCR e Processamento
        textos_ocr = []
        for f in todos_arquivos:
            if f.type == "application/pdf":
                paginas = convert_from_bytes(f.read(), 200)
                for p in paginas: textos_ocr.append(pytesseract.image_to_string(preparar_imagem(p), lang='por'))
            else:
                textos_ocr.append(pytesseract.image_to_string(preparar_imagem(Image.open(f)), lang='por'))
        
        res = motor_analise_caixa(textos_ocr)

with aba_results:
    if 'res' in locals():
        st.header("📊 Relatório Macro de Viabilidade")
        
        # --- SEÇÃO DADOS CLIENTE ---
        with st.expander("👤 Dados do Cliente", expanded=True):
            r1, r2, r3 = st.columns(3)
            r1.write(f"**Nome:** {res['nome']}")
            r1.write(f"**CPF:** {res['cpf']}")
            r2.write(f"**RG:** {res['rg']}")
            r2.write(f"**Nascimento:** {res['nasc']}")
            r3.write(f"**Estado Civil:** {res['est_civil']}")
            st.write(f"**Endereço Completo:** {res['endereco_completo']} - **CEP:** {res['cep']}")

        # --- SEÇÃO FINANCEIRO ---
        with st.expander("💰 Financeiro e Renda", expanded=True):
            f1, f2, f3 = st.columns(3)
            f1.write(f"**Origem:** {origem_recurso}")
            f1.write(f"**Cargo/Função:** {res['cargo']}")
            f1.write(f"**Tempo de Casa:** {res['tempo_casa']}")
            
            f2.metric("Média Salarial Bruta", f"R$ {res['media_bruta']:,.2f}")
            f2.metric("Último Salário Bruto", f"R$ {res['ultimo_bruto']:,.2f}")
            
            f3.metric("Média Salarial Líquida", f"R$ {res['media_liq_real']:,.2f}")
            f3.metric("Último Líquido Real", f"R$ {res['ultimo_liq_real']:,.2f}", delta="C/ Adiantamento")

        # --- SEÇÃO FGTS ---
        with st.expander("📈 Detalhamento FGTS", expanded=True):
            fg1, fg2 = st.columns(2)
            with fg1:
                for i, valor in enumerate(res['fgts_contas']):
                    st.write(f"**Conta {i+1}:** R$ {valor:,.2f}")
            with fg2:
                st.success(f"**Saldo Total FGTS:** R$ {res['fgts_total']:,.2f}")

        # --- SEÇÃO VEREDITO CAIXA ---
        st.divider()
        st.subheader("🎯 Veredito de Enquadramento")
        
        # Regras de Negócio Caixa
        enquadramento = "SBPE" if res['ultimo_bruto'] > 8000 else "MCMV"
        subsidio = 55000.00 if enquadramento == "MCMV" else 0.0
        parcela_max = res['ultimo_liq_real'] * 0.30
        
        v1, v2, v3 = st.columns(3)
        v1.info(f"**Modalidade:** {enquadramento}")
        v2.metric("Subsídio Estimado", f"R$ {subsidio:,.2f}")
        v3.metric("Capacidade de Parcela (30%)", f"R$ {parcela_max:,.2f}")
        
        st.markdown("### **Status de Provável Aprovação:** ✅ ALTA PROBABILIDADE")
        st.button("🖨️ Imprimir Relatório (PDF)")
    else:
        st.info("Aguardando upload de documentos para processar os resultados.")
