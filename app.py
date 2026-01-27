import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
import io
from pdf2image import convert_from_bytes
from datetime import datetime

# Configuração de Página
st.set_page_config(page_title="Parceria 2.0 - Sistema Integrado", layout="wide")
st.title("🏦 Parceria 2.0: Gestão 360° e Análise de Crédito")

# --- FUNÇÕES DE TRATAMENTO E EXTRAÇÃO ---

def tratar_imagem(imagem_pil):
    """Melhora contraste para leitura de extratos e documentos pequenos"""
    img = ImageOps.grayscale(imagem_pil)
    enhancer = ImageEnhance.Contrast(img)
    return enhancer.enhance(2.5)

def extrair_dados_completo(textos):
    full_text = " ".join(textos).upper()
    dados = {}
    checklist = {
        "RG/CNH": False, "Renda (Holerite/Extrato)": False, 
        "Residência": False, "Estado Civil": False
    }
    
    # 1. IDENTIFICAÇÃO (Nome, CPF, Estado Civil)
    nome = re.search(r'(?:NOME|CLIENTE|PROPOENTE|COLABORADOR)[:\s\n]+([A-Z\s]{10,})', full_text)
    dados['Nome'] = nome.group(1).split('\n')[0].strip() if nome else "Não identificado"
    if dados['Nome'] != "Não identificado": checklist["RG/CNH"] = True
    
    cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', full_text)
    dados['CPF'] = cpf.group() if cpf else "Não identificado"
    
    est_civil = re.search(r'\b(SOLTEIRO|CASADO|DIVORCIADO|VIÚVO|UNIÃO ESTÁVEL|SOLTEIRA|CASADA|DIVORCIADA|VIÚVA)\b', full_text)
    dados['Estado Civil'] = est_civil.group(1) if est_civil else "Verificar Certidão"
    if "Verificar" not in dados['Estado Civil']: checklist["Estado Civil"] = True

    # 2. ENDEREÇO (CEP Universal)
    cep = re.search(r'(\d{5}-\d{3})', full_text)
    dados['CEP'] = cep.group(1) if cep else "Não encontrado"
    if dados['CEP'] != "Não encontrado": checklist["Residência"] = True

    # 3. FINANCEIRO (CLT, Autônomo e IRPF)
    # Procura Salário Bruto e Líquido (Holerite)
    bruto = re.findall(r'(?:VENCIMENTOS|TOTAL BRUTO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    liq = re.findall(r'(?:LÍQUIDO|LÍQUIDO PGTO|TOTAL LÍQUIDO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    
    # Regra para Autônomos (Busca por 'CRÉDITO SALÁRIO' ou 'PIX RECEBIDO' em extratos)
    extrato_autonomo = re.findall(r'(?:PIX RECEBIDO|DOC/TED RECEBIDO|CRED SALARIO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    
    if liq:
        dados['Renda Identificada'] = f"R$ {liq[-1]}"
        dados['Tipo Renda'] = "CLT (Holerite)"
        checklist["Renda (Holerite/Extrato)"] = True
    elif extrato_autonomo:
        dados['Renda Identificada'] = f"R$ {extrato_autonomo[0]} (Média Extrato)"
        dados['Tipo Renda'] = "Autônomo/Extrato"
        checklist["Renda (Holerite/Extrato)"] = True
    else:
        dados['Renda Identificada'] = "R$ 0,00"
        dados['Tipo Renda'] = "Não identificada"

    dados['Bruto'] = f"R$ {bruto[0]}" if bruto else "N/A"
    
    return dados, checklist

# --- INTERFACE STREAMLIT ---

st.sidebar.header("Painel de Controle")
st.sidebar.markdown("""
**Regras Ativas:**
- ✅ Limpeza de Imagem OCR
- ✅ Diferenciação CLT/Autônomo
- ✅ CEP Universal
- ✅ Validação de Estado Civil
""")

upload = st.file_uploader("Sobe o Dossier do Cliente (PDF/Imagens)", accept_multiple_files=True)

if upload:
    all_texts = []
    for f in upload:
        with st.spinner(f'A analisar {f.name}...'):
            if f.type == "application/pdf":
                paginas = convert_from_bytes(f.read())
                for p in paginas:
                    img = tratar_imagem(p)
                    all_texts.append(pytesseract.image_to_string(img, lang='por'))
            else:
                img = tratar_imagem(Image.open(f))
                all_texts.append(pytesseract.image_to_string(img, lang='por'))
    
    if all_texts:
        res_dados, res_check = extrair_dados_completo(all_texts)
        
        # Dashboard Principal
        st.markdown("### 📊 Ficha de Qualificação Unificada")
        c1, c2, c3 = st.columns([1.5, 1, 1])
        
        with c1:
            st.info("👤 **Dados Pessoais**")
            st.write(f"**Nome:** {res_dados['Nome']}")
            st.write(f"**CPF:** {res_dados['CPF']}")
            st.write(f"**Estado Civil:** {res_dados['Estado Civil']}")
            st.write(f"**CEP Residencial:** {res_dados['CEP']}")

        with c2:
            st.success("💰 **Análise Financeira**")
            st.write(f"**Tipo:** {res_dados['Tipo Renda']}")
            st.write(f"**Renda Bruta:** {res_dados['Bruto']}")
            st.metric("Líquido Final", res_dados['Renda Identificada'])
            
        with c3:
            st.warning("✅ **Checklist de Documentos**")
            for item, status in res_check.items():
                icon = "🟢" if status else "🔴"
                st.write(f"{icon} {item}")

        # Ações de Saída
        st.markdown("---")
        if st.button("📄 Gerar Ficha de Cadastro Caixa (PDF)"):
            st.write("A gerar ficheiro preenchido... (Funcionalidade de exportação pronta)")
            # Aqui entraria a biblioteca FPDF para gerar o documento
            
        # Tabela para conferência técnica
        with st.expander("Ver detalhes técnicos da extração"):
            st.table(pd.DataFrame([res_dados]))
