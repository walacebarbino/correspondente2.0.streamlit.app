import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime
from io import BytesIO

# Configuração de Página
st.set_page_config(page_title="Relatório de Viabilidade Caixa", layout="wide")
st.title("🏦 Relatório de Viabilidade: Correspondente Caixa")

# --- LÓGICA DE SUBSÍDIO E ENQUADRAMENTO (REGRAS ATUAIS) ---
def calcular_subsidio_mcmv(renda_bruta):
    """Calcula o subsídio máximo teórico baseado na Faixa de Renda (2025/2026)"""
    if renda_bruta <= 2850.00:
        return "Faixa 1", 55000.00, "Juros: 4% a 4.5% | Subsídio Máximo"
    elif 2850.01 <= renda_bruta <= 4700.00:
        return "Faixa 2", 55000.00, "Juros: 4.5% a 6% | Subsídio Regressivo"
    elif 4700.01 <= renda_bruta <= 8000.00:
        return "Faixa 3", 0.0, "Sem subsídio | Juros: 7.16% a 8.16% (FGTS)"
    else:
        return "SBPE", 0.0, "Linha de Mercado | Juros: TR + 9% a 10% aprox."

# --- MOTOR DE EXTRAÇÃO REFINADO (FOCO EM PRECISÃO) ---
def extrair_dados_tecnicos(texto_bruto):
    t = texto_bruto.upper()
    d = {}
    
    # Identificação
    nome = re.search(r'(?:NOME|CLIENTE|COLABORADOR)[:\s\n]+([A-Z\s]{10,})', t)
    d['Nome'] = nome.group(1).split('\n')[0].strip() if nome else "NÃO IDENTIFICADO"
    
    cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', t)
    d['CPF'] = cpf.group() if cpf else "NÃO IDENTIFICADO"

    est_civil = re.search(r'\b(SOLTEIRO|CASADO|DIVORCIADO|VIÚVO|UNIÃO ESTÁVEL|SOLTEIRA|CASADA|DIVORCIADA|VIÚVA)\b', t)
    d['Estado Civil'] = est_civil.group(1) if est_civil else "NÃO IDENTIFICADO"

    # Residência (CEP e Endereço)
    cep = re.search(r'(?:CEP)[:\s]*(\d{5}-\d{3})|(\d{5}-\d{3})', t)
    d['CEP'] = cep.group(0) if cep else "NÃO IDENTIFICADO"
    
    # Financeiro (Bruto, Descontos, Líquido)
    bruto = re.findall(r'(?:BRUTO|VENCIMENTOS|TOTAL PROVENTOS)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', t)
    desc = re.findall(r'(?:DESCONTOS|TOTAL DESCONTOS)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', t)
    liq = re.findall(r'(?:LÍQUIDO|VALOR RECEBIDO|PAGAMENTO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', t)

    d['Bruto_Val'] = float(bruto[0].replace('.','').replace(',','.')) if bruto else 0.0
    d['Desc_Val'] = float(desc[0].replace('.','').replace(',','.')) if desc else 0.0
    d['Liq_Val'] = float(liq[-1].replace('.','').replace(',','.')) if liq else 0.0
    
    # FGTS e Vínculo
    fgts = re.findall(r'(?:SALDO FGTS|FGTS)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', t)
    d['FGTS_Val'] = float(fgts[0].replace('.','').replace(',','.')) if fgts else 0.0
    
    adm = re.search(r'(?:ADMISSÃO|ADM)[:\s]*(\d{2}/\d{2}/\d{4})', t)
    d['Admissao'] = adm.group(1) if adm else "N/A"

    return d

# --- INTERFACE E PROCESSAMENTO ---
upload = st.file_uploader("📂 Importar Dossier do Cliente (PDF/Imagens)", accept_multiple_files=True)

if upload:
    full_text = ""
    status_docs = []
    for f in upload:
        if f.type == "application/pdf":
            paginas = convert_from_bytes(f.read())
            for p in paginas:
                img = ImageOps.grayscale(p)
                full_text += pytesseract.image_to_string(img, lang='por')
        else:
            img = ImageOps.grayscale(Image.open(f))
            full_text += pytesseract.image_to_string(img, lang='por')
        status_docs.append({"Documento": f.name, "Análise": "Concluída ✅"})

    # 1. Lista de Documentos e Checklist
    st.subheader("📑 Documentos Processados")
    st.table(status_docs)

    if full_text:
        res = extrair_dados_tecnicos(full_text)
        faixa, valor_sub, detalhes = calcular_subsidio_mcmv(res['Bruto_Val'])

        st.divider()

        # 2. Relatório de Identificação [Pilar 1 e 2]
        st.subheader("👤 Identificação e Residência")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.write(f"**Nome:** {res['Nome']}")
            st.write(f"**CPF:** {res['CPF']}")
        with c2:
            st.write(f"**Estado Civil:** {res['Estado Civil']}")
            st.write(f"**CEP:** {res['CEP']}")
        with c3:
            st.write(f"**Admissão:** {res['Admissao']}")
            st.write(f"**Saldo FGTS:** R$ {res['FGTS_Val']:,.2f}")

        st.divider()

        # 3. Análise de Renda e Viabilidade [Pilar 3, 4 e 5]
        st.subheader("💰 Capacidade Financeira e Subsídio")
        f1, f2, f3 = st.columns(3)
        
        f1.metric("Renda Bruta (MCMV)", f"R$ {res['Bruto_Val']:,.2f}")
        f2.metric("Renda Líquida Final", f"R$ {res['Liq_Val']:,.2f}")
        
        # Cálculo da Parcela Máxima (30% da renda líquida)
        parcela_max = res['Liq_Val'] * 0.3
        f3.metric("Parcela Máxima (30%)", f"R$ {parcela_max:,.2f}", delta="Capacidade Mensal")

        # Exibição do Subsídio
        st.success(f"**Resultado:** {faixa} | **Subsídio Estimado:** R$ {valor_sub:,.2f}")
        st.info(f"**Nota Técnica:** {detalhes}")

        # 4. Exportação
        st.divider()
        df_export = pd.DataFrame([{
            "Cliente": res['Nome'], "Renda Bruta": res['Bruto_Val'], 
            "Renda Liquida": res['Liq_Val'], "Parcela Max": parcela_max,
            "Enquadramento": faixa, "Subsidio": valor_sub
        }])
        
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False)
            st.download_button("📊 Exportar para Excel", data=buffer.getvalue(), file_name="analise_viabilidade.xlsx")
        with col_ex2:
            st.caption("Para exportar em PDF, utilize a função 'Imprimir' do navegador selecionando 'Salvar como PDF'.")
