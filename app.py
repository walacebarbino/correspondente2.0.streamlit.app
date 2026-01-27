import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import re
from pdf2image import convert_from_bytes
from datetime import datetime
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Parceria 2.0 - Resumo Macro", layout="wide")
st.title("🏦 Parceria 2.0: Ficha de Qualificação Unificada")

def extrair_valor(padrao, texto):
    match = re.search(padrao, texto, re.I | re.M)
    return match.group(1).strip() if match else None

def analisar_macro_cliente(textos_combinados):
    full_text = " ".join(textos_combinados)
    hoje = datetime.now()
    
    # --- DICIONÁRIO DE DADOS UNIFICADO ---
    ficha = {}

    # 1. Identidade (Busca em todos os docs)
    # Padrão específico para o teu recibo e CNH
    nome = extrair_valor(r'(?:NOME|COLABORADOR|CLIENTE)[:\s-]*([A-Z\s]{10,})', full_text)
    ficha['Nome Cliente'] = nome.split('\n')[0] if nome else "Não identificado"
    
    cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', full_text)
    ficha['CPF'] = cpf.group() if cpf else "Não identificado"
    
    # 2. Localização (Foco no padrão Neoenergia)
    cep = re.search(r'(\d{5}-\d{3})', full_text)
    ficha['CEP'] = cep.group(1) if cep else "Não encontrado"
    
    # Procura endereço completo
    rua = extrair_valor(r'(?:ENDEREÇO|RUA|AV)[:\s]+([A-Z0-9\s,.-]+54440-030|.+AP-\d+)', full_text)
    ficha['Endereço'] = rua if rua else "Verificar Comprovante"

    # 3. Vida Profissional (Foco no Recibo de Pagamento)
    adm = extrair_valor(r'(?:ADMISSÃO)[:\s]*(\d{2}/\d{2}/\d{4})', full_text)
    ficha['Data Admissão'] = adm if adm else "Não encontrada"
    
    cargo = extrair_valor(r'(?:CARGO)[:\s]+([A-Z\s]{5,})', full_text)
    ficha['Cargo'] = cargo.split('\n')[0] if cargo else "Não encontrado"

    # 4. Financeiro e FGTS
    # Padrão para "Total Líquido Pgto" ou "Líquido"
    renda = re.findall(r'(?:LÍQUIDO|TOTAL)[:\s]*R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text, re.I)
    ficha['Renda Líquida'] = f"R$ {renda[-1]}" if renda else "R$ 0,00"
    
    # Soma de FGTS (Procura todos os valores perto de FGTS)
    fgts_valores = re.findall(r'(?:FGTS)[:\s]*R?\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text, re.I)
    total_fgts = sum([float(v.replace('.','').replace(',','.')) for v in fgts_valores])
    ficha['Saldo FGTS Est.'] = f"R$ {total_fgts:,.2f}"

    # 5. Inteligência de Enquadramento
    try:
        val_r = float(renda[-1].replace('.','').replace(',','.')) if renda else 0
        if val_r <= 2850: ficha['Faixa MCMV'] = "Faixa 1"
        elif val_r <= 4700: ficha['Faixa MCMV'] = "Faixa 2"
        else: ficha['Faixa MCMV'] = "Faixa 3 / SBPE"
    except: ficha['Faixa MCMV'] = "Análise Manual"

    # 6. Alertas de Pendência
    alertas = []
    if adm:
        dt = datetime.strptime(adm, '%d/%m/%Y')
        if relativedelta(hoje, dt).years < 1: alertas.append("⚠️ Estabilidade < 1 ano")
    
    ficha['Status do Processo'] = "✅ Pronto para Montagem" if not alertas else " | ".join(alertas)
    
    return ficha

# --- INTERFACE ---
st.info("💡 Sobe todos os documentos do mesmo cliente de uma vez para gerar o Resumo Macro.")
files = st.file_uploader("Documentos (PDF/JPG)", accept_multiple_files=True)

if files:
    all_texts = []
    for f in files:
        with st.spinner(f'Lendo {f.name}...'):
            if f.type == "application/pdf":
                pages = convert_from_bytes(f.read())
                for p in pages: all_texts.append(pytesseract.image_to_string(p, lang='por'))
            else:
                all_texts.append(pytesseract.image_to_string(Image.open(f), lang='por'))
    
    # GERA O RESULTADO ÚNICO
    resultado_final = analisar_macro_cliente(all_texts)
    
    st.write("### 📜 Ficha de Qualificação Macro")
    
    # Exibição em formato de Card para ficar bonito
    col1, col2, col3 = st.columns(3)
    col1.metric("Cliente", resultado_final['Nome Cliente'])
    col1.metric("CPF", resultado_final['CPF'])
    
    col2.metric("Renda", resultado_final['Renda Líquida'])
    col2.metric("Faixa", resultado_final['Faixa MCMV'])
    
    col3.metric("FGTS", resultado_final['Saldo FGTS Est.'])
    col3.metric("Status", "Ok" if "✅" in resultado_final['Status do Processo'] else "Atenção")

    st.table(pd.DataFrame([resultado_final]))
