import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import re
from pdf2image import convert_from_bytes

# 1. Mudança de Nome conforme solicitado
st.set_page_config(page_title="Parceria - Correspondente 2.0", layout="wide")
st.title("🏦 Parceria - Correspondente 2.0")
st.subheader("Análise de Conformidade e Extração Automática")

def analisar_regras_caixa(dados):
    """Função para verificar inconformidades com regras da Caixa"""
    alertas = []
    
    # Exemplo Regra MCMV (Faixa 3 - teto de 8k)
    try:
        valor_renda = float(dados['Renda'].replace('R$', '').replace('.', '').replace(',', '.').strip())
        if valor_renda > 8000:
            alertas.append("⚠️ Renda acima do limite para MCMV (Faixa 3).")
    except:
        pass

    # Exemplo Regra de Documentação
    if dados['CPF'] == "Não encontrado":
        alertas.append("❌ CPF não identificado ou ilegível.")
    
    return " | ".join(alertas) if alertas else "✅ Em conformidade inicial"

arquivos = st.file_uploader("Suba Documentos (PDF, JPG, PNG)", accept_multiple_files=True)

if arquivos:
    lista_resultados = []
    for arq in arquivos:
        # Lógica para aceitar PDF e Imagem
        if arq.type == "application/pdf":
            paginas = convert_from_bytes(arq.read())
            img = paginas[0] # Analisa a primeira página
        else:
            img = Image.open(arq)
        
        texto = pytesseract.image_to_string(img, lang='por')
        
        # Extração
        cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto)
        renda = re.search(r'R\$\s?\d{1,3}(\.\d{3})*,\d{2}', texto)
        
        dados_extraidos = {
            "Arquivo": arq.name,
            "CPF": cpf.group() if cpf else "Não encontrado",
            "Renda": renda.group() if renda else "Não encontrado"
        }
        
        # Inserindo a inteligência de análise
        dados_extraidos["Análise de Regras"] = analisar_regras_caixa(dados_extraidos)
        lista_resultados.append(dados_extraidos)

    df = pd.DataFrame(lista_resultados)
    st.dataframe(df, use_container_width=True)
    
    # Botão de Exportação
    df.to_excel("analise_caixa.xlsx", index=False)
    st.download_button("📥 Baixar Relatório de Inconformidades", open("analise_caixa.xlsx", "rb"), file_name="analise.xlsx")
