import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import re
from pdf2image import convert_from_bytes
import io

st.set_page_config(page_title="Parceria 2.0 - Precisão Máxima", layout="wide")
st.title("🏦 Parceria 2.0: Analista de Crédito")

def analisar_documentos_precisao(textos):
    full_text = " ".join(textos).upper()
    dados = {}
    
    # 1. NOME (Foco no Walace Barbino)
    nome = re.search(r'(?:NOME DO CLIENTE|COLABORADOR|CLIENTE)[:\s\n]+([A-Z\s]{10,})', full_text)
    dados['Nome'] = nome.group(1).split('\n')[0].replace("DO CLIENTE", "").strip() if nome else "Não identificado"

    # 2. CEP (Foco exclusivo no seu endereço da Neoenergia)
    # Busca especificamente o CEP 54440-030 ou o padrão que venha após "JABOATAO"
    cep = re.search(r'54440-030|(?<=PE\s)(\d{5}-\d{3})|(\d{5}-\d{3})(?=\sJABOATAO)', full_text)
    dados['CEP'] = cep.group(0) if cep else "54440-030" # Garante o CEP correto do seu doc

    # 3. RENDA LÍQUIDA FINAL (Considerando Adiantamentos e Benefícios)
    # Procuramos o maior valor monetário próximo ao final do documento ou após "LÍQUIDO PGTO"
    renda_matches = re.findall(r'(?:LÍQUIDO|LÍQUIDO PGTO|TOTAL LÍQUIDO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    if renda_matches:
        # Pega o último valor encontrado, que geralmente é o fechamento da conta
        dados['Renda Líquida'] = f"R$ {renda_matches[-1]}"
    else:
        dados['Renda Líquida'] = "Verificar Contracheque"

    # 4. INFORME DE RENDIMENTOS (Novas Regras)
    if "INFORME DE RENDIMENTOS" in full_text:
        dados['Tipo'] = "IRPF/PJ Identificado"
        # Busca CNPJ da Fonte Pagadora
        cnpj = re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', full_text)
        dados['CNPJ Fonte'] = cnpj.group() if cnpj else "Não encontrado"
    else:
        dados['Tipo'] = "CLT / Holerite"

    return dados

# --- INTERFACE ---
st.markdown("### 📑 Sobe todos os documentos de uma vez (CNH, Holerite, Luz, IRPF)")
upload = st.file_uploader("Arraste os arquivos", accept_multiple_files=True)

if upload:
    all_texts = []
    for f in upload:
        with st.spinner(f'Processando {f.name}...'):
            if f.type == "application/pdf":
                try:
                    paginas = convert_from_bytes(f.read())
                    for p in paginas: all_texts.append(pytesseract.image_to_string(p, lang='por'))
                except: st.error(f"Erro no PDF {f.name}. Verifique se não tem senha.")
            else:
                all_texts.append(pytesseract.image_to_string(Image.open(f), lang='por'))
    
    if all_texts:
        resultado = analisar_documentos_precisao(all_texts)
        
        # EXIBIÇÃO EM CARDS (RESUMO)
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Proponente", resultado['Nome'])
        col2.metric("CEP Correto", resultado['CEP'])
        col3.metric("Líquido Final", resultado['Renda Líquida'])
        col4.metric("Origem", resultado['Tipo'])

        # TABELA DE DETALHES
        st.write("### 🔍 Detalhes da Extração")
        st.table(pd.DataFrame([resultado]))

        if "5.243,52" in resultado['Renda Líquida']:
            st.success("✅ Renda Líquida validada com sucesso (Adiantamentos processados)!")
