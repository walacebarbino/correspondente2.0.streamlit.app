import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime

st.set_page_config(page_title="Parceria 2.0 - Inteligência Caixa", layout="wide")
st.title("🏦 Parceria 2.0: Analista de Crédito & Modalidades Caixa")

def tratar_imagem(imagem_pil):
    img = ImageOps.grayscale(imagem_pil)
    enhancer = ImageEnhance.Contrast(img)
    return enhancer.enhance(2.5)

def definir_modalidade_caixa(renda, tempo_fgts_anos, saldo_fgts):
    """Lógica de decisão das modalidades de crédito da Caixa"""
    if renda <= 8000:
        return {
            "Modalidade": "Minha Casa, Minha Vida (MCMV)",
            "Vantagem": "Juros baixos e possível Subsídio.",
            "Sugestão": "Utilizar FGTS para abater a entrada."
        }
    elif tempo_fgts_anos >= 3 and renda > 8000:
        return {
            "Modalidade": "Pró-Cotista FGTS",
            "Vantagem": "Taxa de juros menor que o SBPE comum.",
            "Sugestão": "Excelente para quem tem carreira longa no regime CLT."
        }
    else:
        return {
            "Modalidade": "SBPE (Poupança)",
            "Vantagem": "Liberdade de escolha do imóvel e valores maiores.",
            "Sugestão": "Opção para rendas altas ou sem vínculo FGTS longo."
        }

def extrair_dados_caixa(textos):
    full_text = " ".join(textos).upper()
    dados = {}
    
    # --- EXTRAÇÃO BÁSICA ---
    nome = re.search(r'(?:NOME|CLIENTE|COLABORADOR)[:\s\n]+([A-Z\s]{10,})', full_text)
    dados['Nome'] = nome.group(1).split('\n')[0].strip() if nome else "Não identificado"
    
    # --- FINANCEIRO ---
    liq = re.findall(r'(?:LÍQUIDO|LÍQUIDO PGTO|TOTAL LÍQUIDO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    renda_val = float(liq[-1].replace('.', '').replace(',', '.')) if liq else 0.0
    dados['Renda Líquida'] = renda_val

    # FGTS Total
    fgts_vals = re.findall(r'(?:FGTS|SALDO FGTS)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    total_fgts = sum([float(v.replace('.','').replace(',','.')) for v in fgts_vals])
    dados['FGTS'] = total_fgts

    # Tempo de Casa (Estimativa por Admissão)
    adm = re.search(r'(?:ADMISSÃO|ADM)[:\s]*(\d{2}/\d{2}/\d{4})', full_text)
    anos_casa = 0
    if adm:
        data_adm = datetime.strptime(adm.group(1), '%d/%m/%Y')
        anos_casa = (datetime.now() - data_adm).days / 365
    
    # --- INTELIGÊNCIA CAIXA ---
    analise_modalidade = definir_modalidade_caixa(renda_val, anos_casa, total_fgts)
    dados.update(analise_modalidade)

    return dados

# --- INTERFACE ---
upload = st.file_uploader("Suba os documentos para definir a melhor modalidade", accept_multiple_files=True)

if upload:
    all_texts = []
    for f in upload:
        with st.spinner(f'Lendo {f.name}...'):
            if f.type == "application/pdf":
                paginas = convert_from_bytes(f.read())
                for p in paginas: all_texts.append(pytesseract.image_to_string(tratar_imagem(p), lang='por'))
            else:
                all_texts.append(pytesseract.image_to_string(tratar_imagem(Image.open(f)), lang='por'))
    
    if all_texts:
        res = extrair_dados_caixa(all_texts)
        
        st.markdown("### 🏆 Melhor Modalidade para este Perfil")
        
        col1, col2 = st.columns([1, 1.5])
        with col1:
            st.metric("Modalidade Recomendada", res['Modalidade'])
            st.write(f"**Por que?** {res['Vantagem']}")
        
        with col2:
            st.success(f"💡 **Dica do Especialista:** {res['Sugestão']}")
            st.write(f"**Renda Analisada:** R$ {res['Renda Líquida']:,.2f}")
            st.write(f"**FGTS Disponível:** R$ {res['FGTS']:,.2f}")

        st.markdown("---")
        # Tabela completa
        st.dataframe(pd.DataFrame([res]), use_container_width=True)
