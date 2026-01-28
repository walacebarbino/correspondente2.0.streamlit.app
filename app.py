import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DE AMBIENTE ---
# Caso o Tesseract não esteja no PATH, descomente a linha abaixo:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- FUNÇÕES DE TRATAMENTO E EXTRAÇÃO ---
def preparar_imagem(img):
    img = ImageOps.grayscale(img)
    return ImageEnhance.Contrast(img).enhance(3.0)

def limpar_v(texto):
    if not texto: return 0.0
    val = re.sub(r'[^\d,]', '', texto).replace(',', '.')
    try: return float(val)
    except: return 0.0

def analisar_dossie(texto_consolidado):
    t = texto_consolidado.upper().replace('|', 'I')
    d = {}

    # 1. Identificação (Regra de Exclusão de Empresas)
    nomes = re.findall(r'(?:NOME|COLABORADOR|CLIENTE)[:\s]+([A-Z\s]{10,})', t)
    # Filtra nomes que contenham palavras de empresas comuns em faturas/holerites
    d['nome'] = next((n.strip() for n in nomes if not any(x in n for x in ["CONSORCIO", "SERVICOS", "NEOENERGIA", "CIA"])), "Não Identificado")
    
    d['cpf'] = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t).group(1) if re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t) else "Não Identificado"
    d['rg'] = re.search(r'(\d{7,10})\s*(?:SESP|SSP)', t).group(1) if re.search(r'(\d{7,10})\s*(?:SESP|SSP)', t) else "Não Identificado"
    d['nasc'] = re.search(r'(\d{2}/\d{2}/\d{4})', t).group(1) if re.search(r'(\d{2}/\d{2}/\d{4})', t) else "Não Identificado"

    # 2. Residência (Regra Anti-Erro Neoenergia)
    ceps = re.findall(r'(\d{5}-\d{3})', t)
    # Ignora o CEP da Neoenergia Pernambuco (50050-902)
    d['cep'] = next((c for c in ceps if c != "50050-902"), "Não Identificado")
    
    linhas = t.split('\n')
    d['endereco'] = next((l.strip() for l in linhas if any(x in l for x in ["RUA", "AV.", "ESTRADA"]) and "CNPJ" not in l), "Endereço não detectado")

    # 3. Renda e Cargo (Análise de Holerite)
    # Busca Cargo/Função
    d['cargo'] = re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t).group(1).split('\n')[0].strip() if re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t) else "Não Identificado"
    
    # Extração de Bruto e Líquido (Com Adiantamento)
    brutos = re.findall(r'(?:VENCIMENTOS|TOTAL PROVENTOS|BRUTO)[:\s]*([\d\.,]{5,})', t)
    liquidos = re.findall(r'(?:TOTAL LIQUIDO|LIQUIDO PGTO)[:\s]*([\d\.,]{5,})', t)
    adiantos = re.findall(r'(?:ADIANTAMENTO|ANTECIPACAO|VALE)[:\s]*([\d\.,]{5,})', t)

    val_bruto = limpar_v(brutos[-1]) if brutos else 0.0
    val_liq = limpar_v(liquidos[-1]) if liquidos else 0.0
    val_adi = limpar_v(adiantos[-1]) if adiantos else 0.0

    d['ultimo_bruto'] = val_bruto
    d['ultimo_liq_real'] = val_liq + val_adi # Reincorporação obrigatória
    
    # 4. FGTS (Consolidação de Múltiplos Vínculos)
    # Busca "VALOR PARA FINS RESCISÓRIOS" (e variações de OCR)
    saldos_fgts = re.findall(r'(?:FINS\s+RE[SC]{1,2}ISORIOS).*?([\d\.,]{5,})', t)
    d['fgts_contas'] = [limpar_v(s) for s in saldos_fgts]
    d['fgts_total'] = sum(d['fgts_contas'])

    return d

# --- INTERFACE POR ABAS ---
st.set_page_config(page_title="Correspondente Caixa 2.0", layout="wide")

aba1, aba2, aba3 = st.tabs(["1. Aba Geral", "2. Aba Importação", "3. Aba de Resultados"])

with aba1:
    st.header("Configuração de Origem")
    origem = st.radio("Sinalize a origem de recursos:", ["CLT", "Autônomos/Profissionais Liberais", "Empresários/MEI"])

with aba2:
    st.header("Importação de Dossiê")
    arquivos = st.file_uploader("Arraste os arquivos aqui (PDF ou Imagem)", accept_multiple_files=True)
    
    if arquivos:
        texto_full = ""
        with st.spinner("Analisando documentos..."):
            for f in arquivos:
                try:
                    if f.type == "application/pdf":
                        paginas = convert_from_bytes(f.read(), 150)
                        for p in paginas: texto_full += pytesseract.image_to_string(preparar_imagem(p), lang='por') + " "
                    else:
                        texto_full += pytesseract.image_to_string(preparar_imagem(Image.open(f)), lang='por') + " "
                except Exception as e:
                    st.error(f"Erro no arquivo {f.name}")
            
            # Executa Motor
            res = analisar_dossie(texto_full)
            st.success("Análise Técnica Concluída!")

with aba3:
    if 'res' in locals():
        # Dados Cliente
        st.subheader("👤 Dados do Cliente")
        c1, c2, c3 = st.columns(3)
        c1.write(f"**Nome:** {res['nome']}")
        c1.write(f"**CPF:** {res['cpf']}")
        c2.write(f"**RG:** {res['rg']}")
        c2.write(f"**Nascimento:** {res['nasc']}")
        c3.write(f"**CEP:** {res['cep']}")
        st.write(f"**Endereço:** {res['endereco']}")

        # Financeiro
        st.subheader("💰 Financeiro")
        f1, f2, f3 = st.columns(3)
        f1.metric("Último Bruto", f"R$ {res['ultimo_bruto']:,.2f}")
        f2.metric("Líquido Real (C/ Adiant.)", f"R$ {res['ultimo_liq_real']:,.2f}")
        f3.write(f"**Cargo:** {res['cargo']}")

        # FGTS
        st.subheader("📈 FGTS")
        for i, v in enumerate(res['fgts_contas']):
            st.write(f"Conta {i+1}: R$ {v:,.2f}")
        st.success(f"**Total FGTS Disponível:** R$ {res['fgts_total']:,.2f}")

        # Veredito
        st.divider()
        enquad = "SBPE" if res['ultimo_bruto'] > 8000 else "MCMV"
        capacidade = res['ultimo_liq_real'] * 0.30 # Regra de 30%
        
        v1, v2 = st.columns(2)
        v1.info(f"**Enquadramento:** {enquad}")
        v2.warning(f"**Capacidade de Parcela (30%):** R$ {capacidade:,.2f}")
        
        st.button("📄 Gerar Relatório de Impressão PDF")
    else:
        st.info("Aguardando upload de documentos para processar os resultados.")
