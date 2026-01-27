import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
import io
from pdf2image import convert_from_bytes
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Configuração de Página
st.set_page_config(page_title="Parceria 2.0 - Sistema Integrado Final", layout="wide")
st.title("🏦 Parceria 2.0: Analista Digital Expert & Simulador")

# --- 1. MOTOR DE TRATAMENTO DE IMAGEM (OCR PRO) ---
def tratar_imagem(imagem_pil):
    """Aplica filtros para garantir leitura de CEP e valores pequenos"""
    img = ImageOps.grayscale(imagem_pil)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.5)
    return img

# --- 2. INTELIGÊNCIA DE MODALIDADES E SIMULAÇÃO ---
def calcular_simulacao_sac(valor_financiado, prazo_meses, taxa_anual):
    """Gera estimativa de primeira e última parcela na Tabela SAC"""
    taxa_mensal = (1 + taxa_anual)**(1/12) - 1
    amortizacao = valor_financiado / prazo_meses
    juros_1 = valor_financiado * taxa_mensal
    primeira_parcela = amortizacao + juros_1
    
    # Estimativa simplificada da última parcela
    juros_n = amortizacao * taxa_mensal
    ultima_parcela = amortizacao + juros_n
    
    return primeira_parcela, ultima_parcela

def definir_modalidade_caixa(renda, tempo_fgts_anos):
    if renda <= 8000:
        return "Minha Casa, Minha Vida (MCMV)", "Juros reduzidos e possível Subsídio.", 0.045
    elif tempo_fgts_anos >= 3:
        return "Pró-Cotista (FGTS)", "Taxas menores que o SBPE comum.", 0.085
    else:
        return "SBPE (Poupança)", "Taxas de mercado (Poupança + Juros fixos).", 0.099

# --- 3. MOTOR DE EXTRAÇÃO E REGRAS ---
def extrair_dados_total(textos_combinados):
    full_text = " ".join(textos_combinados).upper()
    hoje = datetime.now()
    dados = {}
    checklist = {
        "Identificação (RG/CNH)": False,
        "Comprovante de Renda": False,
        "Comprovante de Residência": False,
        "Estado Civil": False
    }

    # IDENTIFICAÇÃO (Nome e Estado Civil)
    nome_match = re.search(r'(?:NOME DO CLIENTE|COLABORADOR|CLIENTE)[:\s\n]+([A-Z\s]{10,})', full_text)
    if nome_match:
        nome_bruto = nome_match.group(1).split('\n')[0].replace("DO CLIENTE", "").strip()
        dados['Nome'] = re.sub(r'\d+', '', nome_bruto).strip() # Limpa números de contrato
        checklist["Identificação (RG/CNH)"] = True
    else: dados['Nome'] = "Não identificado"

    est_civil = re.search(r'\b(SOLTEIRO|CASADO|DIVORCIADO|VIÚVO|UNIÃO ESTÁVEL|SOLTEIRA|CASADA|DIVORCIADA|VIÚVA)\b', full_text)
    dados['Estado Civil'] = est_civil.group(1) if est_civil else "Verificar Certidão"
    if "Verificar" not in dados['Estado Civil']: checklist["Estado Civil"] = True

    # CEP (Padrão Universal)
    ceps = re.findall(r'\d{5}-\d{3}', full_text)
    dados['CEP'] = ceps[0] if ceps else "Não encontrado"
    if dados['CEP'] != "Não encontrado": checklist["Comprovante de Residência"] = True

    # FINANCEIRO (Bruto, Descontos, Líquido)
    bruto_match = re.findall(r'(?:VENCIMENTOS|TOTAL VENCIMENTOS|VALOR BRUTO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    desc_match = re.findall(r'(?:TOTAL DESCONTOS|DESCONTOS|VALOR DESCONTOS)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    liq_match = re.findall(r'(?:LÍQUIDO|LÍQUIDO PGTO|TOTAL LÍQUIDO)[:\s]*R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})', full_text)
    
    val_renda = float(liq_match[-1].replace('.', '').replace(',', '.')) if liq_match else 0.0
    dados['Salário Bruto'] = f"R$ {bruto_match[0]}" if bruto_match else "N/A"
    dados['Total Descontos'] = f"R$ {desc_match[0]}" if desc_match else "N/A"
    dados['Renda Líquida'] = val_renda
    if val_renda > 0: checklist["Comprovante de Renda"] = True

    # TEMPO DE CASA E MODALIDADE
    adm = re.search(r'(?:ADMISSÃO|ADM)[:\s]*(\d{2}/\d{2}/\d{4})', full_text)
    anos_fgts = 0
    if adm:
        dt_adm = datetime.strptime(adm.group(1), '%d/%m/%Y')
        anos_fgts = (hoje - dt_adm).days / 365
        dados['Tempo Casa'] = f"{relativedelta(hoje, dt_adm).years} anos"
    else: dados['Tempo Casa'] = "N/A"

    mod, desc_mod, taxa = definir_modalidade_caixa(val_renda, anos_fgts)
    dados['Modalidade'] = mod
    dados['Justificativa'] = desc_mod
    dados['Taxa Anual'] = taxa

    # EXTRATOS / AUTÔNOMO / IRPF
    if "INFORME DE RENDIMENTOS" in full_text:
        cnpj = re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', full_text)
        dados['Fonte/CNPJ'] = cnpj.group() if cnpj else "Identificado"

    return dados, checklist

# --- 4. INTERFACE ---
upload = st.file_uploader("📂 Envie o Dossier do Cliente (PDF/Imagens)", accept_multiple_files=True)

if upload:
    all_texts = []
    for f in upload:
        with st.spinner(f'Processando {f.name}...'):
            if f.type == "application/pdf":
                paginas = convert_from_bytes(f.read())
                for p in paginas:
                    all_texts.append(pytesseract.image_to_string(tratar_imagem(p), lang='por'))
            else:
                all_texts.append(pytesseract.image_to_string(tratar_imagem(Image.open(f)), lang='por'))
    
    if all_texts:
        res, check = extrair_dados_total(all_texts)
        
        st.markdown("---")
        col1, col2, col3 = st.columns([1.5, 1, 1])
        
        with col1:
            st.subheader("👤 Identificação Proponente")
            st.info(f"**Nome:** {res['Nome']}\n\n**Estado Civil:** {res['Estado Civil']}\n\n**CEP:** {res['CEP']}")
            st.write(f"**Tempo de Empresa:** {res['Tempo Casa']}")

        with col2:
            st.subheader("💰 Análise Financeira")
            st.metric("Renda Líquida", f"R$ {res['Renda Líquida']:,.2f}")
            st.write(f"**Bruto:** {res['Salário Bruto']}")
            st.write(f"**Descontos:** {res['Total Descontos']}")
            st.caption(f"**Modalidade:** {res['Modalidade']}")

        with col3:
            st.subheader("✅ Checklist")
            for item, status in check.items():
                st.write(f"{'🟢' if status else '🔴'} {item}")

        # --- SEÇÃO DE SIMULAÇÃO ---
        st.markdown("---")
        st.subheader("🧮 Simulação de Financiamento (Estimativa SAC)")
        
        c_sim1, c_sim2 = st.columns(2)
        with c_sim1:
            v_imovel = st.number_input("Valor do Imóvel (R$)", value=200000.0)
            v_finan = st.number_input("Valor Financiado (R$)", value=v_imovel * 0.8)
        with c_sim2:
            prazo = st.slider("Prazo (Meses)", 120, 420, 360)
            st.write(f"**Taxa Anual Aplicada:** {res['Taxa Anual']*100}%")

        p1, pN = calcular_simulacao_sac(v_finan, prazo, res['Taxa Anual'])
        
        res1, res2, res3 = st.columns(3)
        res1.metric("Primeira Parcela", f"R$ {p1:,.2f}")
        res2.metric("Última Parcela", f"R$ {pN:,.2f}")
        
        margem_30 = res['Renda Líquida'] * 0.3
        if p1 > margem_30:
            st.error(f"⚠️ Parcela excede 30% da renda líquida (Máximo: R$ {margem_30:,.2f})")
        else:
            st.success("✅ Parcela dentro da margem de 30% do cliente.")

        with st.expander("Ver Planilha Consolidada"):
            st.table(pd.DataFrame([res]))
