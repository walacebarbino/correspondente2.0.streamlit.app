import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime, date

# --- CONFIGURAÇÕES INICIAIS ---
st.set_page_config(page_title="Analista Documental Caixa", layout="wide")

def limpar_valor(texto):
    if not texto: return 0.0
    # Remove tudo que não é número, vírgula ou ponto
    val = re.sub(r'[^\d,.]', '', texto)
    if ',' in val and '.' in val:
        val = val.replace('.', '').replace(',', '.')
    elif ',' in val:
        val = val.replace(',', '.')
    try:
        return float(val)
    except:
        return 0.0

def calcular_tempo_casa(data_admissao):
    try:
        admissao = datetime.strptime(data_admissao, "%d/%m/%Y").date()
        hoje = date.today()
        anos = hoje.year - admissao.year - ((hoje.month, hoje.day) < (admissao.month, admissao.day))
        return f"{anos} anos"
    except:
        return "Não identificado"

def validar_data(texto, meses_limite):
    datas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto)
    if not datas: return "⚠️ NÃO DETECTADO"
    
    hoje = datetime.now()
    try:
        # Pega a data mais recente encontrada no documento
        data_doc = max([datetime.strptime(d, "%d/%m/%Y") for d in datas])
        diferenca = (hoje - data_doc).days / 30
        if diferenca > meses_limite:
            return "⚠️ DOCUMENTO EXPIRADO"
        return "✅ VÁLIDO"
    except:
        return "⚠️ ERRO NA DATA"

# --- MOTOR DE EXTRAÇÃO OCR ---
def extrair_dados_documentos(texto_completo):
    dados = {}
    t = texto_completo.upper()

    # Identificação
    dados['nome'] = re.search(r'(?:NOME|CLIENTE)[:\s]+([A-Z\s]{10,})', t).group(1).strip() if re.search(r'(?:NOME|CLIENTE)[:\s]+([A-Z\s]{10,})', t) else "Não encontrado"
    dados['cpf'] = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t).group(1) if re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t) else "Não encontrado"
    dados['rg'] = re.search(r'(?:RG|IDENTIDADE)[:\s]+([\d\.X-]{7,12})', t).group(1) if re.search(r'(?:RG|IDENTIDADE)[:\s]+([\d\.X-]{7,12})', t) else "Não encontrado"
    dados['nasc'] = re.search(r'(?:NASCIMENTO|NASC)[:\s]+(\d{2}/\d{2}/\d{4})', t).group(1) if re.search(r'(?:NASCIMENTO|NASC)[:\s]+(\d{2}/\d{2}/\d{4})', t) else "Não encontrado"
    dados['est_civil'] = re.search(r'(?:ESTADO CIVIL)[:\s]+(SOLTEIRO|CASADO|DIVORCIADO|VIUVO|UNIAO ESTAVEL)', t).group(1) if re.search(r'(?:ESTADO CIVIL)[:\s]+(SOLTEIRO|CASADO|DIVORCIADO|VIUVO|UNIAO ESTAVEL)', t) else "Não encontrado"
    
    # Renda e Cargo
    dados['cargo'] = re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t).group(1).split('\n')[0].strip() if re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t) else "Não encontrado"
    dados['admissao'] = re.search(r'(?:ADMISSAO)[:\s]+(\d{2}/\d{2}/\d{4})', t).group(1) if re.search(r'(?:ADMISSAO)[:\s]+(\d{2}/\d{2}/\d{4})', t) else ""
    
    # Financeiro (Regex para valores após palavras chave)
    brutos = re.findall(r'(?:BRUTO|VENCIMENTOS|PROVENTOS).*?([\d\.,]{5,})', t)
    liquidos = re.findall(r'(?:LIQUIDO|A RECEBER).*?([\d\.,]{5,})', t)
    adiantamentos = re.findall(r'(?:ADIANTAMENTO|ANTECIPACAO|VALE).*?([\d\.,]{5,})', t)

    val_brutos = [limpar_valor(v) for v in brutos]
    dados['ult_bruto'] = val_brutos[-1] if val_brutos else 0.0
    dados['media_bruta'] = sum(val_brutos)/len(val_brutos) if val_brutos else 0.0
    
    # Regra de Reincorporação
    ult_liq = limpar_valor(liquidos[-1]) if liquidos else 0.0
    ult_adt = limpar_valor(adiantamentos[-1]) if adiantamentos else 0.0
    dados['liq_real'] = ult_liq + ult_adt
    
    # FGTS
    empresas = re.findall(r'(?:EMPRESA|EMPREGADOR)[:\s]+([A-Z\s\.]{10,})', t)
    fins = re.findall(r'(?:FINS RESCISORIOS).*?([\d\.,]{5,})', t)
    creditos = re.findall(r'(?:CREDITO DE).*?([\d\.,]{5,})', t)
    
    dados['fgts_lista'] = []
    for i in range(len(fins)):
        dados['fgts_lista'].append({
            'empresa': empresas[i].strip() if i < len(empresas) else "Conta Antiga",
            'valor': limpar_valor(fins[i]) + (limpar_valor(creditos[i]) if i < len(creditos) else 0)
        })
    dados['fgts_total'] = sum(item['valor'] for item in dados['fgts_lista'])

    return dados

# --- INTERFACE STREAMLIT ---
st.title("📑 Sistema de Análise Documental - Crédito Imobiliário")

tab1, tab2, tab3 = st.tabs(["Aba Geral", "Importação", "Resultados"])

with tab1:
    st.header("Origem de Recursos")
    origem = st.selectbox("Selecione a Origem:", ["CLT", "Autônomo/Liberal", "Empresário/MEI"])

with tab2:
    st.header("Importação de Documentos")
    col1, col2 = st.columns(2)
    
    with col1:
        u_id = st.file_uploader("Identificação (RG/CPF/CNH/Certidões)", accept_multiple_files=True)
        u_res = st.file_uploader("Comprovante de Residência", accept_multiple_files=True)
        u_ext = st.file_uploader("Extratos Bancários (6 meses)", accept_multiple_files=True)
        
    with col2:
        u_renda = st.file_uploader("Comprovação de Renda (Holerites)", accept_multiple_files=True)
        u_fgts = st.file_uploader("Extratos FGTS", accept_multiple_files=True)
        u_ir = st.file_uploader("IR / DECORE", accept_multiple_files=True)

    status_data = []
    texto_acumulado = ""

    if st.button("Processar Documentos"):
        # Lógica de processamento simplificada para o exemplo
        all_uploads = [
            (u_id, "ID", 999), (u_res, "Residência", 3), (u_renda, "Renda", 3), 
            (u_ext, "Extrato", 6), (u_fgts, "FGTS", 99), (u_ir, "IR", 12)
        ]
        
        for up, tipo, prazo in all_uploads:
            if up:
                for f in up:
                    # Se for PDF, converte pra imagem, se imagem abre direto
                    if f.type == "application/pdf":
                        pags = convert_from_bytes(f.read())
                        txt = " ".join([pytesseract.image_to_string(p, lang='por') for p in pags])
                    else:
                        txt = pytesseract.image_to_string(Image.open(f), lang='por')
                    
                    st_doc = validar_data(txt, prazo) if prazo < 99 else "✅ IMPORTADO"
                    status_data.append({"Documento": f.name, "Tipo": tipo, "Status": st_doc})
                    texto_acumulado += " " + txt
        
        st.table(pd.DataFrame(status_data))
        st.session_state['dados_extraidos'] = extrair_dados_documentos(texto_acumulado)

with tab3:
    if 'dados_extraidos' in st.session_state:
        d = st.session_state['dados_extraidos']
        st.header("Relatório de Análise")
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Dados Cadastrais")
            st.write(f"**Nome:** {d['nome']}")
            st.write(f"**CPF:** {d['cpf']} | **RG:** {d['rg']}")
            st.write(f"**Nascimento:** {d['nasc']}")
            st.write(f"**Estado Civil:** {d['est_civil']}")
            st.write(f"**Tempo de Casa:** {calcular_tempo_casa(d['admissao'])}")
            
        with c2:
            st.subheader("Análise Financeira")
            st.write(f"**Cargo:** {d['cargo']}")
            st.write(f"**Média Bruta:** R$ {d['media_bruta']:,.2f}")
            st.write(f"**Último Bruto:** R$ {d['ult_bruto']:,.2f}")
            st.metric("Líquido Real (C/ Adiantamento)", f"R$ {d['liq_real']:,.2f}")

        st.subheader("FGTS e Veredito")
        for conta in d['fgts_lista']:
            st.write(f"- {conta['empresa']}: R$ {conta['valor']:,.2f}")
        
        modalidade = "SBPE" if d['ult_bruto'] > 8000 else "MCMV"
        st.success(f"**Veredito:** Modalidade {modalidade} | Status: Provável Aprovação")
