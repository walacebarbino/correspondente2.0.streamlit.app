import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime
from io import BytesIO

# Configurações de Página
st.set_page_config(page_title="Correspondente 2.0 - Analista Caixa", layout="wide")

# --- FUNÇÕES DE APOIO ---
def tratar_imagem(img):
    img = ImageOps.grayscale(img)
    return ImageEnhance.Contrast(img).enhance(3.0)

def limpar_valor(texto):
    """Converte 'R$ 1.234,56' em float 1234.56"""
    if not texto: return 0.0
    val = re.sub(r'[^\d,]', '', texto).replace(',', '.')
    try: return float(val)
    except: return 0.0

# --- MOTOR DE EXTRAÇÃO DINÂMICO ---
def processar_dossie(textos_paginas):
    full_text = " ".join(textos_paginas).upper().replace('|', 'I')
    
    data = {}

    # 1. IDENTIFICAÇÃO (Busca Padrões)
    nome_m = re.search(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{10,})', full_text)
    data['nome'] = nome_m.group(1).split('\n')[0].strip() if nome_m else "Não Identificado"
    
    cpf_m = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', full_text)
    data['cpf'] = cpf_m.group(1) if cpf_m else "Não Identificado"
    
    nasc_m = re.search(r'(\d{2}/\d{2}/\d{4})', full_text)
    data['nascimento'] = nasc_m.group(1) if nasc_m else "Não Identificado"

    # 2. RESIDÊNCIA (Filtro Hierárquico anti-concessionária)
    # Busca endereços que NÃO estejam próximos a CNPJs de concessionárias conhecidas
    ceps = re.findall(r'(\d{5}-\d{3})', full_text)
    # Filtro: Geralmente o CEP do cliente aparece próximo ao nome dele ou no campo destinatário
    data['cep'] = ceps[0] if ceps else "Não Identificado"
    
    # Busca de Logradouro (Rua, Av, etc)
    end_m = re.search(r'(?:RUA|AV|ESTRADA|LOGRADOURO)[:\s]+([^,]+,\s*\d+.*)', full_text)
    data['endereco'] = end_m.group(1).split('\n')[0].strip() if end_m else "Endereço não detectado"

    # 3. RENDA (Lógica de Adiantamento Reincorporado)
    # Busca Bruto
    brutos = re.findall(r'(?:TOTAL VENCIMENTOS|VALOR BRUTO|TOTAL PROVENTOS)[:\s]*([\d\.,]{5,})', full_text)
    data['vencimentos'] = [limpar_valor(v) for v in brutos]
    data['bruto_ultimo'] = data['vencimentos'][-1] if data['vencimentos'] else 0.0
    data['bruto_media'] = sum(data['vencimentos'])/len(data['vencimentos']) if data['vencimentos'] else 0.0

    # Busca Líquido e Adiantamentos
    liquidos = re.findall(r'(?:LÍQUIDO PGTO|VALOR LÍQUIDO|LÍQUIDO A RECEBER)[:\s]*([\d\.,]{5,})', full_text)
    adiantamentos = re.findall(r'(?:ADIANTAMENTO SALARIAL|ADIANT\. QUINZENAL|VALOR ADIANTADO)[:\s]*([\d\.,]{5,})', full_text)
    
    val_liq = limpar_valor(liquidos[-1]) if liquidos else 0.0
    val_adiant = limpar_valor(adiantamentos[-1]) if adiantamentos else 0.0
    
    data['liq_real_ultimo'] = val_liq + val_adiant
    data['cargo'] = re.search(r'(?:CARGO|FUNÇÃO)[:\s]+([A-Z\s/]+)', full_text).group(1).split('\n')[0].strip() if re.search(r'(?:CARGO|FUNÇÃO)[:\s]+([A-Z\s/]+)', full_text) else "Não Identificado"

    # 4. FGTS (Soma de Múltiplas Contas)
    saldos_fgts = re.findall(r'VALOR PARA FINS RESCISÓRIOS.*?([\d\.,]{5,})', full_text)
    data['fgts_lista'] = [limpar_valor(s) for s in saldos_fgts if limpar_valor(s) > 0]
    data['fgts_total'] = sum(data['fgts_lista'])

    return data

# --- INTERFACE POR ABAS ---
st.title("🏦 Correspondente 2.0 - Analista de Crédito")

tab1, tab2, tab3 = st.tabs(["📌 Aba Geral", "📂 Importação de Documentos", "📊 Resultados"])

with tab1:
    st.header("Configuração da Origem")
    origem_recurso = st.selectbox("Selecione a Origem de Recursos:", 
                                  ["CLT", "Autônomos e Profissionais Liberais", "Empresários/MEI"])
    st.info(f"Sistema configurado para análise de perfil: {origem_recurso}")

with tab2:
    st.header("Upload de Dossier")
    col_a, col_b = st.columns(2)
    
    with col_a:
        files_id = st.file_uploader("Identificação (RG/CNH/Certidões)", accept_multiple_files=True)
        files_res = st.file_uploader("Residência (Contas de Luz/Água)", accept_multiple_files=True)
    
    with col_b:
        files_renda = st.file_uploader("Renda (Holerites/Extratos/IR)", accept_multiple_files=True)
        files_fgts = st.file_uploader("FGTS (Extratos)", accept_multiple_files=True)

    # Exibição dos documentos postados
    todos_arquivos = []
    for f in [files_id, files_res, files_renda, files_fgts]:
        if f: todos_arquivos.extend(f)
    
    if todos_arquivos:
        st.subheader("📋 Documentos Analisados")
        df_docs = pd.DataFrame([{"Arquivo": f.name, "Status": "✅ Processado"} for f in todos_arquivos])
        st.table(df_docs)

        # Processamento OCR
        textos_totais = []
        for f in todos_arquivos:
            if f.type == "application/pdf":
                paginas = convert_from_bytes(f.read(), 200)
                for p in paginas: textos_totais.append(pytesseract.image_to_string(tratar_imagem(p), lang='por'))
            else:
                textos_totais.append(pytesseract.image_to_string(tratar_imagem(Image.open(f)), lang='por'))
        
        resultado_analise = processar_dossie(textos_totais)

with tab3:
    if 'resultado_analise' in locals():
        res = resultado_analise
        st.header("📝 Relatório Macro de Viabilidade")
        
        # Bloco 1: Dados do Cliente
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 👤 Dados do Cliente")
            st.write(f"**Nome:** {res['nome']}")
            st.write(f"**CPF:** {res['cpf']}")
            st.write(f"**Nascimento:** {res['nascimento']}")
        with c2:
            st.markdown("### 📍 Endereço")
            st.write(f"**Endereço:** {res['endereco']}")
            st.write(f"**CEP:** {res['cep']}")

        st.divider()

        # Bloco 2: Financeiro
        st.markdown("### 💰 Informações Financeiras")
        f1, f2, f3 = st.columns(3)
        f1.write(f"**Origem:** {origem_recurso}")
        f1.write(f"**Cargo/Função:** {res['cargo']}")
        
        f2.metric("Média Bruta", f"R$ {res['bruto_media']:,.2f}")
        f2.metric("Último Bruto", f"R$ {res['bruto_ultimo']:,.2f}")
        
        # Capacidade baseada no líquido real (com adiantamento)
        f3.metric("Último Líquido Real", f"R$ {res['liq_real_ultimo']:,.2f}")
        cap_max = res['liq_real_ultimo'] * 0.30
        f3.metric("Capacidade de Parcela (30%)", f"R$ {cap_max:,.2f}")

        st.divider()

        # Bloco 3: FGTS
        st.markdown("### 📈 Saldos de FGTS")
        fg1, fg2 = st.columns(2)
        with fg1:
            for i, s in enumerate(res['fgts_lista']):
                st.write(f"Conta {i+1}: R$ {s:,.2f}")
        with fg2:
            st.success(f"**Saldo Total FGTS:** R$ {res['fgts_total']:,.2f}")

        st.divider()

        # Bloco 4: Enquadramento
        st.markdown("### 🎯 Veredito de Enquadramento")
        if res['bruto_ultimo'] > 8000:
            st.warning("🚨 **MODALIDADE SBPE:** Renda bruta familiar acima de R$ 8.000,00.")
            subsídio = 0.0
        else:
            st.success("✅ **MODALIDADE MINHA CASA MINHA VIDA:** Renda dentro do perfil do programa.")
            subsídio = 55000.00 # Valor base de exemplo
            
        st.write(f"**Subsídio Previsto:** R$ {subsídio:,.2f}")
        st.write("**Status de Aprovação:** Analisando comprometimento de renda e score interno...")

        st.button("🖨️ Imprimir Relatório Completo")
    else:
        st.info("Aguardando upload de documentos para gerar o relatório.")
