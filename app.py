import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import re

# Título da App
st.title("🚀 Parceria Soluções - Automação Imobiliária")
st.subheader("Extração Automática de Dados para Correspondente Caixa")

# Área de Upload
arquivos = st.file_uploader("Arraste os documentos dos clientes (JPG, PNG)", accept_multiple_files=True)

if arquivos:
    lista_dados = []
    
    for arquivo in arquivos:
        # Abrir a imagem
        img = Image.open(arquivo)
        st.image(img, caption=f"Processando: {arquivo.name}", width=200)
        
        # OCR - Transformar imagem em texto
        texto = pytesseract.image_to_string(img, lang='por')
        
        # Extrair dados com Regex (Lógica que criamos antes)
        dados = {
            "Documento": arquivo.name,
            "CPF": "Não encontrado",
            "Renda": "Não encontrado",
            "Estado Civil": "Não encontrado"
        }
        
        cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto)
        if cpf: dados["CPF"] = cpf.group()
        
        renda = re.search(r'R\$\s?\d{1,3}(\.\d{3})*,\d{2}', texto)
        if renda: dados["Renda"] = renda.group()
        
        # Adicionar à lista
        lista_dados.append(dados)

    # Mostrar Tabela na tela
    df = pd.DataFrame(lista_dados)
    st.write("### Dados Extraídos:", df)

    # Botão para baixar Excel
    df.to_excel("dados_clientes.xlsx", index=False)
    with open("dados_clientes.xlsx", "rb") as f:
        st.download_button("📥 Baixar Planilha Excel", f, file_name="dados_clientes.xlsx")
