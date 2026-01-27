import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime
from dateutil.relativedelta import relativedelta
from io import BytesIO

st.set_page_config(page_title="Correspondente 2.0", layout="wide")
st.title("🏦 Correspondente 2.0: Analista de Crédito Caixa")

# --- MOTOR DE TRATAMENTO DE IMAGEM ---
def tratar_imagem(img):
    img = ImageOps.grayscale(img)
    return ImageEnhance.Contrast(img).enhance(2.5)

# --- LÓGICA DE SUBSÍDIO E REGRAS CAIXA (2026) ---
def calcular_regras_caixa(bruto, liquido):
    # Enquadramento por Renda Bruta
    if bruto <= 2850.00:
        faixa, subsidio, taxa = "Faixa 1", 55000.00, "4.00% a 4.50%"
    elif bruto <= 4700.00:
        faixa, subsidio, taxa = "Faixa 2", 55000.00, "4.50% a 6.00%"
    elif bruto <= 8000.00:
        faixa, subsidio, taxa = "Faixa 3", 0.0, "7.16% a 8.16%"
    else:
        faixa, subsidio, taxa = "SBPE", 0.0, "9.00% + TR"
    
    # Capacidade de Pagamento (30% do Líquido)
    capacidade = liquido * 0.30
    
    return {
        "Faixa": faixa,
        "Subsidio_Max": subsidio,
        "Taxa_Juros": taxa,
        "Capacidade_Mensal": capacidade
    }

# --- MOTOR DE EXTRAÇÃO DE DADOS ---
def analisar_documentos(texto_total):
    t = texto_total.upper()
    d = {}
    
    # 1. IDENTIFICAÇÃO
    d['Nome'] = (re.search(r'(?:NOME|CLIENTE|COLABORADOR)[:\s\n]+([A-Z\s]{10,})', t).group(1).split('\n')[0].strip() 
                 if re.search(r'(?:NOME|CLIENTE|COLABORADOR)[:\s\n]+([A-Z\s]{10,})', t) else "N/A")
    d['CPF'] = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', t).group() if re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', t) else "N/A"
    d['RG_CNH'] = re.search(r'(?:\d[\d\.]{6,12}-\d|RG\s\d{7,10}|CNH\s\d{10,12})', t).group() if re.search(r'(?:\d[\d\.]{6,12}-\d|RG\s\d{7,10}|CNH\s\d{10,12})', t) else "N/A"
    d['Estado_Civil'] = re.search(r'\b(SOLTEIRO|CASADO|DIVORCIADO|VIÚVO|UNIÃO ESTÁVEL)\b', t).group(1) if re.search(r'\b(SOLTEIRO|CASADO|DIVORCIADO|VIÚVO|UNIÃO ESTÁVEL)\b', t) else "N/A"
    d['Nascimento'] = re.search(r'(?:NASCIMENTO|NASC)[:\s]*(\d{2}/\d{2}/\d{4})', t).group(1) if re.search(r'(?:NASCIMENTO|NASC)[:\s]*(\d{2}/\d{2}/\d{4})', t) else "N/A"

    # 2. RESIDÊNCIA
    d['CEP'] = re.search(r'(\d{5}-\d{3})', t).group(1) if re.search(r'(\d{5}-\d{3})', t) else "N/A"
    end_match = re.search(r'(?:RUA|AV|LOGRADOURO)[:\s]+([^,]+,[^,]+,[^,]+,[^,]+)', t)
    d['Endereco'] = end_match.group(1).strip() if end_match else "NÃO IDENTIFICADO"

    # 3. RENDA (Lógica de Adiantamento)
    bruto_vals = re.findall(r'(?:VENCIMENTOS|PROVENTOS|VALOR BRUTO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', t)
    liq_vals = re.findall(r'(?:LÍQUIDO|VALOR LÍQUIDO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', t)
    adiantamento = re.findall(r'(?:ADIANTAMENTO|VALOR ADIANT)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', t)
    
    val_bruto = float(bruto_vals[0].replace('.','').replace(',','.')) if bruto_vals else 0.0
    val_liq = float(liq_vals[-1].replace('.','').replace(',','.')) if liq_vals else 0.0
    val_adiant = float(adiantamento[0].replace('.','').replace(',','.')) if adiantamento else 0.0
    
    d['Bruto'] = val_bruto
    d['Liquido_Ajustado'] = val_liq + val_adiant

    # TEMPO DE CASA
    adm_match = re.search(r'(?:ADMISSÃO|ADM)[:\s]*(\d{2}/\d{2}/\d{4})', t)
    if adm_match:
        dt_adm = datetime.strptime(adm_match.group(1), '%d/%m/%Y')
        diff = relativedelta(datetime.now(), dt_adm)
        d['Tempo_Casa'] = f"{diff.years} anos, {diff.months} meses e {diff.days} dias"
    else: d['Tempo_Casa'] = "N/A"

    # 4. FGTS
    contas_fgts = re.findall(r'(?:SALDO DO FGTS|SALDO DISPONÍVEL)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', t)
    saldos = [float(v.replace('.','').replace(',','.')) for v in contas_fgts]
    d['FGTS_Individual'] = saldos
    d['FGTS_Total'] = sum(saldos)

    return d

# --- INTERFACE ---
st.subheader("📁 Importação de Dossier")
upload = st.file_uploader("Arraste os documentos (PDF/Imagens)", accept_multiple_files=True)

if upload:
    full_text = ""
    docs_status = []
    for f in upload:
        if f.type == "application/pdf":
            paginas = convert_from_bytes(f.read())
            for p in paginas: full_text += pytesseract.image_to_string(tratar_imagem(p), lang='por')
        else:
            full_text += pytesseract.image_to_string(tratar_imagem(Image.open(f)), lang='por')
        docs_status.append({"Arquivo": f.name, "Análise": "✅ Concluída"})

    st.table(docs_status)

    if full_text:
        res = analisar_documentos(full_text)
        caixa = calcular_regras_caixa(res['Bruto'], res['Liquido_Ajustado'])

        # --- RELATÓRIO MACRO ---
        st.divider()
        st.header("📋 Relatório Macro de Viabilidade")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 1. Identificação")
            st.write(f"**Nome:** {res['Nome']}")
            st.write(f"**CPF:** {res['CPF']} | **Doc:** {res['RG_CNH']}")
            st.write(f"**Estado Civil:** {res['Estado_Civil']}")
            st.write(f"**Nascimento:** {res['Nascimento']}")

            st.markdown("### 2. Residência")
            st.write(f"**Endereço:** {res['Endereco']}")
            st.write(f"**CEP:** {res['CEP']}")

        with c2:
            st.markdown("### 3. Análise de Renda")
            st.write(f"**Salário Bruto:** R$ {res['Bruto']:,.2f}")
            st.write(f"**Líquido (+ Adiantamento):** R$ {res['Liquido_Ajustado']:,.2f}")
            st.write(f"**Tempo de Casa:** {res['Tempo_Casa']}")

            st.markdown("### 4. Vínculo FGTS")
            st.write(f"**Saldos por Conta:** {res['FGTS_Individual']}")
            st.success(f"**Total FGTS Disponível:** R$ {res['FGTS_Total']:,.2f}")

        st.divider()
        st.header("🎯 Enquadramento e Aprovação")
        
        e1, e2, e3 = st.columns(3)
        e1.metric("Enquadramento", caixa['Faixa'])
        e2.metric("Subsídio Estimado", f"R$ {caixa['Subsidio_Max']:,.2f}")
        e3.metric("Capacidade de Prestação", f"R$ {caixa['Capacidade_Mensal']:,.2f}")
        
        st.info(f"**Taxa de Juros Aplicável:** {caixa['Taxa_Juros']}")

        # --- EXPORTAÇÃO ---
        st.divider()
        df_export = pd.DataFrame([{**res, **caixa}])
        
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False)
            st.download_button("📊 Exportar para Excel", data=buffer.getvalue(), file_name="correspondente_macro.xlsx")
