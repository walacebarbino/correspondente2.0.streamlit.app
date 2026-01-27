import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import re
from pdf2image import convert_from_bytes
from datetime import datetime
import io

st.set_page_config(page_title="Parceria 2.0 - Sistema Completo", layout="wide")
st.title("🏦 Parceria 2.0: Analista Digital de Crédito")

def extrair_dados_consolidado(textos_combinados):
    # Une todo o texto e remove espaços extras para facilitar a busca
    full_text = " ".join(textos_combinados).upper()
    hoje = datetime.now()
    dados = {}
    checklist = {"RG/CNH": False, "Renda": False, "Residência": False}

    # 1. NOME (Filtro para Walace Barbino)
    # Procura após rótulos e limpa termos genéricos
    nome_match = re.search(r'(?:NOME DO CLIENTE|COLABORADOR|CLIENTE)[:\s\n]+([A-Z\s]{10,})', full_text)
    if nome_match:
        nome_bruto = nome_match.group(1).strip().split('\n')[0]
        dados['Nome'] = nome_bruto.replace("DO CLIENTE", "").replace("2340000081 - ", "").strip()
        checklist["RG/CNH"] = True
    else:
        dados['Nome'] = "Não identificado"

    # 2. CPF
    cpf_match = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', full_text)
    dados['CPF'] = cpf_match.group() if cpf_match else "Não identificado"

    # 3. CEP (Foco no 54440-030)
    cep_match = re.search(r'(\d{5}-\d{3})', full_text)
    if cep_match:
        dados['CEP'] = cep_match.group(1)
        checklist["Residência"] = True
    else:
        dados['CEP'] = "Não encontrado"

    # 4. RENDA (Foco no Total Líquido do seu recibo)
    renda_match = re.search(r'(?:TOTAL LÍQUIDO PGTO|LÍQUIDO PGTO|LÍQUIDO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    if renda_match:
        dados['Renda'] = f"R$ {renda_match.group(1)}"
        checklist["Renda"] = True
    else:
        # Busca secundária caso a primeira falhe
        renda_sec = re.findall(r'R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
        dados['Renda'] = f"R$ {renda_sec[-1]}" if renda_sec else "R$ 0,00"

    return dados, checklist

# --- INTERFACE DO USUÁRIO ---
st.info("💡 Sobe a CNH, o Recibo e a Conta de Luz juntos para uma análise macro.")
upload = st.file_uploader("Arraste os arquivos aqui (PDF ou Imagem)", accept_multiple_files=True)

if upload:
    all_texts = []
    for f in upload:
        try:
            with st.spinner(f'Lendo {f.name}...'):
                if f.type == "application/pdf":
                    # Converte PDF para imagem para o OCR conseguir ler
                    paginas = convert_from_bytes(f.read())
                    for p in paginas:
                        all_texts.append(pytesseract.image_to_string(p, lang='por'))
                else:
                    # Abre imagem diretamente
                    img = Image.open(f)
                    all_texts.append(pytesseract.image_to_string(img, lang='por'))
        except Exception as e:
            st.error(f"Erro ao ler {f.name}. Verifique se o arquivo não está corrompido.")

    if all_texts:
        res_dados, res_check = extrair_dados_consolidado(all_texts)
        
        # --- EXIBIÇÃO DOS RESULTADOS ---
        st.markdown("### 📊 Ficha Resumo do Cliente")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.metric("Nome do Cliente", res_dados['Nome'])
            st.metric("CPF", res_dados['CPF'])
        
        with c2:
            st.metric("Renda Identificada", res_dados['Renda'])
            st.metric("CEP da Residência", res_dados['CEP'])
            
        with c3:
            st.subheader("✅ Checklist")
            for item, status in res_check.items():
                if status: st.success(f"{item}: OK")
                else: st.error(f"{item}: Pendente")

        # Botão para baixar relatório
        df_export = pd.DataFrame([res_dados])
        csv = df_export.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Dados da Ficha", csv, "ficha_cliente.csv", "text/csv")
